#!/usr/bin/env python3
"""
OBIE Demo Script

Run this script to demonstrate the OBIE pipeline with sample data.
This creates demo leads and shows the scoring system in action.
"""
import asyncio
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, "backend")

from app.pipelines.normalization import NormalizationPipeline
from app.pipelines.scoring import IntentScorer, ScoreResult
from app.pipelines.dedupe import DedupePipeline
from app.adapters.base import LeadSignal


def create_sample_leads():
    """Create sample lead signals for demo."""
    
    leads = [
        # High-quality tender lead
        LeadSignal(
            source_name="ted",
            source_url="https://ted.europa.eu/notice/123456",
            buyer_name="Ministry of Infrastructure - UAE",
            buyer_type="Government",
            product_text="500 tons of construction-grade plywood sheets",
            quantity_text="500 tons",
            location_text="Dubai, UAE",
            budget_text="AED 2,500,000",
            deadline_text=(datetime.utcnow() + timedelta(days=21)).strftime("%Y-%m-%d"),
            published_at=datetime.utcnow() - timedelta(days=2),
            description="Government tender for construction plywood supply",
            extraction_confidence=0.95,
        ),
        
        # Medium-quality B2B lead
        LeadSignal(
            source_name="tradekey",
            source_url="https://www.tradekey.com/buying-leads/789",
            buyer_name="Al Rashid Trading LLC",
            buyer_type="Importer",
            product_text="Need plywood sheets for furniture manufacturing",
            quantity_text="200 pieces",
            location_text="Abu Dhabi",
            budget_text=None,
            deadline_text=None,
            published_at=datetime.utcnow() - timedelta(days=5),
            description="Looking for regular supplier of plywood",
            extraction_confidence=0.8,
        ),
        
        # Low-quality social signal
        LeadSignal(
            source_name="reddit",
            source_url="https://reddit.com/r/procurement/comments/abc",
            buyer_name="u/DubaiBuilder",
            buyer_type="Private",
            product_text="Looking for supplier recommendations",
            quantity_text=None,
            location_text=None,
            budget_text=None,
            deadline_text=None,
            published_at=datetime.utcnow() - timedelta(days=15),
            description="Anyone know good plywood suppliers?",
            extraction_confidence=0.4,
        ),
        
        # High-quality B2B with deadline
        LeadSignal(
            source_name="go4worldbusiness",
            source_url="https://www.go4worldbusiness.com/buyers/xyz",
            buyer_name="Emirates Construction Materials",
            buyer_type="Distributor",
            product_text="Steel rebar for construction project",
            quantity_text="1000 tons",
            location_text="Sharjah, UAE",
            budget_text="$800,000",
            deadline_text=(datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%d"),
            published_at=datetime.utcnow() - timedelta(days=1),
            description="Urgent requirement for steel rebar",
            extraction_confidence=0.9,
        ),
    ]
    
    return leads


def demo_pipeline():
    """Run the demo pipeline."""
    
    print("=" * 70)
    print("OBIE - Export Buyer Intent Engine")
    print("Demo Pipeline")
    print("=" * 70)
    print()
    
    # Create sample leads
    print("📥 Creating sample leads...")
    leads = create_sample_leads()
    print(f"   Created {len(leads)} sample leads")
    print()
    
    # Normalize
    print("🔄 Normalizing leads...")
    normalizer = NormalizationPipeline()
    normalized_leads = []
    
    for lead in leads:
        normalized = normalizer.normalize(lead)
        normalized_leads.append(normalized)
    
    print(f"   Normalized {len(normalized_leads)} leads")
    print()
    
    # Score
    print("📊 Scoring leads...")
    scorer = IntentScorer()
    scored_leads = []
    
    for opp in normalized_leads:
        result = scorer.score(opp)
        opp["intent_score"] = result.score_total
        opp["intent_tier"] = result.tier
        opp["score_breakdown"] = result.to_dict()
        scored_leads.append(opp)
    
    # Sort by score
    scored_leads.sort(key=lambda x: x["intent_score"], reverse=True)
    
    print(f"   Scored {len(scored_leads)} leads")
    print()
    
    # Dedupe
    print("🔍 Checking for duplicates...")
    dedupe = DedupePipeline()
    unique, duplicates = dedupe.find_exact_duplicates(scored_leads)
    print(f"   Unique: {len(unique)}, Duplicates: {len(duplicates)}")
    print()
    
    # Display results
    print("=" * 70)
    print("RESULTS - Scored Leads")
    print("=" * 70)
    print()
    
    for i, lead in enumerate(scored_leads, 1):
        tier_emoji = {"S": "🔥", "A": "⭐", "B": "📋", "C": "📝"}
        emoji = tier_emoji.get(lead["intent_tier"], "📄")
        
        print(f"{emoji} Lead #{i}: {lead['title'][:60]}...")
        print(f"   Tier: {lead['intent_tier']} | Score: {lead['intent_score']:.1f}")
        print(f"   Buyer: {lead['buyer_name_raw']}")
        print(f"   Source: {lead['source_name']}")
        
        if lead.get("score_breakdown"):
            breakdown = lead["score_breakdown"]
            print(f"   Why: {breakdown['explain_text'][:100]}")
        
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    tier_counts = {"S": 0, "A": 0, "B": 0, "C": 0}
    for lead in scored_leads:
        tier_counts[lead["intent_tier"]] += 1
    
    print(f"Total Leads: {len(scored_leads)}")
    print(f"  S Tier (Priority): {tier_counts['S']}")
    print(f"  A Tier (High):     {tier_counts['A']}")
    print(f"  B Tier (Medium):   {tier_counts['B']}")
    print(f"  C Tier (Low):      {tier_counts['C']}")
    print()
    
    # Top recommendation
    if scored_leads:
        top = scored_leads[0]
        print(f"🏆 TOP LEAD: {top['buyer_name_raw']}")
        print(f"   Product: {top['product_text'][:80]}")
        print(f"   Score: {top['intent_score']:.1f} ({top['intent_tier']} Tier)")
        print(f"   Action: Contact immediately!")
    
    print()
    print("=" * 70)
    print("Demo complete!")
    print()
    print("To run the full system:")
    print("  1. docker-compose up -d")
    print("  2. cd backend && alembic upgrade head")
    print("  3. Open http://localhost:8000/docs for API")
    print("=" * 70)


if __name__ == "__main__":
    demo_pipeline()
