"""
Intent Scoring Engine

Explainable, configurable scoring for buyer intent.

Scoring factors:
- Recency (when was it published)
- Product fit (how well does it match target products)
- Demand specificity (how clear are the requirements)
- Buyer reliability (verified buyer, history)
- Contactability (contact info available)
- Urgency (deadline proximity)
"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    """Result of intent scoring."""
    
    score_total: float
    tier: str  # S, A, B, C
    subscores: Dict[str, float]
    reason_codes: List[str]
    explain_text: str
    
    def to_dict(self) -> dict:
        return {
            "score_total": self.score_total,
            "tier": self.tier,
            "subscores": self.subscores,
            "reason_codes": self.reason_codes,
            "explain_text": self.explain_text,
        }


class IntentScorer:
    """
    Calculate explainable intent scores for opportunities.
    
    All weights are configurable via settings.
    """
    
    # Reason codes for explainability
    REASON_HIGH_RECENCY = "high_recency"
    REASON_PRODUCT_MATCH = "product_match"
    REASON_SPECIFIC_REQUIREMENTS = "specific_requirements"
    REASON_BUDGET_SPECIFIED = "budget_specified"
    REASON_DEADLINE_SPECIFIED = "deadline_specified"
    REASON_URGENT_DEADLINE = "urgent_deadline"
    REASON_VERIFIED_BUYER = "verified_buyer"
    REASON_CONTACT_AVAILABLE = "contact_available"
    REASON_GOVERNMENT_BUYER = "government_buyer"
    REASON_DEADLINE_PASSED = "deadline_passed"
    REASON_LOW_CONFIDENCE = "low_confidence"
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        tier_thresholds: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize scorer with configurable weights.
        
        Args:
            weights: Dict of factor weights (must sum to ~1.0)
            tier_thresholds: Dict of tier name -> minimum score
        """
        self.weights = weights or settings.scoring_weights
        self.tier_thresholds = tier_thresholds or {
            "S": settings.scoring_s_tier_threshold,
            "A": settings.scoring_a_tier_threshold,
            "B": settings.scoring_b_tier_threshold,
        }
    
    def score(
        self,
        opportunity_data: Dict[str, Any],
        buyer_data: Optional[Dict[str, Any]] = None,
        contact_data: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        """
        Calculate intent score for an opportunity.
        
        Args:
            opportunity_data: Normalized opportunity data
            buyer_data: Optional buyer entity data
            contact_data: Optional contact data
        
        Returns:
            ScoreResult with total score, tier, and explanations
        """
        subscores = {}
        reasons = []
        
        # ─────────────────────────────────────────────────────
        # 1. Recency Score (0-100)
        # ─────────────────────────────────────────────────────
        recency_score = self._score_recency(opportunity_data)
        subscores["recency"] = recency_score
        
        if recency_score >= 80:
            reasons.append(self.REASON_HIGH_RECENCY)
        
        # ─────────────────────────────────────────────────────
        # 2. Product Fit Score (0-100)
        # ─────────────────────────────────────────────────────
        product_score = self._score_product_fit(opportunity_data)
        subscores["product_fit"] = product_score
        
        if product_score >= 70:
            reasons.append(self.REASON_PRODUCT_MATCH)
        
        # ─────────────────────────────────────────────────────
        # 3. Demand Specificity Score (0-100)
        # ─────────────────────────────────────────────────────
        specificity_score = self._score_demand_specificity(opportunity_data)
        subscores["demand_specificity"] = specificity_score
        
        if specificity_score >= 70:
            reasons.append(self.REASON_SPECIFIC_REQUIREMENTS)
        
        # ─────────────────────────────────────────────────────
        # 4. Buyer Reliability Score (0-100)
        # ─────────────────────────────────────────────────────
        buyer_score = self._score_buyer_reliability(opportunity_data, buyer_data)
        subscores["buyer_reliability"] = buyer_score
        
        if buyer_score >= 80:
            reasons.append(self.REASON_VERIFIED_BUYER)
        
        # ─────────────────────────────────────────────────────
        # 5. Contactability Score (0-100)
        # ─────────────────────────────────────────────────────
        contact_score = self._score_contactability(opportunity_data, contact_data)
        subscores["contactability"] = contact_score
        
        if contact_score >= 50:
            reasons.append(self.REASON_CONTACT_AVAILABLE)
        
        # ─────────────────────────────────────────────────────
        # 6. Urgency Score (0-100)
        # ─────────────────────────────────────────────────────
        urgency_score = self._score_urgency(opportunity_data)
        subscores["urgency"] = urgency_score
        
        if urgency_score >= 80:
            reasons.append(self.REASON_URGENT_DEADLINE)
        elif urgency_score < 0:
            reasons.append(self.REASON_DEADLINE_PASSED)
        
        # ─────────────────────────────────────────────────────
        # Calculate Weighted Total
        # ─────────────────────────────────────────────────────
        total_score = (
            recency_score * self.weights.get("recency", 0.25) +
            product_score * self.weights.get("product_fit", 0.20) +
            specificity_score * self.weights.get("demand_specificity", 0.20) +
            buyer_score * self.weights.get("buyer_reliability", 0.15) +
            contact_score * self.weights.get("contactability", 0.10) +
            urgency_score * self.weights.get("urgency", 0.10)
        )
        
        # Apply bonuses
        bonuses = self._calculate_bonuses(opportunity_data, buyer_data)
        total_score += bonuses
        
        # Clamp to 0-100
        total_score = max(0, min(100, total_score))
        
        # ─────────────────────────────────────────────────────
        # Determine Tier
        # ─────────────────────────────────────────────────────
        tier = self._determine_tier(total_score)
        
        # ─────────────────────────────────────────────────────
        # Generate Explanation
        # ─────────────────────────────────────────────────────
        explain_text = self._generate_explanation(
            total_score, tier, subscores, reasons
        )
        
        return ScoreResult(
            score_total=round(total_score, 2),
            tier=tier,
            subscores=subscores,
            reason_codes=reasons,
            explain_text=explain_text,
        )
    
    def _score_recency(self, opp: Dict[str, Any]) -> float:
        """Score based on how recent the opportunity is."""
        published_at = opp.get("published_at")
        created_at = opp.get("created_at") or datetime.utcnow()
        
        # Use created_at if published_at not available
        reference_date = published_at or created_at
        
        if isinstance(reference_date, datetime):
            days_old = (datetime.utcnow() - reference_date).days
        else:
            days_old = 30  # Default if can't parse
        
        # Score decay: 100 at 0 days, 50 at 7 days, 0 at 30+ days
        if days_old <= 0:
            return 100
        elif days_old <= 3:
            return 90
        elif days_old <= 7:
            return 75
        elif days_old <= 14:
            return 60
        elif days_old <= 30:
            return 40
        else:
            return 20
    
    def _score_product_fit(self, opp: Dict[str, Any]) -> float:
        """Score based on product match quality."""
        score = 50  # Base score
        
        # Has normalized product category
        if opp.get("product_normalized"):
            score += 20
        
        # Has HS codes
        if opp.get("hs_codes"):
            score += 15
        
        # Has quantity specified
        if opp.get("quantity_value"):
            score += 15
        
        # Has incoterm
        if opp.get("incoterm"):
            score += 10
        
        return min(100, score)
    
    def _score_demand_specificity(self, opp: Dict[str, Any]) -> float:
        """Score based on how specific the requirements are."""
        score = 40  # Base score
        
        # Has description
        if opp.get("description") and len(opp.get("description", "")) > 100:
            score += 15
        
        # Has budget
        if opp.get("budget_value"):
            score += 20
        
        # Has deadline
        if opp.get("deadline"):
            score += 15
        
        # Has destination country
        if opp.get("destination_country"):
            score += 10
        
        # Has quantity
        if opp.get("quantity_value"):
            score += 10
        
        return min(100, score)
    
    def _score_buyer_reliability(
        self,
        opp: Dict[str, Any],
        buyer: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Score based on buyer reliability indicators."""
        score = 50  # Base score
        
        if buyer:
            # Verified buyer
            if buyer.get("verification_status") == "verified":
                score += 25
            
            # Has reliability score
            reliability = buyer.get("reliability_score", 0)
            if reliability:
                score += (reliability / 4)  # Max 25 points
            
            # Multiple sources
            if buyer.get("source_count", 1) > 1:
                score += 10
            
            # Has website
            if buyer.get("website"):
                score += 5
        
        # Government buyer bonus
        buyer_type = opp.get("buyer_type", "")
        if buyer_type and "government" in buyer_type.lower():
            score += 15
        
        return min(100, score)
    
    def _score_contactability(
        self,
        opp: Dict[str, Any],
        contact: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Score based on contact information availability."""
        score = 40  # Base score
        
        if contact:
            # Has email
            if contact.get("email"):
                score += 25
            
            # Email verified
            if contact.get("email_verified"):
                score += 15
            
            # Has phone
            if contact.get("phone"):
                score += 15
            
            # Has LinkedIn
            if contact.get("linkedin_url"):
                score += 10
        
        return min(100, score)
    
    def _score_urgency(self, opp: Dict[str, Any]) -> float:
        """Score based on deadline urgency."""
        deadline = opp.get("deadline")
        
        if not deadline:
            return 50  # Neutral if no deadline
        
        if isinstance(deadline, datetime):
            days_until = (deadline - datetime.utcnow()).days
        else:
            return 50  # Can't parse
        
        if days_until < 0:
            return -20  # Penalty for past deadline
        elif days_until <= 7:
            return 100  # Very urgent
        elif days_until <= 14:
            return 85
        elif days_until <= 30:
            return 70
        elif days_until <= 60:
            return 50
        else:
            return 30  # Not urgent
    
    def _calculate_bonuses(
        self,
        opp: Dict[str, Any],
        buyer: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate bonus points for special factors."""
        bonus = 0
        
        # Government buyer multiplier effect
        buyer_type = opp.get("buyer_type", "")
        if buyer_type and "government" in buyer_type.lower():
            bonus += 10
        
        # High confidence extraction
        if opp.get("extraction_confidence", 0) >= 0.9:
            bonus += 5
        
        return bonus
    
    def _determine_tier(self, score: float) -> str:
        """Determine tier based on score."""
        if score >= self.tier_thresholds["S"]:
            return "S"
        elif score >= self.tier_thresholds["A"]:
            return "A"
        elif score >= self.tier_thresholds["B"]:
            return "B"
        else:
            return "C"
    
    def _generate_explanation(
        self,
        score: float,
        tier: str,
        subscores: Dict[str, float],
        reasons: List[str],
    ) -> str:
        """Generate human-readable explanation."""
        parts = []
        
        # Tier summary
        tier_descriptions = {
            "S": "Priority lead - act immediately",
            "A": "High-quality lead - prioritize outreach",
            "B": "Medium-quality lead - worth pursuing",
            "C": "Low-quality lead - nurture or discard",
        }
        parts.append(tier_descriptions.get(tier, ""))
        
        # Top factors
        if reasons:
            reason_texts = {
                self.REASON_HIGH_RECENCY: "Very recent opportunity",
                self.REASON_PRODUCT_MATCH: "Clear product match",
                self.REASON_SPECIFIC_REQUIREMENTS: "Specific requirements defined",
                self.REASON_BUDGET_SPECIFIED: "Budget specified",
                self.REASON_DEADLINE_SPECIFIED: "Deadline specified",
                self.REASON_URGENT_DEADLINE: "Urgent deadline",
                self.REASON_VERIFIED_BUYER: "Verified buyer",
                self.REASON_CONTACT_AVAILABLE: "Contact information available",
                self.REASON_GOVERNMENT_BUYER: "Government buyer",
            }
            
            positive_reasons = [
                reason_texts.get(r, r)
                for r in reasons
                if r != self.REASON_DEADLINE_PASSED
            ]
            
            if positive_reasons:
                parts.append("Positive factors: " + ", ".join(positive_reasons[:4]))
        
        return ". ".join(parts)
    
    def score_batch(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> List[ScoreResult]:
        """Score multiple opportunities efficiently."""
        return [self.score(opp) for opp in opportunities]
