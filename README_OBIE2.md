# OBIE 2.0 - OSINT Buyer Intent Engine

**Automated B2B buyer discovery from tenders, trade boards, and social signals.**

---

## ⚠️ Current Status: Beta

This is a **work-in-progress** framework. The architecture is solid, but individual scrapers need maintenance as sites change their structures.

### What Works ✅

| Component | Status | Notes |
|-----------|--------|-------|
| Lead Scoring System | ✅ Working | S/A/B/C tiers based on budget, deadline, quantity |
| Unified Data Model | ✅ Working | All sources output to same schema |
| CLI Interface | ✅ Working | Easy to run and configure |
| TED Fallback | ⚠️ Partial | Creates search links (API needs auth) |
| RSS Monitor | ⚠️ Partial | Feed URLs need updating |
| SAM.gov | ⚠️ Needs API Key | Works with valid key |

### What Needs Work ⚠️

| Component | Issue | Solution |
|-----------|-------|----------|
| B2B Scrapers | Sites block bots | Need proxy rotation + better stealth |
| TED API | Requires authentication | Get free API key from EU |
| RSS Feeds | URLs change frequently | Manual maintenance needed |
| Tender Portals | Anti-scraping measures | Use official APIs where possible |

---

## Quick Start

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
# Basic run (TED + RSS)
python obie_v2.py --products "plywood,construction"

# With SAM.gov (US tenders)
python obie_v2.py --products "construction" --sam-key "YOUR_API_KEY"

# Select specific sources
python obie_v2.py --products "steel" --sources "ted,rss"
```

### Output

```
output/
├── obie_leads_TIMESTAMP.csv      # All leads with scores
└── obie_summary_TIMESTAMP.json   # Stats + top leads
```

---

## Lead Scoring

| Score | Tier | Meaning |
|-------|------|---------|
| 200+ | **S** | Government tender, budget + urgent deadline |
| 120+ | **A** | Active RFQ with quantity + deadline |
| 60+ | **B** | General buying inquiry |
| <60 | **C** | Passive interest |

---

## Adding New Sources

### 1. API-Based Source (Recommended)

```python
class NewAPIScraper:
    def __init__(self, keywords, api_key=None):
        self.keywords = keywords
        self.api_key = api_key
        self.leads = []
    
    def scrape(self, days_back=30):
        for keyword in self.keywords:
            self._search(keyword, days_back)
        return self.leads
    
    def _search(self, keyword, days_back):
        # Make API request
        # Parse response
        # Create BuyerLead objects
        pass
```

### 2. RSS Feed

Add to `RSSMonitor.RSS_FEEDS`:

```python
{
    "name": "Your Source Name",
    "url": "https://example.com/rss/tenders.xml",
    "type": "tender_rss"  # or "b2b_rss"
}
```

### 3. Web Scraper

Use Playwright with manual selectors:

```python
SITE_CONFIGS = [
    {
        "name": "Site Name",
        "search_url": "https://example.com/search?q={keyword}",
        "selectors": {
            "item": ".product-card",
            "title": "h3 a",
            "link": "h3 a",
            "company": ".company-name"
        }
    }
]
```

---

## Getting API Keys

### EU TED API (Free)
1. Go to https://op.europa.eu/en/web/op-data-portal
2. Register for API access
3. Add key to `.env` or pass via `--ted-key`

### SAM.gov (Free)
1. Go to https://open.gsa.gov/api/sam-api/
2. Request API key
3. Use with `--sam-key` flag

---

## Troubleshooting

### No Leads Found

1. **Check keywords** - Try broader terms
2. **Check sources** - Some need API keys
3. **Check logs** - Look for error messages

### Sites Blocking Requests

1. Use `--no-headless` to see what's happening
2. Add delays between requests
3. Consider residential proxies

### RSS Feeds Not Working

Feed URLs change frequently. Update `RSSMonitor.RSS_FEEDS` with current URLs.

---

## Architecture

```
obie_v2.py (Main orchestrator)
│
├── TEDScraper          → EU tenders (API + web fallback)
├── SAMScraper          → US tenders (API)
├── RSSMonitor          → RSS feed aggregator
└── SimpleB2BScraper    → Manual selector-based scraping
│
└── BuyerLead           → Unified data model
    └── calculate_score() → Lead scoring logic
```

---

## Next Steps for Production

1. **Get API Keys** - TED, SAM.gov for reliable data
2. **Find Working RSS Feeds** - Research industry-specific feeds
3. **Add Proxy Support** - For B2B scraping without blocking
4. **Schedule Runs** - Cron job for daily lead generation
5. **Add Email Validation** - Integrate existing validator.py
6. **Build Dashboard** - Simple web UI for viewing leads

---

## License

MIT License

---

## Disclaimer

This tool is for educational purposes. Always respect website Terms of Service and robots.txt files. Use official APIs where available.
