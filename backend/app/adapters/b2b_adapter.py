"""
B2B Board Adapter

Scrapes B2B opportunity boards like TradeKey, go4WorldBusiness, EC21.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.adapters.base import LeadSignal, SourceAdapter, FetchError, ParseError

logger = logging.getLogger(__name__)


class B2BAdapter(SourceAdapter):
    """
    Adapter for B2B opportunity boards.
    
    Supports:
    - TradeKey
    - go4WorldBusiness
    - EC21
    
    Note: These sites have anti-scraping measures. Use with caution
    and respect robots.txt and ToS.
    """
    
    SOURCE_NAME = "b2b_boards"
    SOURCE_DISPLAY_NAME = "B2B Boards"
    SOURCE_TYPE = "b2b_board"
    RATE_LIMIT_PER_MINUTE = 30
    REQUEST_DELAY = 2.0
    
    # Site configurations
    SITE_CONFIGS = {
        "tradekey": {
            "base_url": "https://www.tradekey.com",
            "search_path": "/buying-leads/search.html",
            "selectors": {
                "item": ".buying-leads-item, .rfq-item",
                "title": "h3 a, .title a",
                "link": "h3 a, .title a",
                "buyer": ".buyer-name, .company-name",
                "quantity": ".quantity, .qty",
            }
        },
        "go4worldbusiness": {
            "base_url": "https://www.go4worldbusiness.com",
            "search_path": "/find.php",
            "selectors": {
                "item": ".postings, .buyer-leads-item",
                "title": "a[itemprop='name'], .title a",
                "link": "a[itemprop='name'], .title a",
                "buyer": ".company-name, .member-name",
            }
        },
        "ec21": {
            "base_url": "https://www.ec21.com",
            "search_path": "/buyOffer/search.do",
            "selectors": {
                "item": ".buyOffer-list, .buying-leads-item",
                "title": "a.subject, .title a",
                "link": "a.subject, .title a",
                "buyer": ".company-name, .member-name",
            }
        }
    }
    
    def __init__(self, site: str = "tradekey", use_playwright: bool = False):
        """
        Initialize B2B adapter.
        
        Args:
            site: Which B2B site to scrape
            use_playwright: Whether to use Playwright (for JS-heavy sites)
        """
        if site not in self.SITE_CONFIGS:
            raise ValueError(f"Unknown site: {site}. Available: {list(self.SITE_CONFIGS.keys())}")
        
        self.site = site
        self.site_config = self.SITE_CONFIGS[site]
        self.use_playwright = use_playwright
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate fetch configuration."""
        errors = []
        
        if "keywords" not in config:
            errors.append("keywords is required")
        
        if not isinstance(config.get("keywords"), list):
            errors.append("keywords must be a list")
        
        return (len(errors) == 0, errors)
    
    async def fetch(self, config: Dict[str, Any]) -> List[Any]:
        """
        Fetch buying leads from B2B board.
        
        Config expects:
        - keywords: List of product keywords
        - pages: Number of pages to scrape (default: 3)
        - country: Optional country filter
        """
        self.validate_config(config)
        
        keywords = config.get("keywords", [])
        pages = config.get("pages", 3)
        
        all_results = []
        
        for keyword in keywords:
            logger.info(f"Fetching {self.site} for keyword: {keyword}")
            
            try:
                if self.use_playwright:
                    results = await self._fetch_playwright(keyword, pages)
                else:
                    results = await self._fetch_http(keyword, pages)
                
                all_results.extend(results)
                
                # Rate limiting
                await asyncio.sleep(self.REQUEST_DELAY)
                
            except Exception as e:
                logger.error(f"Failed to fetch {self.site} for '{keyword}': {e}")
                raise FetchError(f"Failed to fetch from {self.site}: {e}")
        
        return all_results
    
    async def _fetch_http(self, keyword: str, pages: int) -> List[Dict]:
        """Fetch using HTTP requests (faster, but may be blocked)."""
        import httpx
        
        results = []
        base_url = self.site_config["base_url"]
        search_path = self.site_config["search_path"]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            for page in range(1, pages + 1):
                try:
                    # Build search URL (site-specific)
                    if self.site == "tradekey":
                        url = f"{base_url}{search_path}?query={keyword}&page={page}"
                    elif self.site == "go4worldbusiness":
                        url = f"{base_url}{search_path}?search={keyword}&buyers=1&page={page}"
                    elif self.site == "ec21":
                        url = f"{base_url}{search_path}?searchword={keyword}&page={page}"
                    else:
                        url = f"{base_url}{search_path}?q={keyword}&page={page}"
                    
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        results.append({
                            "html": response.text,
                            "url": url,
                            "page": page,
                            "keyword": keyword,
                        })
                    elif response.status_code == 429:
                        logger.warning(f"Rate limited on {self.site}")
                        break
                    else:
                        logger.warning(f"HTTP {response.status_code} from {self.site}")
                    
                    # Delay between pages
                    if page < pages:
                        await asyncio.sleep(self.REQUEST_DELAY)
                        
                except httpx.HTTPError as e:
                    logger.error(f"HTTP error on page {page}: {e}")
                    continue
        
        return results
    
    async def _fetch_playwright(self, keyword: str, pages: int) -> List[Dict]:
        """Fetch using Playwright (slower, but handles JS)."""
        from playwright.async_api import async_playwright
        from playwright_stealth.stealth import Stealth
        
        results = []
        stealth = Stealth()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1366, "height": 768},
            )
            page = await context.new_page()
            await stealth.apply_stealth_async(page)
            
            base_url = self.site_config["base_url"]
            
            for page_num in range(1, pages + 1):
                try:
                    # Navigate to search
                    if self.site == "tradekey":
                        url = f"{base_url}{self.site_config['search_path']}?query={keyword}"
                    else:
                        url = f"{base_url}{self.site_config['search_path']}?q={keyword}"
                    
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)  # Wait for JS to load
                    
                    # Get page content
                    html = await page.content()
                    
                    results.append({
                        "html": html,
                        "url": url,
                        "page": page_num,
                        "keyword": keyword,
                    })
                    
                    # Click next page
                    if page_num < pages:
                        next_btn = await page.query_selector("a.next, .pagination-next")
                        if next_btn:
                            await next_btn.click()
                            await page.wait_for_load_state("domcontentloaded")
                            await asyncio.sleep(2)
                        else:
                            break
                            
                except Exception as e:
                    logger.error(f"Playwright error on page {page_num}: {e}")
                    continue
            
            await browser.close()
        
        return results
    
    async def parse(self, raw_data: Any) -> List[LeadSignal]:
        """
        Parse raw HTML into LeadSignal objects.
        """
        from bs4 import BeautifulSoup
        
        if not isinstance(raw_data, list):
            raise ParseError("Expected list of raw data items")
        
        leads = []
        selectors = self.site_config["selectors"]
        
        for item in raw_data:
            if not isinstance(item, dict) or "html" not in item:
                continue
            
            try:
                soup = BeautifulSoup(item["html"], "html.parser")
                
                # Find all lead items
                lead_items = soup.select(selectors.get("item", ""))
                
                for lead_item in lead_items:
                    try:
                        # Extract title
                        title_el = lead_item.select_one(selectors.get("title", ""))
                        title = title_el.get_text(strip=True) if title_el else ""
                        
                        # Extract link
                        link_el = lead_item.select_one(selectors.get("link", ""))
                        source_url = link_el.get("href", "") if link_el else ""
                        
                        # Normalize URL
                        if source_url and not source_url.startswith("http"):
                            source_url = f"{self.site_config['base_url']}{source_url}"
                        
                        # Extract buyer name
                        buyer_el = lead_item.select_one(selectors.get("buyer", ""))
                        buyer_name = buyer_el.get_text(strip=True) if buyer_el else "Unknown Buyer"
                        
                        # Extract quantity
                        qty_el = lead_item.select_one(selectors.get("quantity", ""))
                        quantity = qty_el.get_text(strip=True) if qty_el else None
                        
                        # Create lead signal
                        lead = self.create_lead_signal(
                            buyer_name=buyer_name,
                            product_text=title,
                            source_url=source_url or item.get("url", ""),
                            quantity_text=quantity,
                            description=title,
                            raw_payload={
                                "site": self.site,
                                "keyword": item.get("keyword"),
                                "page": item.get("page"),
                            },
                            extraction_confidence=0.8 if source_url else 0.5,
                        )
                        
                        # Validate
                        is_valid, errors = lead.validate()
                        if is_valid:
                            leads.append(lead)
                        else:
                            logger.debug(f"Invalid lead: {errors}")
                            
                    except Exception as e:
                        logger.debug(f"Error parsing lead item: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error parsing page: {e}")
                continue
        
        logger.info(f"Parsed {len(leads)} leads from {self.site}")
        return leads
