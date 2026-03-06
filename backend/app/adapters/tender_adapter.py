"""
Tender Adapter

Scrapes tender/procurement portals like EU TED, SAM.gov, UN GM.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.adapters.base import LeadSignal, SourceAdapter, FetchError, ParseError

logger = logging.getLogger(__name__)


class TenderAdapter(SourceAdapter):
    """
    Adapter for tender/procurement portals.
    
    Supports:
    - EU TED (Tenders Electronic Daily)
    - SAM.gov (US)
    - UN Development Business
    
    Prefers official APIs where available.
    """
    
    SOURCE_NAME = "tenders"
    SOURCE_DISPLAY_NAME = "Tender Portals"
    SOURCE_TYPE = "tender"
    RATE_LIMIT_PER_MINUTE = 60
    REQUEST_DELAY = 1.0
    
    # Portal configurations
    PORTAL_CONFIGS = {
        "ted": {
            "name": "EU TED",
            "base_url": "https://ted.europa.eu",
            "api_url": "https://api.ted.europa.eu/api/v1",
            "requires_api_key": True,
        },
        "sam": {
            "name": "SAM.gov",
            "base_url": "https://sam.gov",
            "api_url": "https://api.sam.gov/prod/opportunities/v2",
            "requires_api_key": True,
        },
        "ungm": {
            "name": "UN Global Marketplace",
            "base_url": "https://www.ungm.org",
            "api_url": None,  # Web scraping only
            "requires_api_key": False,
        }
    }
    
    def __init__(
        self,
        portal: str = "ted",
        api_key: Optional[str] = None,
    ):
        """
        Initialize Tender adapter.
        
        Args:
            portal: Which portal to scrape (ted, sam, ungm)
            api_key: API key if required
        """
        if portal not in self.PORTAL_CONFIGS:
            raise ValueError(f"Unknown portal: {portal}")
        
        self.portal = portal
        self.portal_config = self.PORTAL_CONFIGS[portal]
        self.api_key = api_key
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate fetch configuration."""
        errors = []
        
        if "keywords" not in config:
            errors.append("keywords is required")
        
        if self.portal_config["requires_api_key"] and not self.api_key:
            errors.append(f"API key required for {self.portal}")
        
        return (len(errors) == 0, errors)
    
    async def fetch(self, config: Dict[str, Any]) -> List[Any]:
        """
        Fetch tenders from portal.
        
        Config expects:
        - keywords: List of product keywords
        - days_back: Number of days to search back (default: 30)
        - country: Optional country filter
        """
        self.validate_config(config)
        
        keywords = config.get("keywords", [])
        days_back = config.get("days_back", 30)
        
        all_results = []
        
        for keyword in keywords:
            logger.info(f"Fetching {self.portal} for keyword: {keyword}")
            
            try:
                if self.portal == "ted":
                    results = await self._fetch_ted(keyword, days_back)
                elif self.portal == "sam":
                    results = await self._fetch_sam(keyword, days_back)
                elif self.portal == "ungm":
                    results = await self._fetch_ungm(keyword, days_back)
                else:
                    results = []
                
                all_results.extend(results)
                
                # Rate limiting
                await asyncio.sleep(self.REQUEST_DELAY)
                
            except Exception as e:
                logger.error(f"Failed to fetch {self.portal} for '{keyword}': {e}")
        
        return all_results
    
    async def _fetch_ted(self, keyword: str, days_back: int) -> List[Dict]:
        """Fetch from EU TED API."""
        if not self.api_key:
            # Fallback: return search URL for manual review
            logger.warning("TED: No API key, returning search URL only")
            return [{
                "type": "search_url",
                "url": f"https://ted.europa.eu/search?q={keyword}",
                "keyword": keyword,
                "portal": "ted",
            }]
        
        # Calculate date range
        from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        
        params = {
            "from": from_date,
            "pageSize": 50,
            "language": "ENG",
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.portal_config['api_url']}/notices",
                    headers=headers,
                    params=params,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return [{
                        "type": "notice",
                        "data": data,
                        "keyword": keyword,
                        "portal": "ted",
                    }]
                else:
                    logger.warning(f"TED API returned {response.status_code}")
                    return []
                    
            except httpx.HTTPError as e:
                logger.error(f"TED API error: {e}")
                return []
    
    async def _fetch_sam(self, keyword: str, days_back: int) -> List[Dict]:
        """Fetch from SAM.gov API."""
        if not self.api_key:
            logger.warning("SAM.gov: No API key, returning search URL only")
            return [{
                "type": "search_url",
                "url": f"https://sam.gov/search/?keywords={keyword}",
                "keyword": keyword,
                "portal": "sam",
            }]
        
        params = {
            "api_key": self.api_key,
            "keywords": keyword,
            "sort": "-modifiedDate",
            "limit": 50,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.portal_config['api_url']}/search",
                    params=params,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return [{
                        "type": "opportunity",
                        "data": data,
                        "keyword": keyword,
                        "portal": "sam",
                    }]
                else:
                    logger.warning(f"SAM.gov API returned {response.status_code}")
                    return []
                    
            except httpx.HTTPError as e:
                logger.error(f"SAM.gov API error: {e}")
                return []
    
    async def _fetch_ungm(self, keyword: str, days_back: int) -> List[Dict]:
        """Fetch from UN GM (web scraping)."""
        # UN GM requires login for full access
        # Return search URL for now
        return [{
            "type": "search_url",
            "url": f"https://www.ungm.org/Procurement/Opportunities?q={keyword}",
            "keyword": keyword,
            "portal": "ungm",
        }]
    
    async def parse(self, raw_data: Any) -> List[LeadSignal]:
        """Parse raw tender data into LeadSignal objects."""
        if not isinstance(raw_data, list):
            raise ParseError("Expected list of raw data items")
        
        leads = []
        
        for item in raw_data:
            item_type = item.get("type", "")
            
            if item_type == "search_url":
                # Create placeholder lead for search URL
                lead = self.create_lead_signal(
                    buyer_name="Government Entity",
                    product_text=item.get("keyword", ""),
                    source_url=item.get("url", ""),
                    description=f"Search {self.portal} for: {item.get('keyword')}",
                    raw_payload=item,
                    extraction_confidence=0.3,
                )
                leads.append(lead)
            
            elif item_type == "notice" and self.portal == "ted":
                # Parse TED API response
                ted_leads = self._parse_ted_notice(item)
                leads.extend(ted_leads)
            
            elif item_type == "opportunity" and self.portal == "sam":
                # Parse SAM.gov API response
                sam_leads = self._parse_sam_opportunity(item)
                leads.extend(sam_leads)
        
        logger.info(f"Parsed {len(leads)} tender leads from {self.portal}")
        return leads
    
    def _parse_ted_notice(self, item: Dict) -> List[LeadSignal]:
        """Parse TED notice data."""
        leads = []
        data = item.get("data", {})
        notices = data.get("notices", [])
        
        for notice in notices[:20]:  # Limit to 20
            try:
                title = notice.get("title", {}).get("EN", ["No title"])[0]
                notice_id = notice.get("id", "")
                source_url = f"https://ted.europa.eu/notice/{notice_id}"
                
                # Get country
                countries = notice.get("country", [])
                location = countries[0] if countries else None
                
                # Get value
                value = notice.get("estimated_value", {})
                budget = f"{value.get('amount', '')} {value.get('currency', 'EUR')}" if value.get("amount") else None
                
                # Get deadline
                deadline = notice.get("dates", {}).get("tendering_deadline", "")
                
                lead = self.create_lead_signal(
                    buyer_name="EU Government Entity",
                    product_text=title,
                    source_url=source_url,
                    budget_text=budget,
                    deadline_text=deadline[:10] if deadline else None,
                    location_text=location,
                    description=title,
                    raw_payload=notice,
                    extraction_confidence=0.9,
                )
                leads.append(lead)
                
            except Exception as e:
                logger.debug(f"Error parsing TED notice: {e}")
        
        return leads
    
    def _parse_sam_opportunity(self, item: Dict) -> List[LeadSignal]:
        """Parse SAM.gov opportunity data."""
        leads = []
        data = item.get("data", {})
        opportunities = data.get("opportunities", [])
        
        for opp in opportunities[:20]:
            try:
                title = opp.get("title", "No title")
                opp_id = opp.get("id", "")
                source_url = f"https://sam.gov/opp/{opp_id}"
                
                # Get agency
                agency = opp.get("agency", "")
                office = opp.get("office", "")
                buyer = f"{agency} - {office}" if office else agency
                
                # Get value
                value = opp.get("value", "")
                budget = f"${value:,}" if value else None
                
                # Get dates
                response_date = opp.get("responseDate", "")
                
                lead = self.create_lead_signal(
                    buyer_name=buyer or "US Government",
                    product_text=title,
                    source_url=source_url,
                    budget_text=budget,
                    deadline_text=response_date[:10] if response_date else None,
                    description=opp.get("description", title),
                    raw_payload=opp,
                    extraction_confidence=0.9,
                )
                leads.append(lead)
                
            except Exception as e:
                logger.debug(f"Error parsing SAM opportunity: {e}")
        
        return leads


# Import asyncio for the async functions
import asyncio
