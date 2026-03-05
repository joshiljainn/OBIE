import asyncio
import argparse
import csv
import logging
import random
import re
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Constants
EXCLUDED_DOMAINS = [
    "google.com", "google.co.uk", "google.ae", "facebook.com", "linkedin.com",
    "twitter.com", "instagram.com", "youtube.com", "alibaba.com", "indiamart.com",
    "thomasnet.com", "globalsources.com", "amazon.com", "ebay.com", "pinterest.com",
    "yelp.com", "yellowpages.com"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

def is_valid_url(url):
    """Basic filter for organic results."""
    if not url or not url.startswith("http"):
        return False
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Remove 'www.' for easier comparison
    clean_domain = domain.replace("www.", "")
    
    for excluded in EXCLUDED_DOMAINS:
        if excluded in clean_domain:
            return False
            
    return True

async def handle_cookie_consent(page):
    """Handles Google's cookie consent popup."""
    try:
        # Look for "Accept all" button. Google uses various IDs/text depending on region.
        # Common selectors: 'button:has-text("Accept all")', 'button:has-text("I agree")', '#L2AGLb'
        consent_button = await page.wait_for_selector('button:has-text("Accept all"), button:has-text("I agree"), #L2AGLb', timeout=5000)
        if consent_button:
            await consent_button.click()
            logger.info("Cookie consent accepted.")
            await asyncio.sleep(random.uniform(1, 2))
    except Exception:
        # If no popup, just continue
        pass

async def scrape_google(product, company_type, country_tld, pages=3, headless=True):
    """Scrapes Google for raw URLs."""
    # Simplified query construction
    query = f"site:{country_tld} {company_type} {product} -manufacturer"
    # Use localized Google URL for better regional results
    base_search_url = "https://www.google.ae/search" if country_tld == ".ae" else "https://www.google.com/search"
    search_url = f"{base_search_url}?q={query}"
    
    raw_urls = set()
    
    async with async_playwright() as p:
        # Launch browser with more standard arguments
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        await stealth_async(page)
        
        logger.info(f"Navigating to Google with query: {query}")
        try:
            # Increase timeout and use a more resilient wait
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.warning(f"Initial navigation timeout: {e}. Retrying with shorter wait...")
            await page.goto(search_url, wait_until="commit", timeout=30000)
        
        # Give it a moment to load and check for cookie consent
        await asyncio.sleep(random.uniform(3, 6))
        await handle_cookie_consent(page)
        
        for current_page in range(1, pages + 1):
            logger.info(f"Processing page {current_page}...")
            
            # Check for CAPTCHA or blocking text
            content = await page.content()
            if 'form#captcha-form' in content or "captcha" in page.url.lower() or "not a robot" in content.lower():
                logger.error("CAPTCHA detected or access blocked! Stopping and saving progress.")
                break
            
            # Extract URLs
            # Google organic result links are inside h3/a tags usually.
            # We'll use a broader set of selectors to catch varying layouts
            selectors = [
                'div.g a[href^="http"]:not([href*="google.com"])',
                'div#search a[href^="http"]:not([href*="google.com"])',
                'div.yuRUbf a[href^="http"]',  # Common class for organic links
                'div.OrganicResult a[href^="http"]'
            ]
            
            links = []
            for selector in selectors:
                found = await page.query_selector_all(selector)
                links.extend(found)
            
            extracted_on_page = 0
            for link in links:
                href = await link.get_attribute('href')
                if href and is_valid_url(href):
                    if href not in raw_urls:
                        raw_urls.add(href)
                        extracted_on_page += 1
            
            logger.info(f"Extracted {extracted_on_page} URLs from page {current_page}.")
            
            if current_page < pages:
                # Click 'Next' button
                try:
                    next_button = await page.query_selector('a#pnnext')
                    if next_button:
                        # Human-like delay
                        delay = random.uniform(3, 7)
                        logger.info(f"Delaying for {delay:.2f}s before next page...")
                        await asyncio.sleep(delay)
                        await next_button.click()
                        await page.wait_for_load_state("domcontentloaded")
                    else:
                        logger.info("No 'Next' button found. Ending search.")
                        break
                except Exception as e:
                    logger.warning(f"Could not navigate to next page: {e}")
                    break
                    
        await browser.close()
        
    return list(raw_urls)

def save_to_csv(urls, filename="raw_domains.csv"):
    """Saves unique URLs to a CSV file."""
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["url"])
        for url in urls:
            writer.writerow([url])
    logger.info(f"Saved {len(urls)} unique URLs to {filename}")

async def main():
    parser = argparse.ArgumentParser(description="OBIE Phase 1: Targeted Crawler")
    parser.add_argument("--product", required=True, help="Product keyword (e.g., 'ceramic tiles')")
    parser.add_argument("--type", required=True, help="Company type (e.g., 'importer OR distributor')")
    parser.add_argument("--country", required=True, help="Target country TLD (e.g., '.uk' or '.ae')")
    parser.add_argument("--pages", type=int, default=3, help="Number of Google pages to scrape (default: 3)")
    parser.add_argument("--output", default="raw_domains.csv", help="Output file name")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Run browser in non-headless mode")
    parser.set_defaults(headless=True)
    
    args = parser.parse_args()
    
    try:
        urls = await scrape_google(args.product, args.type, args.country, args.pages, args.headless)
        if urls:
            save_to_csv(urls, args.output)
        else:
            logger.warning("No URLs found. (Check CAPTCHA if running headless)")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
