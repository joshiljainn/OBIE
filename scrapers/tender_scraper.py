"""
Tender Portal Scrapers
Scrapes government and corporate tenders - HIGHEST INTENT leads

Sources:
- EU TED (Tenders Electronic Daily): https://ted.europa.eu
- UAE eProcurement: https://www.eprocure.gov.ae
- UN Development Business: https://www.ungm.org

These have defined budgets, deadlines, and legal procurement requirements.
"""
import asyncio
import csv
import logging
import re
import os
import requests
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth

from models import BuyerLead, calculate_intent_level

stealth = Stealth()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TEDScraper:
    """
    EU TED (Tenders Electronic Daily) scraper
    Uses the official ODS API: https://op.europa.eu/en/web/op-data-portal
    
    This is more reliable than web scraping.
    """
    
    BASE_URL = "https://ted.europa.eu"
    # Official ODS API endpoint for TED notices
    API_URL = "https://op.europa.eu/webapis/rdf/sparql"
    
    def __init__(self, product_keywords: List[str], headless: bool = True):
        self.product_keywords = product_keywords
        self.headless = headless
        self.leads = []
    
    def scrape(self, days_back: int = 30) -> List[BuyerLead]:
        """
        Scrape TED using the official API.
        
        Note: This uses synchronous requests since the API is REST-based.
        """
        for keyword in self.product_keywords:
            logger.info(f"Searching EU TED for: {keyword}")
            self._search_keyword(keyword, days_back)
        
        return self.leads
    
    def _search_keyword(self, keyword: str, days_back: int):
        """Search TED API for a keyword"""
        # TED/OP API requires SPARQL queries, but we can use the simpler REST API
        # Alternative: Use the web search URL and parse results
        
        # For now, use a simpler approach - search the public web interface
        # and parse the HTML results
        import requests
        from bs4 import BeautifulSoup
        
        search_url = f"{self.BASE_URL}/TED/search/{keyword}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml"
        }
        
        try:
            response = requests.get(search_url, headers=headers, timeout=30)
            if response.status_code == 200:
                self._parse_search_results(response.text, keyword)
            else:
                logger.warning(f"TED API returned {response.status_code}")
        except Exception as e:
            logger.warning(f"TED search failed for '{keyword}': {e}")
    
    def _parse_search_results(self, html: str, keyword: str):
        """Parse TED search results HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for notice items
        notices = soup.find_all('div', class_='notice-item') or \
                  soup.find_all('article') or \
                  soup.find_all('li', class_='result')
        
        for notice in notices[:20]:  # Limit to first 20
            try:
                # Title
                title_el = notice.find(['h2', 'h3', 'a'], class_=lambda x: x and ('title' in x.lower() or 'name' in x.lower()))
                title = title_el.get_text(strip=True) if title_el else ""
                
                # URL
                link = notice.find('a', href=True)
                source_url = link['href'] if link else ""
                if source_url and source_url.startswith('/'):
                    source_url = f"{self.BASE_URL}{source_url}"
                
                # Country/Location
                country_el = notice.find(['span', 'div'], class_=lambda x: x and ('country' in x.lower() or 'location' in x.lower()))
                location = country_el.get_text(strip=True) if country_el else ""
                
                # Value
                value_el = notice.find(['span', 'div'], class_=lambda x: x and ('value' in x.lower() or 'amount' in x.lower()))
                budget = value_el.get_text(strip=True) if value_el else ""
                
                # Deadline
                deadline_el = notice.find(['span', 'div'], class_=lambda x: x and ('deadline' in x.lower() or 'date' in x.lower()))
                deadline = deadline_el.get_text(strip=True) if deadline_el else ""
                
                if title:
                    # Parse deadline for days remaining
                    days_to_deadline = None
                    if deadline:
                        deadline_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', deadline)
                        if deadline_match:
                            try:
                                deadline_date = datetime.strptime(deadline_match.group(1), '%d/%m/%Y')
                                days_to_deadline = (deadline_date - datetime.now()).days
                            except:
                                pass
                    
                    lead = BuyerLead(
                        source_type="tender",
                        source_url=source_url or f"{self.BASE_URL}/search/{keyword}",
                        intent_level=calculate_intent_level(
                            has_budget=bool(budget),
                            has_deadline=bool(deadline),
                            is_tender=True,
                            days_to_deadline=days_to_deadline
                        ),
                        product=title[:200],
                        destination_country=self._extract_country(location),
                        budget=budget if budget else None,
                        deadline=deadline if deadline else None,
                        buyer_name="Government Entity",
                        buyer_type="Government",
                        description=title,
                        scraped_at=datetime.now().isoformat()
                    )
                    self.leads.append(lead)
                    
            except Exception as e:
                logger.debug(f"Error parsing notice: {e}")
        
        logger.info(f"Extracted {len(self.leads)} tenders from TED")
    
    def _extract_country(self, text: str) -> Optional[str]:
        """Extract country from location text"""
        if not text:
            return None
        
        eu_countries = {
            'Austria': 'Austria', 'Belgium': 'Belgium', 'Bulgaria': 'Bulgaria',
            'Croatia': 'Croatia', 'Cyprus': 'Cyprus', 'Czech': 'Czech Republic',
            'Denmark': 'Denmark', 'Estonia': 'Estonia', 'Finland': 'Finland',
            'France': 'France', 'Germany': 'Germany', 'Greece': 'Greece',
            'Hungary': 'Hungary', 'Ireland': 'Ireland', 'Italy': 'Italy',
            'Latvia': 'Latvia', 'Lithuania': 'Lithuania', 'Luxembourg': 'Luxembourg',
            'Malta': 'Malta', 'Netherlands': 'Netherlands', 'Poland': 'Poland',
            'Portugal': 'Portugal', 'Romania': 'Romania', 'Slovakia': 'Slovakia',
            'Slovenia': 'Slovenia', 'Spain': 'Spain', 'Sweden': 'Sweden'
        }
        
        for country in eu_countries:
            if country.lower() in text.lower():
                return eu_countries[country]
        return None


class UAEProcurementScraper:
    """
    UAE Government eProcurement Portal scraper
    https://www.eprocure.gov.ae
    
    This is the federal procurement portal for UAE government entities.
    High-value tenders for construction, supplies, and services.
    """
    
    BASE_URL = "https://www.eprocure.gov.ae"
    
    def __init__(self, product_keywords: List[str], headless: bool = True):
        self.product_keywords = product_keywords
        self.headless = headless
        self.leads = []
    
    async def scrape(self, days_back: int = 30) -> List[BuyerLead]:
        """Scrape UAE eProcurement for tenders"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={'width': 1366, 'height': 768}
            )
            page = await context.new_page()
            await stealth.apply_stealth_async(page)
            
            for keyword in self.product_keywords:
                logger.info(f"Scraping UAE eProcurement for: {keyword}")
                await self._scrape_keyword(page, keyword)
                await asyncio.sleep(3)
            
            await browser.close()
        
        return self.leads
    
    async def _scrape_keyword(self, page, keyword: str):
        """Scrape for a single keyword"""
        # UAE eProcurement search
        search_url = f"{self.BASE_URL}/en/tenders/search?q={keyword}"
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
        except Exception as e:
            logger.warning(f"Failed to load UAE eProcurement: {e}")
            return
        
        # Extract tenders
        tender_cards = await page.query_selector_all(
            '.tender-item, .notice-card, .tender-row, tr.tender'
        )
        
        for card in tender_cards:
            try:
                # Title
                title_el = await card.query_selector('h3, .title, a.tender-title')
                title = await title_el.inner_text() if title_el else ""
                
                # URL
                link_el = await card.query_selector('a[href*="/tender/"]')
                source_url = await link_el.get_attribute('href') if link_el else ""
                if source_url and source_url.startswith('/'):
                    source_url = f"{self.BASE_URL}{source_url}"
                
                # Entity/Buyer
                entity_el = await card.query_selector('.entity, .department, .organization')
                buyer_name = await entity_el.inner_text() if entity_el else ""
                
                # Location (Emirate)
                loc_el = await card.query_selector('.location, .emirate')
                location = await loc_el.inner_text() if loc_el else ""
                
                # Value
                value_el = await card.query_selector('.value, .budget, .amount')
                budget = await value_el.inner_text() if value_el else ""
                
                # Deadline
                deadline_el = await card.query_selector('.deadline, .closing-date, .end-date')
                deadline = await deadline_el.inner_text() if deadline_el else ""
                
                # Description
                desc_el = await card.query_selector('.description, .summary')
                description = await desc_el.inner_text() if desc_el else ""
                
                if title and title.strip():
                    # Parse deadline
                    days_to_deadline = None
                    if deadline:
                        deadline_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', deadline)
                        if deadline_match:
                            try:
                                deadline_date = datetime.strptime(deadline_match.group(1), '%d/%m/%Y')
                                days_to_deadline = (deadline_date - datetime.now()).days
                            except:
                                pass
                    
                    lead = BuyerLead(
                        source_type="tender",
                        source_url=source_url or f"{self.BASE_URL}/tenders",
                        intent_level=calculate_intent_level(
                            has_budget=bool(budget),
                            has_deadline=bool(deadline),
                            is_tender=True,
                            days_to_deadline=days_to_deadline
                        ),
                        product=title[:200],
                        destination_country="UAE",
                        budget=budget.strip() if budget else None,
                        deadline=deadline.strip() if deadline else None,
                        buyer_name=buyer_name.strip() if buyer_name else "UAE Government Entity",
                        buyer_type="Government",
                        description=description.strip() if description else None,
                        scraped_at=datetime.now().isoformat()
                    )
                    self.leads.append(lead)
                    
            except Exception as e:
                logger.debug(f"Error extracting tender: {e}")
        
        logger.info(f"Extracted {len(self.leads)} tenders from UAE eProcurement")


class UNDevelopmentBusinessScraper:
    """
    UN Development Business scraper
    https://www.ungm.org
    
    UN procurement notices and development bank tenders.
    Very high value, international development projects.
    """
    
    BASE_URL = "https://www.ungm.org"
    
    def __init__(self, product_keywords: List[str], headless: bool = True):
        self.product_keywords = product_keywords
        self.headless = headless
        self.leads = []
    
    async def scrape(self, days_back: int = 30) -> List[BuyerLead]:
        """Scrape UN GM for procurement opportunities"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={'width': 1366, 'height': 768}
            )
            page = await context.new_page()
            await stealth.apply_stealth_async(page)
            
            for keyword in self.product_keywords:
                logger.info(f"Scraping UN Development Business for: {keyword}")
                await self._scrape_keyword(page, keyword)
                await asyncio.sleep(3)
            
            await browser.close()
        
        return self.leads
    
    async def _scrape_keyword(self, page, keyword: str):
        """Scrape for a single keyword"""
        search_url = f"{self.BASE_URL}/Procurement/Opportunities?q={keyword}"
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
        except Exception as e:
            logger.warning(f"Failed to load UN Development Business: {e}")
            return
        
        # Extract opportunities
        opp_cards = await page.query_selector_all(
            '.opportunity-item, .procurement-notice, .tender-row'
        )
        
        for card in opp_cards:
            try:
                # Title
                title_el = await card.query_selector('h3, .title, a.opportunity-title')
                title = await title_el.inner_text() if title_el else ""
                
                # URL
                link_el = await card.query_selector('a[href*="/Opportunity/"]')
                source_url = await link_el.get_attribute('href') if link_el else ""
                
                # Agency
                agency_el = await card.query_selector('.agency, .organization, .un-body')
                buyer_name = await agency_el.inner_text() if agency_el else ""
                
                # Location
                loc_el = await card.query_selector('.location, .country')
                location = await loc_el.inner_text() if loc_el else ""
                
                # Deadline
                deadline_el = await card.query_selector('.deadline, .closing-date')
                deadline = await deadline_el.inner_text() if deadline_el else ""
                
                # Reference number
                ref_el = await card.query_selector('.reference, .ref-number')
                ref_number = await ref_el.inner_text() if ref_el else ""
                
                if title and title.strip():
                    # Parse deadline
                    days_to_deadline = None
                    if deadline:
                        deadline_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', deadline)
                        if deadline_match:
                            try:
                                deadline_str = deadline_match.group(1)
                                deadline_date = datetime.strptime(deadline_str, '%d %B %Y')
                                days_to_deadline = (deadline_date - datetime.now()).days
                            except:
                                pass
                    
                    lead = BuyerLead(
                        source_type="tender",
                        source_url=source_url or f"{self.BASE_URL}/Procurement",
                        intent_level=calculate_intent_level(
                            has_budget=True,  # UN tenders usually have budgets
                            has_deadline=bool(deadline),
                            is_tender=True,
                            days_to_deadline=days_to_deadline
                        ),
                        product=title[:200],
                        destination_country=self._extract_country(location),
                        budget=None,  # Usually requires login
                        deadline=deadline.strip() if deadline else None,
                        buyer_name=buyer_name.strip() if buyer_name else "UN Agency",
                        buyer_type="International Organization",
                        description=f"Ref: {ref_number}" if ref_number else None,
                        scraped_at=datetime.now().isoformat()
                    )
                    self.leads.append(lead)
                    
            except Exception as e:
                logger.debug(f"Error extracting opportunity: {e}")
        
        logger.info(f"Extracted {len(self.leads)} opportunities from UN Development Business")
    
    def _extract_country(self, text: str) -> Optional[str]:
        if not text:
            return None
        # Common developing countries where UN operates
        countries = [
            'Afghanistan', 'Bangladesh', 'Ethiopia', 'Kenya', 'Nigeria',
            'Pakistan', 'Philippines', 'Tanzania', 'Uganda', 'Yemen',
            'Jordan', 'Lebanon', 'Iraq', 'Syria', 'Myanmar', 'Nepal'
        ]
        for country in countries:
            if country.lower() in text.lower():
                return country
        return None


async def scrape_tender_portals(
    product_keywords: List[str],
    output_file: str = "tender_leads.csv",
    headless: bool = True,
    days_back: int = 30,
    portals: List[str] = None
) -> List[BuyerLead]:
    """
    Scrape multiple tender portals for high-value opportunities.
    
    Args:
        product_keywords: Products/services to search for
        output_file: CSV file to save results
        headless: Run browser in headless mode
        days_back: Only fetch tenders from last N days
        portals: List of portals to scrape (default: all)
    
    Returns:
        List of BuyerLead objects
    """
    if portals is None:
        portals = ['ted', 'uae', 'un']
    
    all_leads = []
    
    # EU TED (synchronous - uses requests)
    if 'ted' in portals:
        try:
            ted_scraper = TEDScraper(product_keywords, headless)
            ted_leads = ted_scraper.scrape(days_back)  # No await - it's sync now
            all_leads.extend(ted_leads)
            logger.info(f"EU TED: {len(ted_leads)} tenders")
        except Exception as e:
            logger.error(f"EU TED scraping failed: {e}")
    
    # UAE eProcurement
    if 'uae' in portals:
        try:
            uae_scraper = UAEProcurementScraper(product_keywords, headless)
            uae_leads = await uae_scraper.scrape(days_back)
            all_leads.extend(uae_leads)
            logger.info(f"UAE eProcurement: {len(uae_leads)} tenders")
        except Exception as e:
            logger.error(f"UAE eProcurement scraping failed: {e}")
    
    # UN Development Business
    if 'un' in portals:
        try:
            un_scraper = UNDevelopmentBusinessScraper(product_keywords, headless)
            un_leads = await un_scraper.scrape(days_back)
            all_leads.extend(un_leads)
            logger.info(f"UN Development Business: {len(un_leads)} opportunities")
        except Exception as e:
            logger.error(f"UN Development Business scraping failed: {e}")
    
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
        logger.info(f"Saved {len(unique_leads)} unique tender leads to {output_file}")
    
    return unique_leads


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape Tender Portals for high-value opportunities")
    parser.add_argument(
        "--products",
        required=True,
        help="Comma-separated product keywords"
    )
    parser.add_argument("--output", default="tender_leads.csv", help="Output CSV file")
    parser.add_argument("--days", type=int, default=30, help="Days back to search")
    parser.add_argument("--portals", default="all", help="Comma-separated: ted,uae,un or 'all'")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    
    args = parser.parse_args()
    
    products = [p.strip() for p in args.products.split(',')]
    portal_list = args.portals.split(',') if args.portals != 'all' else ['ted', 'uae', 'un']
    
    leads = asyncio.run(scrape_tender_portals(
        product_keywords=products,
        output_file=args.output,
        headless=not args.no_headless,
        days_back=args.days,
        portals=portal_list
    ))
    
    print(f"\n{'='*50}")
    print(f"Total Tender Leads Found: {len(leads)}")
    print(f"Results saved to: {args.output}")
