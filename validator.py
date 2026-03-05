import csv
import logging
import os
import re
import smtplib
import socket
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import dns.resolver

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Constants
TIMEOUT = 10
DELAY_BETWEEN_PINGS = 1.5
DUMMY_SENDER = "verifier@gmail.com"
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def get_emails_from_url(url):
    """Scrapes a URL for email addresses using regex."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        
        # Search in text and tag attributes (some obfuscate emails in data-email)
        emails = set(re.findall(EMAIL_REGEX, response.text))
        return emails, response.text
    except Exception as e:
        logger.error(f"Error scraping emails from {url}: {e}")
        return set(), None

def find_contact_page(soup_html, base_url):
    """Attempts to find a 'Contact' page link."""
    if not soup_html:
        return None
    
    soup = BeautifulSoup(soup_html, 'html.parser')
    contact_patterns = ["contact", "reach us", "get in touch", "support"]
    
    for link in soup.find_all('a', href=True):
        link_text = link.get_text().lower()
        href = link['href'].lower()
        
        if any(pattern in link_text or pattern in href for pattern in contact_patterns):
            full_url = urljoin(base_url, link['href'])
            # Ensure it's the same domain
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                return full_url
            
    return None

def get_mx_records(domain):
    """Gets MX records for a domain sorted by priority."""
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx_list = sorted([(r.preference, str(r.exchange).rstrip('.')) for r in records])
        return [mx[1] for mx in mx_list]
    except Exception as e:
        logger.debug(f"MX lookup failed for {domain}: {e}")
        return []

def verify_email_smtp(email, mx_server):
    """Verifies an email existence via SMTP ping."""
    try:
        # Connect to MX server
        server = smtplib.SMTP(mx_server, port=25, timeout=TIMEOUT)
        server.helo(socket.gethostname())
        server.mail(DUMMY_SENDER)
        
        code, message = server.rcpt(email)
        server.quit()
        
        if code == 250:
            return "Valid"
        elif code == 550:
            return "Invalid"
        else:
            return f"Unknown ({code})"
    except Exception as e:
        logger.debug(f"SMTP verify failed for {email} on {mx_server}: {e}")
        return f"Error ({type(e).__name__})"

def is_catch_all(domain, mx_server):
    """Checks if a domain is a catch-all by pinging a random email."""
    random_email = f"verify_test_{int(time.time())}@{domain}"
    status = verify_email_smtp(random_email, mx_server)
    return status == "Valid"

def process_leads(input_file="verified_buyers.csv", output_file="final_leads.csv"):
    """Main execution loop for finding and verifying emails."""
    if not os.path.exists(input_file):
        logger.error(f"Input file {input_file} not found.")
        return

    final_leads = []
    
    with open(input_file, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        leads = list(reader)

    logger.info(f"Starting validation for {len(leads)} leads...")

    for lead in leads:
        url = lead['url']
        domain_parts = urlparse(url).netloc.split('.')
        # Basic domain extraction
        domain = '.'.join(domain_parts[-2:]) if len(domain_parts) > 1 else domain_parts[0]
        logger.info(f"Processing domain: {domain}")
        
        # 1. Discovery
        found_emails, html = get_emails_from_url(url)
        contact_url = find_contact_page(html, url)
        if contact_url and contact_url != url:
            logger.info(f"Checking contact page: {contact_url}")
            contact_emails, _ = get_emails_from_url(contact_url)
            found_emails.update(contact_emails)
        
        # Filter emails to ensure they belong to the target domain
        domain_emails = {e for e in found_emails if e.lower().endswith(domain.lower())}
        
        if not domain_emails:
            logger.warning(f"No emails found for {domain}")
            final_leads.append({**lead, "emails": "None Found", "verification_status": "N/A"})
            continue

        # 2. Validation
        mx_servers = get_mx_records(domain)
        if not mx_servers:
            logger.warning(f"No MX records for {domain}")
            final_leads.append({**lead, "emails": ", ".join(domain_emails), "verification_status": "No MX Records"})
            continue
            
        primary_mx = mx_servers[0]
        catch_all = is_catch_all(domain, primary_mx)
        
        validated_emails = []
        for email in domain_emails:
            time.sleep(DELAY_BETWEEN_PINGS)
            status = verify_email_smtp(email, primary_mx)
            
            if catch_all and status == "Valid":
                status = "Catch-all (Probable)"
                
            validated_emails.append(f"{email} ({status})")
            logger.info(f"Verified {email}: {status}")

        final_leads.append({
            **lead,
            "emails": ", ".join(validated_emails),
            "verification_status": "Catch-all" if catch_all else "Verified"
        })

    # 3. Save Results
    if final_leads:
        keys = final_leads[0].keys()
        with open(output_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(final_leads)
        logger.info(f"Saved {len(final_leads)} final leads to {output_file}")
    else:
        logger.warning("No leads to save.")

if __name__ == "__main__":
    process_leads()
