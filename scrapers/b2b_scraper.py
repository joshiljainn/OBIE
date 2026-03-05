"""
B2B Trade Board Scrapers
Scrapes active buying leads from TradeKey, go4WorldBusiness, EC21

These sites have buyers posting RFQs (Request for Quotations) daily.
We scrape: product, quantity, destination, deadline, buyer contact info
"""
import asyncio
import csv
import logging
import re
import os
from datetime import datetime, timedelta
from typing import List, Optional
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth

from models import BuyerLead, calculate_intent_level

stealth = Stealth()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]


class TradeKeyScraper:
    """
    Scrapes buying leads from TradeKey.com
    URL pattern: https://www.tradekey.com/buying-leads/[product]/
    """
    
    BASE_URL = "https://www.tradekey.com"
    BUYING_LEADS_URL = "https://www.tradekey.com/buying-leads/search.html"
    
    def __init__(self, product_keywords: List[str], headless: bool = True):
        self.product_keywords = product_keywords
        self.headless = headless
        self.leads = []
    
    async def scrape(self, pages: int = 3) -> List[BuyerLead]:
        """Scrape buying leads for all keywords"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent=USER_AGENTS[0],
                viewport={'width': 1366, 'height': 768}
            )
            page = await context.new_page()
            await stealth.apply_stealth_async(page)
            
            for keyword in self.product_keywords:
                logger.info(f"Scraping TradeKey for: {keyword}")
                await self._scrape_keyword(page, keyword, pages)
                await asyncio.sleep(3)  # Be respectful between keywords
            
            await browser.close()
        
        return self.leads
    
    async def _scrape_keyword(self, page, keyword: str, max_pages: int):
        """Scrape a single keyword's results"""
        search_url = f"{self.BUYING_LEADS_URL}?query={keyword}&searchType=buying-leads"
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)  # Wait for dynamic content
        except Exception as e:
            logger.warning(f"Failed to load {search_url}: {e}")
            return
        
        for current_page in range(max_pages):
            logger.info(f"TradeKey page {current_page + 1} for '{keyword}'")
            
            # Extract leads from current page
            leads = await self._extract_leads_from_page(page)
            self.leads.extend(leads)
            logger.info(f"Found {len(leads)} leads on this page")
            
            # Try to go to next page
            if current_page < max_pages - 1:
                next_btn = await page.query_selector('a[title="Next"], a.next, .next a')
                if next_btn:
                    await next_btn.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(3)
                else:
                    logger.info("No more pages available")
                    break
            
            await asyncio.sleep(2)
    
    async def _extract_leads_from_page(self, page) -> List[BuyerLead]:
        """Extract lead data from the current page"""
        leads = []
        
        # Get all lead cards
        lead_cards = await page.query_selector_all(
            '.buying-leads-item, .rfq-item, div[itemtype="http://schema.org/RFQ"], .search-result-item'
        )
        
        for card in lead_cards:
            try:
                # Extract product/title
                title_el = await card.query_selector('h3 a, .title a, .product-title a')
                product = await title_el.inner_text() if title_el else ""
                
                # Extract link
                link_el = await card.query_selector('a[href*="/buying-leads/"], a[href*="/rfq/"]')
                source_url = await link_el.get_attribute('href') if link_el else ""
                if source_url and not source_url.startswith('http'):
                    source_url = f"{self.BASE_URL}{source_url}"
                
                # Extract quantity
                qty_el = await card.query_selector('.quantity, .qty, span:has-text("Quantity")')
                quantity = await qty_el.inner_text() if qty_el else ""
                
                # Extract destination
                dest_el = await card.query_selector('.destination, .location, span:has-text("Destination")')
                destination = await dest_el.inner_text() if dest_el else ""
                
                # Extract buyer name
                buyer_el = await card.query_selector('.buyer-name, .company-name, .member-name')
                buyer_name = await buyer_el.inner_text() if buyer_el else ""
                
                # Extract description snippet
                desc_el = await card.query_selector('.description, .details, .brief')
                description = await desc_el.inner_text() if desc_el else ""
                
                if product and product.strip():
                    lead = BuyerLead(
                        source_type="b2b_board",
                        source_url=source_url or f"{self.BASE_URL}/search?q={product}",
                        intent_level=calculate_intent_level(
                            has_quantity=bool(quantity),
                            has_destination=bool(destination)
                        ),
                        product=product.strip()[:200],
                        quantity=quantity.strip() if quantity else None,
                        destination_country=self._extract_country(destination),
                        buyer_name=buyer_name.strip() if buyer_name else None,
                        description=description.strip() if description else None,
                        scraped_at=datetime.now().isoformat()
                    )
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"Error extracting lead: {e}")
        
        return leads
    
    def _extract_country(self, text: str) -> Optional[str]:
        """Extract country name from text"""
        if not text:
            return None
        # Common country patterns
        country_patterns = [
            r'\b(UAE|Dubai|Saudi Arabia|USA|UK|Germany|France|China|India|Pakistan|'
            r'Bangladesh|Vietnam|Thailand|Malaysia|Indonesia|Turkey|Egypt|Nigeria|'
            r'Kenya|South Africa|Australia|Canada|Brazil|Mexico|Spain|Italy|Netherlands)\b'
        ]
        for pattern in country_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None


class Go4WorldBusinessScraper:
    """
    Scrapes buying leads from go4WorldBusiness.com
    URL pattern: https://www.go4worldbusiness.com/buyers/[product].html
    """
    
    BASE_URL = "https://www.go4worldbusiness.com"
    
    def __init__(self, product_keywords: List[str], headless: bool = True):
        self.product_keywords = product_keywords
        self.headless = headless
        self.leads = []
    
    async def scrape(self, pages: int = 3) -> List[BuyerLead]:
        """Scrape buying leads for all keywords"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent=USER_AGENTS[1],
                viewport={'width': 1366, 'height': 768}
            )
            page = await context.new_page()
            await stealth.apply_stealth_async(page)
            
            for keyword in self.product_keywords:
                logger.info(f"Scraping go4WorldBusiness for: {keyword}")
                await self._scrape_keyword(page, keyword, pages)
                await asyncio.sleep(3)
            
            await browser.close()
        
        return self.leads
    
    async def _scrape_keyword(self, page, keyword: str, max_pages: int):
        """Scrape a single keyword's results"""
        # go4WorldBusiness URL pattern for buyers
        search_url = f"{self.BASE_URL}/find.php?search={keyword}&buyers=1"
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
        except Exception as e:
            logger.warning(f"Failed to load {search_url}: {e}")
            return
        
        for current_page in range(max_pages):
            logger.info(f"go4WorldBusiness page {current_page + 1} for '{keyword}'")
            
            leads = await self._extract_leads_from_page(page)
            self.leads.extend(leads)
            logger.info(f"Found {len(leads)} leads on this page")
            
            if current_page < max_pages - 1:
                # Click next page
                next_btn = await page.query_selector('a.next, .pagination-next, a[rel="next"]')
                if next_btn:
                    await next_btn.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(3)
                else:
                    break
            
            await asyncio.sleep(2)
    
    async def _extract_leads_from_page(self, page) -> List[BuyerLead]:
        """Extract lead data from the current page"""
        leads = []
        
        # go4WorldBusiness has a specific structure
        lead_cards = await page.query_selector_all(
            '.postings, .buyer-leads-item, div[itemtype="http://schema.org/BuyAction"]'
        )
        
        for card in lead_cards:
            try:
                # Product title
                title_el = await card.query_selector('a[itemprop="name"], .title a, h3 a')
                product = await title_el.inner_text() if title_el else ""
                
                # URL
                link_el = await card.query_selector('a[href*="/product/"]')
                source_url = await link_el.get_attribute('href') if link_el else ""
                
                # Quantity
                qty_text = await card.inner_text()
                qty_match = re.search(r'(\d+\s*(kg|tons|tonnes|mt|pieces|units|containers|boxes))', qty_text, re.IGNORECASE)
                quantity = qty_match.group(0) if qty_match else None
                
                # Destination country
                dest_match = re.search(r'(UAE|Dubai|Saudi Arabia|USA|UK|Germany|France|China|India|Pakistan|Bangladesh)', qty_text, re.IGNORECASE)
                destination = dest_match.group(1) if dest_match else None
                
                # Buyer info
                buyer_el = await card.query_selector('.company-name, .member-name, .supplier-name')
                buyer_name = await buyer_el.inner_text() if buyer_el else ""
                
                if product and product.strip():
                    lead = BuyerLead(
                        source_type="b2b_board",
                        source_url=source_url or f"{self.BASE_URL}/search?q={product}",
                        intent_level=calculate_intent_level(
                            has_quantity=bool(quantity),
                            has_destination=bool(destination)
                        ),
                        product=product.strip()[:200],
                        quantity=quantity,
                        destination_country=destination,
                        buyer_name=buyer_name.strip() if buyer_name else None,
                        scraped_at=datetime.now().isoformat()
                    )
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"Error extracting lead: {e}")
        
        return leads


class EC21Scraper:
    """
    Scrapes buying leads from EC21.com
    URL pattern: https://www.ec21.com/buyOffer/[product]/
    """
    
    BASE_URL = "https://www.ec21.com"
    
    def __init__(self, product_keywords: List[str], headless: bool = True):
        self.product_keywords = product_keywords
        self.headless = headless
        self.leads = []
    
    async def scrape(self, pages: int = 3) -> List[BuyerLead]:
        """Scrape buying leads for all keywords"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent=USER_AGENTS[2],
                viewport={'width': 1366, 'height': 768}
            )
            page = await context.new_page()
            await stealth.apply_stealth_async(page)
            
            for keyword in self.product_keywords:
                logger.info(f"Scraping EC21 for: {keyword}")
                await self._scrape_keyword(page, keyword, pages)
                await asyncio.sleep(3)
            
            await browser.close()
        
        return self.leads
    
    async def _scrape_keyword(self, page, keyword: str, max_pages: int):
        """Scrape a single keyword's results"""
        search_url = f"{self.BASE_URL}/buyOffer/search.do?searchword={keyword}"
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
        except Exception as e:
            logger.warning(f"Failed to load {search_url}: {e}")
            return
        
        for current_page in range(max_pages):
            logger.info(f"EC21 page {current_page + 1} for '{keyword}'")
            
            leads = await self._extract_leads_from_page(page)
            self.leads.extend(leads)
            logger.info(f"Found {len(leads)} leads on this page")
            
            if current_page < max_pages - 1:
                next_btn = await page.query_selector('a.next, .page-next, a[title="Next"]')
                if next_btn:
                    await next_btn.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(3)
                else:
                    break
            
            await asyncio.sleep(2)
    
    async def _extract_leads_from_page(self, page) -> List[BuyerLead]:
        """Extract lead data from the current page"""
        leads = []
        
        lead_cards = await page.query_selector_all(
            '.buyOffer-list, .buying-leads-item, .offer-item'
        )
        
        for card in lead_cards:
            try:
                # Product
                title_el = await card.query_selector('a.subject, .title a, h3 a')
                product = await title_el.inner_text() if title_el else ""
                
                # URL
                link_el = await card.query_selector('a.subject, .title a')
                source_url = await link_el.get_attribute('href') if link_el else ""
                if source_url and source_url.startswith('/'):
                    source_url = f"{self.BASE_URL}{source_url}"
                
                # Quantity and details from text
                text = await card.inner_text()
                
                qty_match = re.search(r'(\d+\s*(kg|tons|tonnes|mt|pieces|units))', text, re.IGNORECASE)
                quantity = qty_match.group(0) if qty_match else None
                
                dest_match = re.search(r'(FOB|CIF|CNF)\s*([A-Za-z\s]+)', text, re.IGNORECASE)
                destination = dest_match.group(2) if dest_match else None
                
                # Buyer
                buyer_el = await card.query_selector('.company-name, .member-name')
                buyer_name = await buyer_el.inner_text() if buyer_el else ""
                
                if product and product.strip():
                    lead = BuyerLead(
                        source_type="b2b_board",
                        source_url=source_url or f"{self.BASE_URL}/search?q={product}",
                        intent_level=calculate_intent_level(
                            has_quantity=bool(quantity),
                            has_destination=bool(destination)
                        ),
                        product=product.strip()[:200],
                        quantity=quantity,
                        destination_country=destination,
                        buyer_name=buyer_name.strip() if buyer_name else None,
                        scraped_at=datetime.now().isoformat()
                    )
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"Error extracting lead: {e}")
        
        return leads


async def scrape_all_b2b_boards(
    product_keywords: List[str],
    output_file: str = "b2b_leads.csv",
    headless: bool = True,
    pages_per_site: int = 3
) -> List[BuyerLead]:
    """
    Scrape all B2B boards for given product keywords.
    
    Args:
        product_keywords: List of products to search for (e.g., ["plywood", "ceramic tiles"])
        output_file: CSV file to save results
        headless: Run browser in headless mode
        pages_per_site: Number of pages to scrape per site
    
    Returns:
        List of BuyerLead objects
    """
    all_leads = []
    
    # Scrape TradeKey
    try:
        tk_scraper = TradeKeyScraper(product_keywords, headless)
        tk_leads = await tk_scraper.scrape(pages_per_site)
        all_leads.extend(tk_leads)
        logger.info(f"TradeKey: {len(tk_leads)} leads")
    except Exception as e:
        logger.error(f"TradeKey scraping failed: {e}")
    
    # Scrape go4WorldBusiness
    try:
        g4w_scraper = Go4WorldBusinessScraper(product_keywords, headless)
        g4w_leads = await g4w_scraper.scrape(pages_per_site)
        all_leads.extend(g4w_leads)
        logger.info(f"go4WorldBusiness: {len(g4w_leads)} leads")
    except Exception as e:
        logger.error(f"go4WorldBusiness scraping failed: {e}")
    
    # Scrape EC21
    try:
        ec21_scraper = EC21Scraper(product_keywords, headless)
        ec21_leads = await ec21_scraper.scrape(pages_per_site)
        all_leads.extend(ec21_leads)
        logger.info(f"EC21: {len(ec21_leads)} leads")
    except Exception as e:
        logger.error(f"EC21 scraping failed: {e}")
    
    # Deduplicate by URL
    seen_urls = set()
    unique_leads = []
    for lead in all_leads:
        if lead.source_url not in seen_urls:
            seen_urls.add(lead.source_url)
            unique_leads.append(lead)
    
    # Save to CSV
    if unique_leads:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=BuyerLead.csv_headers())
            writer.writeheader()
            for lead in unique_leads:
                writer.writerow(lead.to_csv_row())
        logger.info(f"Saved {len(unique_leads)} unique B2B leads to {output_file}")
    
    return unique_leads


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape B2B Trade Boards for buying leads")
    parser.add_argument(
        "--products",
        required=True,
        help="Comma-separated product keywords (e.g., 'plywood,ceramic tiles,steel')"
    )
    parser.add_argument("--output", default="b2b_leads.csv", help="Output CSV file")
    parser.add_argument("--pages", type=int, default=3, help="Pages to scrape per site")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    
    args = parser.parse_args()
    
    products = [p.strip() for p in args.products.split(',')]
    
    leads = asyncio.run(scrape_all_b2b_boards(
        product_keywords=products,
        output_file=args.output,
        headless=not args.no_headless,
        pages_per_site=args.pages
    ))
    
    print(f"\n{'='*50}")
    print(f"Total B2B Leads Found: {len(leads)}")
    print(f"Results saved to: {args.output}")
