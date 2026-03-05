"""
Social Signal Scrapers
Monitor social platforms for procurement/sourcing signals

Sources:
- Reddit: r/procurement, r/supplychain, r/manufacturing, r/Construction
- LinkedIn: Public posts with sourcing keywords (requires careful scraping)
- Twitter/X: Procurement-related tweets

These provide real-time signals but require filtering for noise.
"""
import asyncio
import csv
import logging
import re
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth
import requests

from models import BuyerLead, calculate_intent_level

stealth = Stealth()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RedditScraper:
    """
    Scrapes procurement-related subreddits for buying signals.
    
    Target subreddits:
    - r/procurement
    - r/supplychain
    - r/manufacturing
    - r/Construction
    - r/AskEngineers (sometimes has sourcing requests)
    - r/smallbusiness
    
    Search patterns:
    - "looking for suppliers"
    - "need manufacturer"
    - "RFQ"
    - "source from"
    - "alternative supplier"
    - "vendor recommendation"
    """
    
    BASE_URL = "https://www.reddit.com"
    SUBREDDITS = [
        'procurement',
        'supplychain',
        'manufacturing',
        'Construction',
        'AskEngineers',
        'smallbusiness',
        'entrepreneur',
        'importexport'
    ]
    
    SEARCH_QUERIES = [
        'looking for suppliers',
        'need manufacturer',
        'need suppliers',
        'RFQ request',
        'source from',
        'alternative supplier',
        'vendor recommendation',
        'seeking manufacturer',
        'looking for vendor',
        'need to source',
        'supplier recommendation',
        'manufacturing partner'
    ]
    
    def __init__(self, product_keywords: List[str] = None, headless: bool = True):
        self.product_keywords = product_keywords or []
        self.headless = headless
        self.leads = []
    
    async def scrape(self, limit: int = 50) -> List[BuyerLead]:
        """
        Scrape Reddit for procurement signals.
        
        Args:
            limit: Maximum posts to fetch per subreddit
        """
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
            
            # Search each subreddit for our queries
            for subreddit in self.SUBREDDITS:
                logger.info(f"Scraping r/{subreddit}")
                await self._scrape_subreddit(page, subreddit, limit)
                await asyncio.sleep(2)
            
            await browser.close()
        
        return self.leads
    
    async def _scrape_subreddit(self, page, subreddit: str, limit: int):
        """Scrape a single subreddit"""
        
        # Method 1: Search within subreddit
        for query in self.SEARCH_QUERIES[:3]:  # Limit queries to avoid rate limiting
            search_url = f"{self.BASE_URL}/r/{subreddit}/search?q={query.replace(' ', '+')}&sort=new"
            
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)
                
                # Reddit may show a login popup - try to dismiss it
                try:
                    close_btn = await page.query_selector('button[aria-label="Close"]', timeout=3000)
                    if close_btn:
                        await close_btn.click()
                        await asyncio.sleep(1)
                except:
                    pass
                
                await self._extract_posts_from_page(page, subreddit)
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.debug(f"Failed to search r/{subreddit} for '{query}': {e}")
        
        # Method 2: Also check hot posts for keywords
        try:
            hot_url = f"{self.BASE_URL}/r/{subreddit}/hot/"
            await page.goto(hot_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            await self._extract_posts_from_page(page, subreddit, check_keywords=True)
        except Exception as e:
            logger.debug(f"Failed to load hot posts for r/{subreddit}: {e}")
    
    async def _extract_posts_from_page(self, page, subreddit: str, check_keywords: bool = False):
        """Extract relevant posts from the page"""
        
        post_cards = await page.query_selector_all(
            'shreddit-post, post-tile, article[data-post-id]'
        )
        
        keywords = self.product_keywords + ['supplier', 'manufacturer', 'source', 'RFQ', 'vendor']
        
        for card in post_cards[:20]:  # Limit per page
            try:
                # Title
                title_el = await card.query_selector('h3, [slot="title"], .title')
                title = await title_el.inner_text() if title_el else ""
                
                if not title:
                    continue
                
                # Check if relevant
                title_lower = title.lower()
                is_relevant = (
                    any(kw.lower() in title_lower for kw in ['looking for', 'need', 'seeking', 'RFQ', 'recommendation']) or
                    (check_keywords and any(kw.lower() in title_lower for kw in keywords))
                )
                
                if not is_relevant:
                    continue
                
                # URL
                link_el = await card.query_selector('a[href*="/comments/"]')
                source_url = await link_el.get_attribute('href') if link_el else ""
                if source_url and source_url.startswith('/'):
                    source_url = f"{self.BASE_URL}{source_url}"
                
                # Author
                author_el = await card.query_selector('[slot="author"], .author, user-name')
                author = await author_el.inner_text() if author_el else "u/unknown"
                
                # Timestamp
                time_el = await card.query_selector('[slot="timestamp"], time')
                timestamp = await time_el.get_attribute('datetime') if time_el else ""
                
                # Extract product mentions
                mentioned_products = []
                for product in self.product_keywords:
                    if product.lower() in title_lower:
                        mentioned_products.append(product)
                
                # Score/upvotes
                score_el = await card.query_selector('[slot="vote-summary"], .score')
                score_text = await score_el.inner_text() if score_el else "0"
                
                lead = BuyerLead(
                    source_type="social",
                    source_url=source_url or f"{self.BASE_URL}/r/{subreddit}",
                    intent_level=calculate_intent_level(
                        has_quantity=False,
                        has_destination=False
                    ),
                    product=', '.join(mentioned_products) if mentioned_products else title[:200],
                    buyer_name=f"Reddit User: {author}",
                    buyer_type="Private",
                    description=f"r/{subreddit}: {title}",
                    scraped_at=datetime.now().isoformat()
                )
                self.leads.append(lead)
                
            except Exception as e:
                logger.debug(f"Error extracting post: {e}")
        
        logger.info(f"Extracted posts from r/{subreddit}")


class LinkedInScraper:
    """
    Scrapes LinkedIn for procurement/sourcing posts.
    
    WARNING: LinkedIn has strict anti-scraping measures.
    This scraper uses public search and requires careful rate limiting.
    
    Search patterns:
    - "looking for suppliers"
    - "seeking manufacturers"
    - "RFQ"
    - "procurement opportunity"
    - "sourcing request"
    """
    
    BASE_URL = "https://www.linkedin.com"
    
    SEARCH_QUERIES = [
        'looking for suppliers',
        'seeking manufacturers',
        'RFQ procurement',
        'sourcing request',
        'need supplier',
        'procurement opportunity',
        'vendor search',
        'supplier partnership'
    ]
    
    def __init__(self, product_keywords: List[str] = None, headless: bool = True):
        self.product_keywords = product_keywords or []
        self.headless = headless
        self.leads = []
    
    async def scrape(self, limit: int = 20) -> List[BuyerLead]:
        """
        Scrape LinkedIn for procurement signals.
        
        Note: This requires being logged in for best results.
        Without login, only limited public posts are visible.
        """
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
            
            # Try to navigate to LinkedIn
            try:
                await page.goto(f"{self.BASE_URL}/feed/", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(5)
                
                # Check if logged in
                is_logged_in = await page.is_visible('div.profile-details', timeout=5000)
                if not is_logged_in:
                    logger.warning("Not logged into LinkedIn. Results will be limited.")
                    # Still try public search
                    await self._scrape_public_posts(page, limit)
                else:
                    await self._scrape_with_login(page, limit)
                    
            except Exception as e:
                logger.warning(f"LinkedIn access failed: {e}")
                await self._scrape_public_posts(page, limit)
            
            await browser.close()
        
        return self.leads
    
    async def _scrape_with_login(self, page, limit: int):
        """Scrape with logged-in access"""
        for query in self.SEARCH_QUERIES[:5]:
            logger.info(f"Searching LinkedIn for: {query}")
            
            search_url = f"{self.BASE_URL}/feed/search?q={query.replace(' ', '%20')}&type=content"
            
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(5)
                await self._extract_linkedin_posts(page)
                await asyncio.sleep(3)
            except Exception as e:
                logger.debug(f"Search failed for '{query}': {e}")
    
    async def _scrape_public_posts(self, page, limit: int):
        """Scrape public posts without login"""
        # Use Google site:linkedin.com search as fallback
        for query in self.SEARCH_QUERIES[:3]:
            google_search = f"https://www.google.com/search?q=site:linkedin.com+%22{query}%22"
            
            try:
                await page.goto(google_search, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)
                
                # Extract LinkedIn URLs from Google results
                results = await page.query_selector_all('div.g a[href*="linkedin.com"]')
                for result in results[:limit]:
                    href = await result.get_attribute('href')
                    title_el = await result.query_selector('h3')
                    title = await title_el.inner_text() if title_el else ""
                    
                    if href and '/posts/' in href:
                        lead = BuyerLead(
                            source_type="social",
                            source_url=href,
                            intent_level="medium",
                            product=query,
                            description=f"LinkedIn post: {title}",
                            scraped_at=datetime.now().isoformat()
                        )
                        self.leads.append(lead)
                
                await asyncio.sleep(2)
            except Exception as e:
                logger.debug(f"Google search failed: {e}")
    
    async def _extract_linkedin_posts(self, page):
        """Extract post data from LinkedIn page"""
        posts = await page.query_selector_all(
            'div.update-components-text, div.feed-shared-update-v2'
        )
        
        for post in posts[:10]:
            try:
                # Text content
                text_el = await post.query_selector('.update-components-text, .feed-shared-update-v2__description')
                text = await text_el.inner_text() if text_el else ""
                
                # Check for relevant keywords
                if not any(kw in text.lower() for kw in ['supplier', 'manufacturer', 'source', 'RFQ']):
                    continue
                
                # Author
                author_el = await post.query_selector('.feed-shared-actor-name')
                author = await author_el.inner_text() if author_el else ""
                
                # URL (requires finding the post link)
                link_el = await post.query_selector('a.update-components-actor__name')
                source_url = await link_el.get_attribute('href') if link_el else ""
                
                lead = BuyerLead(
                    source_type="social",
                    source_url=source_url or self.BASE_URL,
                    intent_level="medium",
                    product=text[:200],
                    buyer_name=author if author else "LinkedIn User",
                    buyer_type="Private",
                    description=text[:500],
                    scraped_at=datetime.now().isoformat()
                )
                self.leads.append(lead)
                
            except Exception as e:
                logger.debug(f"Error extracting LinkedIn post: {e}")


class TwitterScraper:
    """
    Scrapes Twitter/X for procurement signals.
    
    Search patterns:
    - "looking for supplier"
    - "need manufacturer"
    - "RFQ"
    - "sourcing"
    """
    
    BASE_URL = "https://twitter.com"
    
    def __init__(self, product_keywords: List[str] = None, headless: bool = True):
        self.product_keywords = product_keywords or []
        self.headless = headless
        self.leads = []
    
    async def scrape(self, limit: int = 30) -> List[BuyerLead]:
        """Scrape Twitter for procurement signals"""
        search_queries = [
            'looking for supplier',
            'need manufacturer',
            'RFQ',
            'sourcing opportunity',
            'seeking supplier'
        ]
        
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
            
            for query in search_queries:
                logger.info(f"Searching Twitter for: {query}")
                
                search_url = f"{self.BASE_URL}/search?q={query.replace(' ', '%20')}&f=live"
                
                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(5)
                    
                    # Extract tweets
                    tweets = await page.query_selector_all('article[data-testid="tweet"]')
                    
                    for tweet in tweets[:limit]:
                        try:
                            # Text
                            text_el = await tweet.query_selector('[data-testid="tweetText"]')
                            text = await text_el.inner_text() if text_el else ""
                            
                            # Author
                            author_el = await tweet.query_selector('[data-testid="User-Name"]')
                            author = await author_el.inner_text() if author_el else ""
                            
                            # URL
                            time_el = await tweet.query_selector('time')
                            parent = time_el.locator('..').locator('..') if time_el else None
                            # Twitter URLs are complex, using placeholder
                            
                            if text and len(text) > 20:
                                lead = BuyerLead(
                                    source_type="social",
                                    source_url=f"{self.BASE_URL}/search?q={query}",
                                    intent_level="low",
                                    product=text[:200],
                                    buyer_name=f"Twitter: {author}" if author else "Twitter User",
                                    buyer_type="Private",
                                    description=text[:500],
                                    scraped_at=datetime.now().isoformat()
                                )
                                self.leads.append(lead)
                        except Exception as e:
                            logger.debug(f"Error extracting tweet: {e}")
                    
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.debug(f"Twitter search failed: {e}")
            
            await browser.close()
        
        return self.leads


async def scrape_social_signals(
    product_keywords: List[str] = None,
    output_file: str = "social_leads.csv",
    headless: bool = True,
    platforms: List[str] = None
) -> List[BuyerLead]:
    """
    Scrape social platforms for procurement signals.
    
    Args:
        product_keywords: Products to search for
        output_file: CSV file to save results
        headless: Run browser in headless mode
        platforms: List of platforms (reddit, linkedin, twitter)
    
    Returns:
        List of BuyerLead objects
    """
    if platforms is None:
        platforms = ['reddit', 'twitter']  # LinkedIn requires login
    
    all_leads = []
    
    # Reddit
    if 'reddit' in platforms:
        try:
            reddit_scraper = RedditScraper(product_keywords, headless)
            reddit_leads = await reddit_scraper.scrape()
            all_leads.extend(reddit_leads)
            logger.info(f"Reddit: {len(reddit_leads)} signals")
        except Exception as e:
            logger.error(f"Reddit scraping failed: {e}")
    
    # LinkedIn (limited without login)
    if 'linkedin' in platforms:
        try:
            linkedin_scraper = LinkedInScraper(product_keywords, headless)
            linkedin_leads = await linkedin_scraper.scrape()
            all_leads.extend(linkedin_leads)
            logger.info(f"LinkedIn: {len(linkedin_leads)} signals")
        except Exception as e:
            logger.error(f"LinkedIn scraping failed: {e}")
    
    # Twitter
    if 'twitter' in platforms:
        try:
            twitter_scraper = TwitterScraper(product_keywords, headless)
            twitter_leads = await twitter_scraper.scrape()
            all_leads.extend(twitter_leads)
            logger.info(f"Twitter: {len(twitter_leads)} signals")
        except Exception as e:
            logger.error(f"Twitter scraping failed: {e}")
    
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
        logger.info(f"Saved {len(unique_leads)} unique social leads to {output_file}")
    
    return unique_leads


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape Social Platforms for procurement signals")
    parser.add_argument(
        "--products",
        required=True,
        help="Comma-separated product keywords"
    )
    parser.add_argument("--output", default="social_leads.csv", help="Output CSV file")
    parser.add_argument("--platforms", default="reddit,twitter", help="Comma-separated: reddit,linkedin,twitter")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    
    args = parser.parse_args()
    
    products = [p.strip() for p in args.products.split(',')]
    platform_list = [p.strip() for p in args.platforms.split(',')]
    
    leads = asyncio.run(scrape_social_signals(
        product_keywords=products,
        output_file=args.output,
        headless=not args.no_headless,
        platforms=platform_list
    ))
    
    print(f"\n{'='*50}")
    print(f"Total Social Signals Found: {len(leads)}")
    print(f"Results saved to: {args.output}")
