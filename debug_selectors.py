"""
Debug script to inspect B2B site structures and find correct selectors
"""
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth

stealth = Stealth()

async def inspect_site(url, name):
    """Visit a site and print available selectors"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={'width': 1366, 'height': 768}
        )
        page = await context.new_page()
        await stealth.apply_stealth_async(page)
        
        print(f"\n{'='*60}")
        print(f"Inspecting: {name}")
        print(f"URL: {url}")
        print('='*60)
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
            
            # Get page title
            title = await page.title()
            print(f"\nPage Title: {title}")
            
            # Check for common lead/card elements
            selectors_to_try = [
                '.buying-leads-item', '.rfq-item', '.postings',
                '.product-item', '.trade-item', '.offer-item',
                '[itemtype*="RFQ"]', '[itemtype*="BuyAction"]',
                'article', '.card', '.listing', '.result-item',
                '.search-result', '.product-list li', 'table tr'
            ]
            
            print("\nTrying selectors:")
            for selector in selectors_to_try:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"  ✅ {selector}: {len(elements)} elements found")
                        # Print first element's classes and structure
                        if len(elements) > 0:
                            class_name = await elements[0].get_attribute('class')
                            tag_name = await elements[0].evaluate('el => el.tagName')
                            print(f"      Tag: {tag_name}, Classes: {class_name[:100] if class_name else 'none'}")
                except Exception as e:
                    pass
            
            # Get all text content (first 2000 chars)
            text = await page.content()
            # Look for product-like patterns
            import re
            product_patterns = re.findall(r'[\w\s]+(?:plywood|wood|timber|board)[\w\s]+', text[:10000], re.IGNORECASE)
            if product_patterns:
                print(f"\nProduct mentions found: {len(product_patterns)}")
                for p in product_patterns[:5]:
                    print(f"  - {p.strip()[:80]}")
            
        except Exception as e:
            print(f"Error: {e}")
        
        await browser.close()

async def main():
    # Test with actual buying lead URLs
    await inspect_site(
        "https://www.tradekey.com/buying-leads/search.html?query=plywood&searchType=buying-leads",
        "TradeKey"
    )
    await inspect_site(
        "https://www.go4worldbusiness.com/find.php?search=plywood&buyers=1",
        "go4WorldBusiness"
    )
    await inspect_site(
        "https://www.ec21.com/buyOffer/search.do?searchword=plywood",
        "EC21"
    )

if __name__ == "__main__":
    asyncio.run(main())
