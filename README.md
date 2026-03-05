# OBIE 2.0 - OSINT Buyer Intent Engine

**Automated B2B buyer discovery across tenders, trade boards, and social signals.**

---

## What This Does

OBIE scrapes **high-intent buyer leads** from 3 sources:

| Source | Examples | Intent Level | Value |
|--------|----------|--------------|-------|
| **Tender Portals** | EU TED, UAE eProcurement, UN | 🔥 Critical | $10K-10M deals |
| **B2B Trade Boards** | TradeKey, go4WorldBusiness, EC21 | 🔥 High | Active RFQs |
| **Social Signals** | Reddit, LinkedIn, Twitter | ⚡ Medium | Real-time inquiries |

### Output: Scored, Ranked Leads

```
S-Tier (200+ pts): Government tenders with budget + deadline <30 days
A-Tier (120+ pts): B2B RFQs with quantity + destination specified
B-Tier (60+ pts):  General buying inquiries
C-Tier (<60 pts):  Passive interest / nurture
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install  # Install browser binaries
```

### 2. Set API Key (Optional - for LLM enrichment)

```bash
export GROQ_API_KEY="your-groq-api-key"  # Get free at https://console.groq.com
```

### 3. Run the Pipeline

```bash
# Scrape all sources for your products
python main.py --products "plywood,ceramic tiles,steel" --all

# Scrape only tenders (highest value)
python main.py --products "plywood" --tenders --days 30

# Scrape only B2B boards
python main.py --products "textiles" --b2b --pages 5

# Show browser (debug mode)
python main.py --products "plywood" --all --no-headless
```

### 4. Check Results

```
output/
├── all_leads_scored_20260305_143022.csv    # Unified, ranked leads
├── tender_leads_20260305_143022.csv        # Tender-specific
├── b2b_leads_20260305_143022.csv           # B2B-specific
├── social_leads_20260305_143022.csv        # Social-specific
└── summary_20260305_143022.json            # Stats + top leads
```

---

## Lead Scoring System

Leads are scored automatically based on:

| Factor | Points |
|--------|--------|
| **Source Type** | |
| Tender portal | +100 |
| B2B board | +50 |
| Social signal | +20 |
| **Modifiers** | |
| Budget specified | +50 |
| Deadline specified | +30 |
| Quantity specified | +25 |
| Destination country | +20 |
| Contact info available | +30 |
| Deadline <30 days (urgent) | +40 |
| **Multiplier** | |
| Government buyer | 1.5x |

---

## Architecture

```
main.py (Orchestrator)
│
├── scrapers/
│   ├── b2b_scraper.py    → TradeKey, go4WorldBusiness, EC21
│   ├── tender_scraper.py → EU TED, UAE eProcurement, UN
│   └── social_scraper.py → Reddit, LinkedIn, Twitter
│
├── models.py             → Unified BuyerLead schema
├── validator.py          → Email verification (SMTP ping)
└── verifier.py           → LLM company classification (legacy)
```

---

## CLI Reference

```bash
python main.py --products "PRODUCT1,PRODUCT2" [OPTIONS]

Required:
  --products TEXT         Comma-separated products (e.g., "plywood,steel")

Source Selection (default: all):
  --b2b                   Scrape B2B boards only
  --tenders               Scrape tender portals only
  --social                Scrape social signals only
  --all                   Scrape all sources (default)

Options:
  --days INT              Days back for tenders (default: 30)
  --pages INT             Pages per B2B site (default: 3)
  --output-dir PATH       Output directory (default: output)
  --no-headless           Show browser windows (debug)
  --help                  Show this message
```

---

## Example Output (CSV)

```csv
source_type,source_url,intent_level,product,quantity,destination_country,budget,deadline,buyer_name,lead_score,lead_tier
tender,https://ted.europa.eu/TED/notice/123,critical,Construction Materials,500 tons,UAE,AED 2,500,000,15/04/2026,UAE Ministry of Infrastructure,280,S
b2b_board,https://www.tradekey.com/buying-leads/456,high,Plywood Sheets,1000 units,Pakistan,,30/03/2026,Al-Rashid Trading,145,A
social,https://reddit.com/r/procurement/comments/789,medium,Looking for ceramic tile suppliers,,,,,u/DubaiBuilder,45,C
```

---

## Advanced: Email Validation Pipeline

After scraping, validate contact emails:

```bash
# Run email verification on scraped leads
python validator.py
```

This will:
1. Scrape contact pages for each lead's website
2. Extract email addresses
3. Run SMTP pings to verify deliverability
4. Output to `final_leads.csv` with verification status

---

## Scheduling (Production Use)

Run OBIE daily with cron:

```bash
# Edit crontab
crontab -e

# Add daily run at 6 AM
0 6 * * * cd "/path/to/OBIE" && python main.py --products "plywood,ceramic tiles" --all >> output/daily.log 2>&1
```

---

## Troubleshooting

### CAPTCHA / Blocking Issues
- Use `--no-headless` to see what's happening
- Reduce request frequency (increase delays in scraper code)
- Use residential proxies for large-scale scraping

### No Results Found
- Try different product keywords (more specific)
- Increase `--pages` for B2B scraping
- Check if target sites are accessible

### Email Validation Fails
- Some domains block SMTP pings (catch-all servers)
- MX records may be temporarily unavailable

---

## Legal & Ethics

- **Respect robots.txt** and site Terms of Service
- **Rate limiting** is built-in to avoid overwhelming servers
- **Public data only** - no login bypassing or private data access
- **GDPR compliance** - only scrape business contact information

---

## License

MIT License - See LICENSE file

---

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Contact: [your-email@example.com]
