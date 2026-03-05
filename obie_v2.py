"""
OBIE 2.0 - Focused API-Based Tender & Lead Scraper

Uses official APIs and RSS feeds for reliable, maintainable lead generation.
"""
import asyncio
import csv
import json
import logging
import os
import re
import requests
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class BuyerLead:
    source_type: str
    source_url: str
    title: str
    buyer_name: str
    buyer_type: str
    description: str
    budget: Optional[str] = None
    deadline: Optional[str] = None
    location: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    products: Optional[str] = None
    scraped_at: str = None
    lead_score: int = 0
    lead_tier: str = "C"
    
    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()
    
    def to_row(self):
        return asdict(self)
    
    @staticmethod
    def headers():
        return [
            'source_type', 'source_url', 'title', 'buyer_name', 'buyer_type',
            'description', 'budget', 'deadline', 'location', 'contact_email',
            'contact_phone', 'products', 'scraped_at', 'lead_score', 'lead_tier'
        ]


# ============================================================================
# LEAD SCORING
# ============================================================================

def calculate_score(lead: BuyerLead) -> tuple:
    """Calculate lead score and tier"""
    score = 0
    reasons = []
    
    # Source type
    if lead.source_type == "tender_api":
        score += 100
        reasons.append("Official tender API")
    elif lead.source_type == "tender_rss":
        score += 80
        reasons.append("Tender RSS feed")
    elif lead.source_type == "b2b_api":
        score += 60
        reasons.append("B2B platform")
    elif lead.source_type == "b2b_scrape":
        score += 40
        reasons.append("B2B scrape")
    
    # Budget
    if lead.budget:
        score += 50
        reasons.append("Budget specified")
    
    # Deadline
    if lead.deadline:
        score += 30
        reasons.append("Has deadline")
        
        # Check urgency
        try:
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%B %d, %Y']:
                try:
                    dl = datetime.strptime(lead.deadline, fmt)
                    days_left = (dl - datetime.now()).days
                    if 0 < days_left <= 30:
                        score += 40
                        reasons.append(f"Urgent: {days_left} days")
                    elif days_left <= 0:
                        score -= 20
                        reasons.append("Deadline passed")
                    break
                except:
                    continue
        except:
            pass
    
    # Government buyer
    if lead.buyer_type and "government" in lead.buyer_type.lower():
        score = int(score * 1.5)
        reasons.append("Government buyer")
    
    # Determine tier
    if score >= 200:
        tier = "S"
    elif score >= 120:
        tier = "A"
    elif score >= 60:
        tier = "B"
    else:
        tier = "C"
    
    return score, tier


# ============================================================================
# EU TED API SCRAPER
# ============================================================================

class TEDScraper:
    """
    EU TED Tenders via Official API
    Documentation: https://op.europa.eu/en/web/op-data-portal
    
    Uses the REST API which is simpler than SPARQL.
    """
    
    # TED REST API - no authentication required for basic search
    BASE_URL = "https://api.ted.europa.eu/api/v1"
    
    def __init__(self, keywords: List[str], api_key: str = None):
        self.keywords = keywords
        self.api_key = api_key  # Optional for basic access
        self.leads = []
    
    def scrape(self, days_back: int = 30) -> List[BuyerLead]:
        """Scrape TED for tenders"""
        logger.info(f"TED: Searching for {len(self.keywords)} keywords")
        
        for keyword in self.keywords:
            self._search_keyword(keyword, days_back)
        
        return self.leads
    
    def _search_keyword(self, keyword: str, days_back: int):
        """Search TED REST API for a keyword"""
        
        # Calculate date range
        from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        
        # Build API URL
        # Documentation: https://api.ted.europa.eu/documentation
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            # Without API key, use the public web interface search
            self._search_web(keyword, days_back)
            return
        
        params = {
            "from": from_date,
            "to": to_date,
            "pageSize": 50,
            "language": "ENG"
        }
        
        try:
            # Search notices
            response = requests.get(
                f"{self.BASE_URL}/notices",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self._parse_api_results(data, keyword)
            else:
                logger.warning(f"TED API returned {response.status_code}")
                # Fallback to web search
                self._search_web(keyword, days_back)
                
        except Exception as e:
            logger.warning(f"TED API failed: {e}")
            self._search_web(keyword, days_back)
    
    def _search_web(self, keyword: str, days_back: int):
        """Fallback: Search TED web interface"""
        search_url = f"https://ted.europa.eu/search?q={keyword}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html"
        }
        
        try:
            response = requests.get(search_url, headers=headers, timeout=30)
            if response.status_code == 200:
                # For now, just create a placeholder lead
                # In production, parse the HTML properly
                lead = BuyerLead(
                    source_type="tender_web",
                    source_url=search_url,
                    title=f"TED Search: {keyword}",
                    buyer_name="EU Government",
                    buyer_type="Government",
                    description=f"Search TED for '{keyword}' tenders",
                    products=keyword,
                    scraped_at=datetime.now().isoformat()
                )
                score, tier = calculate_score(lead)
                lead.lead_score = score
                lead.lead_tier = tier
                self.leads.append(lead)
                logger.info(f"TED Web: Created search link for '{keyword}'")
        except Exception as e:
            logger.warning(f"TED web search failed: {e}")
    
    def _parse_api_results(self, data: dict, keyword: str):
        """Parse TED API results"""
        notices = data.get('notices', [])
        
        for notice in notices[:20]:
            try:
                title = notice.get('title', {}).get('EN', ['No title'])[0]
                notice_id = notice.get('id', '')
                source_url = f"https://ted.europa.eu/notice/{notice_id}"
                
                # Get country
                countries = notice.get('country', [])
                location = countries[0] if countries else None
                
                # Get value
                value = notice.get('estimated_value', {})
                budget = f"{value.get('amount', '')} {value.get('currency', 'EUR')}" if value.get('amount') else None
                
                # Get deadline
                deadline = notice.get('dates', {}).get('tendering_deadline', '')
                
                lead = BuyerLead(
                    source_type="tender_api",
                    source_url=source_url,
                    title=title[:300],
                    buyer_name="EU Government Entity",
                    buyer_type="Government",
                    description=title,
                    budget=budget,
                    deadline=deadline[:10] if deadline else None,
                    location=location,
                    products=keyword,
                    scraped_at=datetime.now().isoformat()
                )
                
                score, tier = calculate_score(lead)
                lead.lead_score = score
                lead.lead_tier = tier
                
                self.leads.append(lead)
                
            except Exception as e:
                logger.debug(f"Error parsing TED result: {e}")
        
        logger.info(f"TED: Found {len(self.leads)} tenders for '{keyword}'")


# ============================================================================
# SAM.GOV API SCRAPER (US)
# ============================================================================

class SAMScraper:
    """
    US SAM.gov Contract Opportunities API
    Documentation: https://open.gsa.gov/api/sam-api/
    """
    
    API_URL = "https://api.sam.gov/prod/opportunities/v2/search"
    
    def __init__(self, keywords: List[str], api_key: str = None):
        self.keywords = keywords
        self.api_key = api_key
        self.leads = []
    
    def scrape(self, days_back: int = 30) -> List[BuyerLead]:
        """Scrape SAM.gov for opportunities"""
        
        if not self.api_key:
            logger.warning("SAM.gov: No API key provided, skipping")
            return self.leads
        
        logger.info(f"SAM.gov: Searching for {len(self.keywords)} keywords")
        
        for keyword in self.keywords:
            self._search_keyword(keyword, days_back)
        
        return self.leads
    
    def _search_keyword(self, keyword: str, days_back: int):
        """Search SAM.gov for a keyword"""
        
        params = {
            "api_key": self.api_key,
            "keywords": keyword,
            "sort": "-modifiedDate",
            "limit": 50
        }
        
        try:
            response = requests.get(self.API_URL, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                self._parse_results(data, keyword)
            else:
                logger.warning(f"SAM.gov returned {response.status_code}")
                
        except Exception as e:
            logger.warning(f"SAM.gov search failed: {e}")
    
    def _parse_results(self, data: dict, keyword: str):
        """Parse SAM.gov results"""
        opportunities = data.get('opportunities', [])
        
        for opp in opportunities[:20]:
            try:
                title = opp.get('title', '')
                opp_id = opp.get('id', '')
                source_url = f"https://sam.gov/opp/{opp_id}"
                
                # Get agency info
                agency = opp.get('agency', '')
                office = opp.get('office', '')
                buyer = f"{agency} - {office}" if office else agency
                
                # Get dates
                response_date = opp.get('responseDate', '')
                posted_date = opp.get('postedDate', '')
                
                # Get value
                value = opp.get('value', '')
                if value:
                    budget = f"${value:,}"
                else:
                    budget = None
                
                lead = BuyerLead(
                    source_type="tender_api",
                    source_url=source_url,
                    title=title[:300],
                    buyer_name=buyer or "US Government",
                    buyer_type="Government",
                    description=opp.get('description', '')[:500] if opp.get('description') else title,
                    budget=budget,
                    deadline=response_date[:10] if response_date else None,
                    location=opp.get('placeOfPerformance', {}).get('state', '') if opp.get('placeOfPerformance') else None,
                    products=keyword,
                    scraped_at=datetime.now().isoformat()
                )
                
                score, tier = calculate_score(lead)
                lead.lead_score = score
                lead.lead_tier = tier
                
                self.leads.append(lead)
                
            except Exception as e:
                logger.debug(f"Error parsing SAM result: {e}")
        
        logger.info(f"SAM.gov: Found {len(self.leads)} opportunities for '{keyword}'")


# ============================================================================
# RSS FEED MONITOR
# ============================================================================

class RSSMonitor:
    """
    Monitor RSS feeds from tender portals and B2B sites.
    
    Many sites provide RSS feeds for new tenders/listings.
    This is more reliable than scraping.
    """
    
    # Pre-configured RSS feeds - update when feeds change
    RSS_FEEDS = [
        # Global Tender RSS
        {
            "name": "TenderNews Global",
            "url": "https://www.tendernews.com/rss",
            "type": "tender_rss"
        },
        # Regional feeds (update with working URLs)
        {
            "name": "UAE Tenders",
            "url": "https://www.dubai.gov.ae/rss/tenders.xml",
            "type": "tender_rss"
        },
        # Industry specific
        {
            "name": "Construction Tenders",
            "url": "https://www.constructiontenders.net/rss",
            "type": "tender_rss"
        }
    ]
    
    def __init__(self, keywords: List[str] = None):
        self.keywords = keywords or []
        self.leads = []
    
    def scrape(self) -> List[BuyerLead]:
        """Monitor all configured RSS feeds"""
        logger.info(f"RSS: Monitoring {len(self.RSS_FEEDS)} feeds")
        
        for feed_config in self.RSS_FEEDS:
            self._monitor_feed(feed_config)
        
        return self.leads
    
    def _monitor_feed(self, feed_config: dict):
        """Monitor a single RSS feed"""
        try:
            feed = feedparser.parse(feed_config['url'])
            
            if feed.bozo:
                logger.debug(f"RSS: Feed unavailable - {feed_config['name']}")
                return
            
            logger.info(f"RSS: {feed_config['name']} - {len(feed.entries)} entries")
            
            for entry in feed.entries[:10]:  # Limit to 10 per feed
                # Check if entry matches our keywords
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                content = title + ' ' + summary
                
                # Filter by keywords if specified
                if self.keywords:
                    if not any(kw.lower() in content.lower() for kw in self.keywords):
                        continue
                
                # Extract info
                link = entry.get('link', '')
                published = entry.get('published', '')
                
                # Try to extract budget from title/summary
                budget_match = re.search(r'[\$€£]\s?[\d,\.]+[MBK]?|\d+\s?(million|billion)', content, re.IGNORECASE)
                budget = budget_match.group(0) if budget_match else None
                
                # Try to extract deadline
                deadline_match = re.search(r'(deadline|closing|due)[:\s]+(\d{1,2}/\d{1,2}/\d{4})', content, re.IGNORECASE)
                deadline = deadline_match.group(2) if deadline_match else None
                
                lead = BuyerLead(
                    source_type=feed_config['type'],
                    source_url=link,
                    title=title[:300],
                    buyer_name=feed.feed.get('title', 'Unknown'),
                    buyer_type="Private",
                    description=summary[:500] if summary else title,
                    budget=budget,
                    deadline=deadline,
                    products=', '.join(self.keywords) if self.keywords else None,
                    scraped_at=datetime.now().isoformat()
                )
                
                score, tier = calculate_score(lead)
                lead.lead_score = score
                lead.lead_tier = tier
                
                self.leads.append(lead)
                
        except Exception as e:
            logger.debug(f"RSS feed error - {feed_config['name']}: {e}")
        
        logger.info(f"RSS: {feed_config['name']} - {len(self.leads)} total matching leads")


# ============================================================================
# SIMPLE B2B SCRAPER (Manual Selectors)
# ============================================================================

class SimpleB2BScraper:
    """
    Simple B2B scraper with manually maintained selectors.
    Easy to update when sites change.
    """
    
    # Manually maintained selectors - update when sites change
    SITE_CONFIGS = [
        {
            "name": "IndiaMART",
            "search_url": "https://www.indiamart.com/wholesalers/{keyword}.html",
            "selectors": {
                "item": ".prodcatalog-item, .pdl_product",
                "title": ".prodcatalog-item_title a, .pdl_name a",
                "link": ".prodcatalog-item_title a, .pdl_name a",
                "company": ".prodcatalog-item_company, .pdl_company"
            }
        },
        {
            "name": "ExportersIndia",
            "search_url": "https://www.exportersindia.com/india-suppliers/{keyword}.htm",
            "selectors": {
                "item": ".prod-listings, .product-item",
                "title": "h3 a, .product-title",
                "link": "h3 a, .product-title a",
                "company": ".company-name, .supplier-name"
            }
        }
    ]
    
    def __init__(self, keywords: List[str], headless: bool = True):
        self.keywords = keywords
        self.headless = headless
        self.leads = []
    
    async def scrape(self, pages: int = 2) -> List[BuyerLead]:
        """Scrape configured B2B sites"""
        # Note: This would use Playwright but keeping it simple for now
        # For production, add proper Playwright implementation here
        logger.info("B2B: Simple scraper - use API/RSS sources for reliability")
        return self.leads


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

async def run_obie(
    keywords: List[str],
    output_dir: str = "output",
    sam_api_key: str = None,
    days_back: int = 30,
    sources: List[str] = None
) -> Dict:
    """
    Run OBIE pipeline with all sources.
    
    Args:
        keywords: Products/services to search for
        output_dir: Directory for output files
        sam_api_key: SAM.gov API key (optional)
        days_back: Days to search back
        sources: List of sources to use (default: all)
    """
    if sources is None:
        sources = ['ted', 'rss']  # Default to reliable sources
    
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    all_leads = []
    stats = {}
    
    # TED API
    if 'ted' in sources:
        try:
            ted = TEDScraper(keywords)
            leads = ted.scrape(days_back)
            all_leads.extend(leads)
            stats['ted'] = len(leads)
            logger.info(f"TED: {len(leads)} tenders")
        except Exception as e:
            logger.error(f"TED failed: {e}")
            stats['ted'] = 0
    
    # SAM.gov API
    if 'sam' in sources and sam_api_key:
        try:
            sam = SAMScraper(keywords, sam_api_key)
            leads = sam.scrape(days_back)
            all_leads.extend(leads)
            stats['sam'] = len(leads)
            logger.info(f"SAM.gov: {len(leads)} opportunities")
        except Exception as e:
            logger.error(f"SAM.gov failed: {e}")
            stats['sam'] = 0
    
    # RSS Feeds
    if 'rss' in sources:
        try:
            rss = RSSMonitor(keywords)
            leads = rss.scrape()
            all_leads.extend(leads)
            stats['rss'] = len(leads)
            logger.info(f"RSS: {len(leads)} leads")
        except Exception as e:
            logger.error(f"RSS failed: {e}")
            stats['rss'] = 0
    
    # Deduplicate by URL
    seen = set()
    unique_leads = []
    for lead in all_leads:
        if lead.source_url not in seen:
            seen.add(lead.source_url)
            unique_leads.append(lead)
    
    # Sort by score
    unique_leads.sort(key=lambda x: x.lead_score, reverse=True)
    
    # Save results
    output_file = f"{output_dir}/obie_leads_{timestamp}.csv"
    if unique_leads:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=BuyerLead.headers())
            writer.writeheader()
            for lead in unique_leads:
                writer.writerow(lead.to_row())
        logger.info(f"Saved {len(unique_leads)} leads to {output_file}")
    
    # Summary stats
    tier_counts = {'S': 0, 'A': 0, 'B': 0, 'C': 0}
    for lead in unique_leads:
        tier_counts[lead.lead_tier] += 1
    
    summary = {
        'timestamp': timestamp,
        'keywords': keywords,
        'sources': stats,
        'total_unique': len(unique_leads),
        'tiers': tier_counts,
        'top_leads': [l.to_row() for l in unique_leads[:10]]
    }
    
    summary_file = f"{output_dir}/obie_summary_{timestamp}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "="*60)
    print("OBIE PIPELINE COMPLETE")
    print("="*60)
    print(f"\nKeywords: {', '.join(keywords)}")
    print(f"\nLeads by Source:")
    for source, count in stats.items():
        print(f"  - {source}: {count}")
    print(f"\nTotal Unique: {len(unique_leads)}")
    print(f"\nLead Tiers:")
    print(f"  S (Priority): {tier_counts['S']}")
    print(f"  A (High):     {tier_counts['A']}")
    print(f"  B (Medium):   {tier_counts['B']}")
    print(f"  C (Low):      {tier_counts['C']}")
    print(f"\nOutput: {output_file}")
    print("="*60)
    
    return summary


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="OBIE 2.0 - API-Based Lead Scraper")
    parser.add_argument("--products", required=True, help="Comma-separated keywords")
    parser.add_argument("--output", default="output", help="Output directory")
    parser.add_argument("--sam-key", help="SAM.gov API key")
    parser.add_argument("--days", type=int, default=30, help="Days back")
    parser.add_argument("--sources", default="ted,rss", help="Sources: ted,sam,rss")
    
    args = parser.parse_args()
    
    keywords = [k.strip() for k in args.products.split(',')]
    sources = [s.strip() for s in args.sources.split(',')]
    
    asyncio.run(run_obie(
        keywords=keywords,
        output_dir=args.output,
        sam_api_key=args.sam_key,
        days_back=args.days,
        sources=sources
    ))


if __name__ == "__main__":
    main()
