"""
OBIE Orchestrator - Main Entry Point
Unifies all scrapers, applies lead scoring, and outputs ranked leads
"""
import asyncio
import csv
import logging
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

from models import BuyerLead
from scrapers.b2b_scraper import scrape_all_b2b_boards
from scrapers.tender_scraper import scrape_tender_portals
from scrapers.social_scraper import scrape_social_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class LeadScore:
    """
    Scoring weights for lead prioritization.
    
    Higher score = more valuable lead worth pursuing immediately
    """
    # Base intent scores
    TENDER_BASE = 100
    B2B_BOARD_BASE = 50
    SOCIAL_BASE = 20
    
    # Modifiers
    HAS_BUDGET = 50
    HAS_DEADLINE = 30
    HAS_QUANTITY = 25
    HAS_DESTINATION = 20
    HAS_CONTACT_INFO = 30
    URGENT_DEADLINE = 40  # <30 days
    
    # Buyer type multipliers
    GOVERNMENT_MULTIPLIER = 1.5
    PRIVATE_MULTIPLIER = 1.0


def calculate_lead_score(lead: BuyerLead) -> Dict:
    """
    Calculate a priority score for a lead.
    
    Returns dict with:
    - score: Numeric priority score
    - tier: S/A/B/C classification
    - reasons: Why this score was assigned
    """
    score = 0
    reasons = []
    
    # Base score by source type
    if lead.source_type == "tender":
        score += LeadScore.TENDER_BASE
        reasons.append("High-value tender source")
    elif lead.source_type == "b2b_board":
        score += LeadScore.B2B_BOARD_BASE
        reasons.append("Active RFQ on B2B board")
    elif lead.source_type == "social":
        score += LeadScore.SOCIAL_BASE
        reasons.append("Social media signal")
    
    # Budget modifier
    if lead.budget and lead.budget.strip():
        score += LeadScore.HAS_BUDGET
        reasons.append(f"Budget specified: {lead.budget}")
    
    # Deadline modifier
    if lead.deadline and lead.deadline.strip():
        score += LeadScore.HAS_DEADLINE
        reasons.append("Has submission deadline")
        
        # Check if deadline is urgent (<30 days)
        try:
            # Try common date formats
            deadline_date = None
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d %B %Y', '%B %d, %Y']:
                try:
                    deadline_date = datetime.strptime(lead.deadline.strip(), fmt)
                    break
                except ValueError:
                    continue
            
            if deadline_date:
                days_left = (deadline_date - datetime.now()).days
                if 0 < days_left <= 30:
                    score += LeadScore.URGENT_DEADLINE
                    reasons.append(f"Urgent: {days_left} days remaining")
                elif days_left <= 0:
                    score -= 20  # Past deadline
                    reasons.append("Warning: Deadline passed")
        except Exception as e:
            logger.debug(f"Could not parse deadline: {e}")
    
    # Quantity modifier
    if lead.quantity and lead.quantity.strip():
        score += LeadScore.HAS_QUANTITY
        reasons.append(f"Quantity specified: {lead.quantity}")
    
    # Destination modifier
    if lead.destination_country and lead.destination_country.strip():
        score += LeadScore.HAS_DESTINATION
        reasons.append(f"Destination: {lead.destination_country}")
    
    # Contact info modifier
    if lead.contact_email or lead.contact_phone:
        score += LeadScore.HAS_CONTACT_INFO
        reasons.append("Contact information available")
    
    # Buyer type multiplier
    if lead.buyer_type and "government" in lead.buyer_type.lower():
        score = int(score * LeadScore.GOVERNMENT_MULTIPLIER)
        reasons.append("Government buyer (1.5x multiplier)")
    
    # Determine tier
    if score >= 200:
        tier = "S"
        tier_desc = "Priority - Act Immediately"
    elif score >= 120:
        tier = "A"
        tier_desc = "High Priority"
    elif score >= 60:
        tier = "B"
        tier_desc = "Medium Priority"
    else:
        tier = "C"
        tier_desc = "Low Priority / Nurture"
    
    return {
        "score": score,
        "tier": tier,
        "tier_description": tier_desc,
        "reasons": reasons
    }


def enrich_lead(lead: BuyerLead, scoring_result: Dict) -> Dict:
    """
    Enrich a lead with scoring data for CSV output.
    """
    row = lead.to_csv_row()
    row['lead_score'] = scoring_result['score']
    row['lead_tier'] = scoring_result['tier']
    row['tier_description'] = scoring_result['tier_description']
    row['scoring_reasons'] = '; '.join(scoring_result['reasons'])
    return row


def get_enriched_headers() -> List[str]:
    """Get CSV headers including scoring fields."""
    return BuyerLead.csv_headers() + [
        'lead_score',
        'lead_tier',
        'tier_description',
        'scoring_reasons'
    ]


async def run_full_pipeline(
    product_keywords: List[str],
    output_dir: str = "output",
    run_b2b: bool = True,
    run_tenders: bool = True,
    run_social: bool = True,
    headless: bool = True,
    days_back: int = 30,
    pages_per_site: int = 3
) -> Dict:
    """
    Run the complete OBIE pipeline across all sources.
    
    Args:
        product_keywords: Products/services to search for
        output_dir: Directory to save output files
        run_b2b: Include B2B board scraping
        run_tenders: Include tender portal scraping
        run_social: Include social signal scraping
        headless: Run browsers in headless mode
        days_back: Fetch tenders from last N days
        pages_per_site: Pages to scrape per B2B site
    
    Returns:
        Dict with summary statistics and file paths
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    results = {
        "timestamp": timestamp,
        "products": product_keywords,
        "sources_run": [],
        "leads_found": {},
        "files": {},
        "summary": {}
    }
    
    all_leads = []
    
    # Run B2B Board Scrapers
    if run_b2b:
        logger.info("=" * 60)
        logger.info("Starting B2B Board Scrapers...")
        logger.info("=" * 60)
        results["sources_run"].append("b2b_boards")
        
        try:
            b2b_leads = await scrape_all_b2b_boards(
                product_keywords=product_keywords,
                output_file=f"{output_dir}/b2b_leads_{timestamp}.csv",
                headless=headless,
                pages_per_site=pages_per_site
            )
            all_leads.extend(b2b_leads)
            results["leads_found"]["b2b_boards"] = len(b2b_leads)
            results["files"]["b2b"] = f"{output_dir}/b2b_leads_{timestamp}.csv"
        except Exception as e:
            logger.error(f"B2B scraping failed: {e}")
            results["leads_found"]["b2b_boards"] = 0
    
    # Run Tender Portal Scrapers
    if run_tenders:
        logger.info("=" * 60)
        logger.info("Starting Tender Portal Scrapers...")
        logger.info("=" * 60)
        results["sources_run"].append("tender_portals")
        
        try:
            tender_leads = await scrape_tender_portals(
                product_keywords=product_keywords,
                output_file=f"{output_dir}/tender_leads_{timestamp}.csv",
                headless=headless,
                days_back=days_back
            )
            all_leads.extend(tender_leads)
            results["leads_found"]["tender_portals"] = len(tender_leads)
            results["files"]["tenders"] = f"{output_dir}/tender_leads_{timestamp}.csv"
        except Exception as e:
            logger.error(f"Tender scraping failed: {e}")
            results["leads_found"]["tender_portals"] = 0
    
    # Run Social Signal Scrapers
    if run_social:
        logger.info("=" * 60)
        logger.info("Starting Social Signal Scrapers...")
        logger.info("=" * 60)
        results["sources_run"].append("social_signals")
        
        try:
            social_leads = await scrape_social_signals(
                product_keywords=product_keywords,
                output_file=f"{output_dir}/social_leads_{timestamp}.csv",
                headless=headless
            )
            all_leads.extend(social_leads)
            results["leads_found"]["social_signals"] = len(social_leads)
            results["files"]["social"] = f"{output_dir}/social_leads_{timestamp}.csv"
        except Exception as e:
            logger.error(f"Social scraping failed: {e}")
            results["leads_found"]["social_signals"] = 0
    
    # Deduplicate all leads by URL
    logger.info("=" * 60)
    logger.info("Deduplicating and Scoring Leads...")
    logger.info("=" * 60)
    
    seen_urls = set()
    unique_leads = []
    for lead in all_leads:
        if lead.source_url not in seen_urls:
            seen_urls.add(lead.source_url)
            unique_leads.append(lead)
    
    results["leads_found"]["total_raw"] = len(all_leads)
    results["leads_found"]["unique"] = len(unique_leads)
    
    # Score and enrich all leads
    scored_leads = []
    tier_counts = {"S": 0, "A": 0, "B": 0, "C": 0}
    
    for lead in unique_leads:
        scoring = calculate_lead_score(lead)
        enriched = enrich_lead(lead, scoring)
        scored_leads.append(enriched)
        tier_counts[scoring['tier']] += 1
    
    # Sort by score (highest first)
    scored_leads.sort(key=lambda x: x['lead_score'], reverse=True)
    
    # Save unified output
    unified_file = f"{output_dir}/all_leads_scored_{timestamp}.csv"
    if scored_leads:
        with open(unified_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=get_enriched_headers())
            writer.writeheader()
            writer.writerows(scored_leads)
        results["files"]["unified"] = unified_file
    
    # Save summary report
    summary_file = f"{output_dir}/summary_{timestamp}.json"
    results["summary"] = {
        "total_leads": len(unique_leads),
        "tier_breakdown": tier_counts,
        "s_tier_leads": [l for l in scored_leads if l['lead_tier'] == 'S'][:10],  # Top 10
        "a_tier_leads": [l for l in scored_leads if l['lead_tier'] == 'A'][:20],  # Top 20
    }
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    results["files"]["summary"] = summary_file
    
    # Print summary
    print("\n" + "=" * 60)
    print("OBIE PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\nProducts searched: {', '.join(product_keywords)}")
    print(f"\nLeads by Source:")
    for source, count in results["leads_found"].items():
        print(f"  - {source}: {count}")
    print(f"\nLead Tiers:")
    print(f"  - S Tier (Priority): {tier_counts['S']}")
    print(f"  - A Tier (High):     {tier_counts['A']}")
    print(f"  - B Tier (Medium):   {tier_counts['B']}")
    print(f"  - C Tier (Low):      {tier_counts['C']}")
    print(f"\nOutput Files:")
    for name, path in results["files"].items():
        print(f"  - {name}: {path}")
    print("=" * 60)
    
    return results


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="OBIE - OSINT Buyer Intent Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --products "plywood,ceramic tiles" --all
  python main.py --products "steel" --tenders --days 14
  python main.py --products "textiles" --b2b --social --no-headless
        """
    )
    
    parser.add_argument(
        "--products",
        required=True,
        help="Comma-separated product keywords (e.g., 'plywood,ceramic tiles,steel')"
    )
    parser.add_argument("--output-dir", default="output", help="Output directory")
    
    # Source selection
    source_group = parser.add_argument_group("Source Selection (default: all)")
    source_group.add_argument("--b2b", action="store_true", help="Scrape B2B boards only")
    source_group.add_argument("--tenders", action="store_true", help="Scrape tender portals only")
    source_group.add_argument("--social", action="store_true", help="Scrape social signals only")
    source_group.add_argument("--all", action="store_true", help="Scrape all sources (default)")
    
    # Options
    parser.add_argument("--days", type=int, default=30, help="Days back for tenders (default: 30)")
    parser.add_argument("--pages", type=int, default=3, help="Pages per B2B site (default: 3)")
    parser.add_argument("--no-headless", action="store_true", help="Show browser windows")
    
    args = parser.parse_args()
    
    # Parse products
    products = [p.strip() for p in args.products.split(',')]
    
    # Determine which sources to run
    if args.b2b or args.tenders or args.social:
        run_b2b = args.b2b
        run_tenders = args.tenders
        run_social = args.social
    else:
        run_b2b = True
        run_tenders = True
        run_social = True
    
    # Run pipeline
    results = asyncio.run(run_full_pipeline(
        product_keywords=products,
        output_dir=args.output_dir,
        run_b2b=run_b2b,
        run_tenders=run_tenders,
        run_social=run_social,
        headless=not args.no_headless,
        days_back=args.days,
        pages_per_site=args.pages
    ))
    
    return results


if __name__ == "__main__":
    main()
