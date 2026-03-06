"""
Tests for Scoring Engine
"""
import pytest
from datetime import datetime, timedelta

from app.pipelines.scoring import IntentScorer, ScoreResult


class TestIntentScorer:
    """Test the intent scoring engine."""
    
    @pytest.fixture
    def scorer(self):
        """Create scorer with test weights."""
        return IntentScorer(
            weights={
                "recency": 0.25,
                "product_fit": 0.20,
                "demand_specificity": 0.20,
                "buyer_reliability": 0.15,
                "contactability": 0.10,
                "urgency": 0.10,
            }
        )
    
    def test_score_high_quality_opportunity(self, scorer):
        """Test scoring a high-quality opportunity."""
        opp = {
            "published_at": datetime.utcnow(),
            "product_normalized": "Plywood",
            "quantity_value": 500,
            "budget_value": 50000,
            "deadline": datetime.utcnow() + timedelta(days=14),
            "destination_country": "AE",
            "buyer_type": "Importer",
            "description": "Looking for 500 tons of plywood CIF Dubai",
            "extraction_confidence": 0.95,
        }
        
        buyer = {
            "verification_status": "verified",
            "reliability_score": 85,
            "source_count": 3,
            "website": "https://example.com",
        }
        
        result = scorer.score(opp, buyer_data=buyer)
        
        assert isinstance(result, ScoreResult)
        assert 0 <= result.score_total <= 100
        assert result.tier in ["S", "A", "B", "C"]
        assert len(result.subscores) == 6
        assert isinstance(result.reason_codes, list)
    
    def test_score_low_quality_opportunity(self, scorer):
        """Test scoring a low-quality opportunity."""
        opp = {
            "published_at": datetime.utcnow() - timedelta(days=60),
            "product_normalized": None,
            "quantity_value": None,
            "budget_value": None,
            "deadline": None,
            "destination_country": None,
            "buyer_type": "Unknown",
            "description": "Need products",
            "extraction_confidence": 0.3,
        }
        
        result = scorer.score(opp)
        
        assert result.score_total < 50
        assert result.tier == "C"
    
    def test_score_urgent_deadline(self, scorer):
        """Test scoring with urgent deadline."""
        opp = {
            "published_at": datetime.utcnow(),
            "product_normalized": "Steel",
            "deadline": datetime.utcnow() + timedelta(days=5),
        }
        
        result = scorer.score(opp)
        
        assert result.subscores["urgency"] >= 80
        assert "urgent_deadline" in result.reason_codes
    
    def test_score_past_deadline(self, scorer):
        """Test scoring with past deadline."""
        opp = {
            "published_at": datetime.utcnow(),
            "product_normalized": "Steel",
            "deadline": datetime.utcnow() - timedelta(days=5),
        }
        
        result = scorer.score(opp)
        
        assert result.subscores["urgency"] < 0
        assert "deadline_passed" in result.reason_codes
    
    def test_score_government_buyer(self, scorer):
        """Test scoring government buyer."""
        opp = {
            "published_at": datetime.utcnow(),
            "product_normalized": "Construction Materials",
            "buyer_type": "Government",
        }
        
        result = scorer.score(opp)
        
        # Government buyers get bonus
        assert result.subscores["buyer_reliability"] >= 65
    
    def test_determine_tier_thresholds(self, scorer):
        """Test tier determination."""
        # S tier
        assert scorer._determine_tier(90) == "S"
        assert scorer._determine_tier(85) == "S"
        
        # A tier
        assert scorer._determine_tier(84) == "A"
        assert scorer._determine_tier(70) == "A"
        
        # B tier
        assert scorer._determine_tier(69) == "B"
        assert scorer._determine_tier(50) == "B"
        
        # C tier
        assert scorer._determine_tier(49) == "C"
        assert scorer._determine_tier(0) == "C"
    
    def test_score_batch(self, scorer):
        """Test batch scoring."""
        opportunities = [
            {
                "published_at": datetime.utcnow(),
                "product_normalized": "Plywood",
            },
            {
                "published_at": datetime.utcnow() - timedelta(days=30),
                "product_normalized": None,
            },
        ]
        
        results = scorer.score_batch(opportunities)
        
        assert len(results) == 2
        assert all(isinstance(r, ScoreResult) for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
