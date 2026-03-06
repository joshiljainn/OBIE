"""
Trade Signals Adapter

Monitors social platforms, news, and trade signals for buyer intent.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import feedparser
import httpx

from app.adapters.base import LeadSignal, SourceAdapter, FetchError, ParseError

logger = logging.getLogger(__name__)


class SignalsAdapter(SourceAdapter):
    """
    Adapter for trade signals from social platforms and news.
    
    Supports:
    - Reddit (procurement subreddits)
    - RSS feeds from trade publications
    - Twitter/X (via API or search)
    
    Note: Social signals are lower quality but higher freshness.
    """
    
    SOURCE_NAME = "trade_signals"
    SOURCE_DISPLAY_NAME = "Trade Signals"
    SOURCE_TYPE = "trade_signal"
    RATE_LIMIT_PER_MINUTE = 30
    REQUEST_DELAY = 2.0
    
    # Pre-configured RSS feeds
    RSS_FEEDS = [
        {
            "name": "Global Trade News",
            "url": "https://www.globaltrademag.com/feed/",
            "category": "news",
        },
        {
            "name": "Procurement Leaders",
            "url": "https://www.procurementleaders.com/rss",
            "category": "procurement",
        },
    ]
    
    # Subreddits to monitor
    SUBREDDITS = [
        "procurement",
        "supplychain",
        "manufacturing",
        "Construction",
        "importexport",
    ]
    
    # Search queries indicating buyer intent
    BUYER_QUERIES = [
        "looking for suppliers",
        "need manufacturer",
        "RFQ",
        "seeking supplier",
        "vendor recommendation",
        "sourcing request",
    ]
    
    def __init__(self, signal_type: str = "rss"):
        """
        Initialize Signals adapter.
        
        Args:
            signal_type: Type of signal (rss, reddit, twitter)
        """
        self.signal_type = signal_type
    
    async def fetch(self, config: Dict[str, Any]) -> List[Any]:
        """
        Fetch trade signals.
        
        Config expects:
        - keywords: List of product keywords
        - signal_type: rss, reddit, or twitter
        """
        keywords = config.get("keywords", [])
        
        if self.signal_type == "rss":
            return await self._fetch_rss(keywords)
        elif self.signal_type == "reddit":
            return await self._fetch_reddit(keywords)
        elif self.signal_type == "twitter":
            return await self._fetch_twitter(keywords)
        else:
            return []
    
    async def _fetch_rss(self, keywords: List[str]) -> List[Dict]:
        """Fetch from RSS feeds."""
        results = []
        
        for feed_config in self.RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_config["url"])
                
                if feed.bozo:
                    logger.debug(f"Invalid RSS feed: {feed_config['name']}")
                    continue
                
                for entry in feed.entries[:20]:  # Limit per feed
                    results.append({
                        "type": "rss_entry",
                        "feed_name": feed_config["name"],
                        "feed_url": feed_config["url"],
                        "entry": {
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", ""),
                            "link": entry.get("link", ""),
                            "published": entry.get("published", ""),
                        },
                    })
                
            except Exception as e:
                logger.debug(f"RSS feed error ({feed_config['name']}): {e}")
        
        return results
    
    async def _fetch_reddit(self, keywords: List[str]) -> List[Dict]:
        """Fetch from Reddit (via pushshift API or web)."""
        results = []
        
        # Use Reddit search via Google as fallback
        for subreddit in self.SUBREDDITS[:3]:  # Limit to avoid rate limiting
            for query in self.BUYER_QUERIES[:2]:
                try:
                    # Google site:reddit.com search
                    search_url = f"https://www.google.com/search?q=site:reddit.com/r/{subreddit}+%22{query}%22"
                    
                    results.append({
                        "type": "reddit_search",
                        "subreddit": subreddit,
                        "query": query,
                        "search_url": search_url,
                    })
                    
                except Exception as e:
                    logger.debug(f"Reddit search error: {e}")
        
        return results
    
    async def _fetch_twitter(self, keywords: List[str]) -> List[Dict]:
        """Fetch from Twitter (requires API or use search)."""
        # Twitter API requires paid access
        # Return search URLs for now
        results = []
        
        for query in self.BUYER_QUERIES[:3]:
            search_url = f"https://twitter.com/search?q={query.replace(' ', '%20')}&f=live"
            
            results.append({
                "type": "twitter_search",
                "query": query,
                "search_url": search_url,
            })
        
        return results
    
    async def parse(self, raw_data: Any) -> List[LeadSignal]:
        """Parse raw signal data into LeadSignal objects."""
        if not isinstance(raw_data, list):
            raise ParseError("Expected list of raw data items")
        
        leads = []
        
        for item in raw_data:
            item_type = item.get("type", "")
            
            if item_type == "rss_entry":
                lead = self._parse_rss_entry(item)
                if lead:
                    leads.append(lead)
            
            elif item_type == "reddit_search":
                lead = self._parse_reddit_search(item)
                if lead:
                    leads.append(lead)
            
            elif item_type == "twitter_search":
                lead = self._parse_twitter_search(item)
                if lead:
                    leads.append(lead)
        
        logger.info(f"Parsed {len(leads)} trade signals")
        return leads
    
    def _parse_rss_entry(self, item: Dict) -> Optional[LeadSignal]:
        """Parse RSS entry into lead signal."""
        entry = item.get("entry", {})
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        content = title + " " + summary
        
        # Check for buyer intent keywords
        buyer_keywords = ["buyer", "looking for", "need", "seeking", "RFQ", "procurement"]
        has_intent = any(kw in content.lower() for kw in buyer_keywords)
        
        if not has_intent:
            return None
        
        lead = self.create_lead_signal(
            buyer_name=item.get("feed_name", "Unknown"),
            product_text=title[:200],
            source_url=entry.get("link", ""),
            description=summary[:500] if summary else title,
            raw_payload=item,
            extraction_confidence=0.5 if has_intent else 0.3,
        )
        
        return lead
    
    def _parse_reddit_search(self, item: Dict) -> Optional[LeadSignal]:
        """Create lead signal from Reddit search."""
        lead = self.create_lead_signal(
            buyer_name=f"Reddit User (r/{item.get('subreddit')})",
            product_text=item.get("query", ""),
            source_url=item.get("search_url", ""),
            description=f"Reddit search: {item.get('query')} in r/{item.get('subreddit')}",
            raw_payload=item,
            extraction_confidence=0.4,
        )
        
        return lead
    
    def _parse_twitter_search(self, item: Dict) -> Optional[LeadSignal]:
        """Create lead signal from Twitter search."""
        lead = self.create_lead_signal(
            buyer_name="Twitter User",
            product_text=item.get("query", ""),
            source_url=item.get("search_url", ""),
            description=f"Twitter search: {item.get('query')}",
            raw_payload=item,
            extraction_confidence=0.3,
        )
        
        return lead
