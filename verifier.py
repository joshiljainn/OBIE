import csv
import logging
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Constants
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MAX_WORDS = 3000
TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not found in environment variables. LLM classification will fail.")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

def get_text_from_url(url):
    """Fetches and cleans text from a URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove scripts, styles, and other noise
        for script_or_style in soup(["script", "style", "header", "footer", "nav"]):
            script_or_style.decompose()
            
        text = soup.get_text(separator=' ')
        # Basic cleaning
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Truncate to MAX_WORDS
        words = text.split()[:MAX_WORDS]
        return ' '.join(words), soup
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching {url}: {e}")
        return None, None

def find_about_page(soup, base_url):
    """Finds the 'About' page link in the soup."""
    if not soup:
        return None
    
    # Common words for 'About' links
    about_patterns = ["about", "who we are", "company", "our story"]
    
    for link in soup.find_all('a', href=True):
        link_text = link.get_text().lower()
        href = link['href'].lower()
        
        if any(pattern in link_text or pattern in href for pattern in about_patterns):
            return urljoin(base_url, link['href'])
            
    return None

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(Exception) # Specific Groq exceptions could be used here
)
def classify_company(text, url):
    """Uses Groq LLM to classify the company based on scraped text."""
    if not client:
        return {"is_buyer": False, "company_type": "N/A", "reason": "No API Key"}

    system_prompt = (
        "You are an expert B2B business analyst. Your task is to analyze the provided company website text "
        "and determine if the company is an IMPORTER/BUYER or a MANUFACTURER/COMPETITOR for the product described. "
        "Buyers are typically distributors, wholesalers, or retailers. Manufacturers produce the goods themselves. "
        "Output ONLY valid JSON."
    )
    
    user_prompt = (
        f"Analyze this company website content from {url}:\n\n"
        f"TEXT CONTENT: {text[:5000]}\n\n"
        "Instructions:\n"
        "1. Determine if they buy/import products or manufacture them.\n"
        "2. identify their primary business model (e.g., Wholesaler, Distributor, Manufacturer, Retailer).\n"
        "3. Respond with a JSON object in this EXACT format: "
        '{"is_buyer": boolean, "company_type": "string", "reason": "string"}'
    )

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result_content = chat_completion.choices[0].message.content
        return json.loads(result_content)
    except Exception as e:
        logger.error(f"LLM Classification error for {url}: {e}")
        raise # For retry

def process_domains(input_file="raw_domains.csv", output_file="verified_buyers.csv"):
    """Main loop to process domains."""
    if not os.path.exists(input_file):
        logger.error(f"Input file {input_file} not found.")
        return

    verified_leads = []
    
    with open(input_file, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        domains = [row['url'] for row in reader]

    logger.info(f"Starting verification for {len(domains)} domains...")

    for url in domains:
        logger.info(f"Analyzing {url}...")
        
        # 1. Fetch homepage
        text, soup = get_text_from_url(url)
        if not text:
            logger.warning(f"Skipping {url} due to fetch error or block.")
            continue
            
        # 2. Try to find/fetch About page for better context
        about_url = find_about_page(soup, url)
        if about_url and about_url != url:
            logger.info(f"Found About page: {about_url}")
            about_text, _ = get_text_from_url(about_url)
            if about_text:
                text = f"{text}\n\nABOUT PAGE CONTENT:\n{about_text}"
        
        # 3. Classify with LLM
        try:
            classification = classify_company(text, url)
            
            if classification.get("is_buyer"):
                logger.info(f"Qualified Buyer Found: {url}")
                verified_leads.append({
                    "url": url,
                    "company_type": classification.get("company_type"),
                    "reason": classification.get("reason")
                })
            else:
                logger.info(f"Disqualified: {url} - {classification.get('reason')}")
        except Exception as e:
            logger.error(f"Failed to classify {url} after retries: {e}")

    # 4. Save results
    if verified_leads:
        keys = verified_leads[0].keys()
        with open(output_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(verified_leads)
        logger.info(f"Saved {len(verified_leads)} verified buyers to {output_file}")
    else:
        logger.warning("No verified buyers found.")

if __name__ == "__main__":
    process_domains()
