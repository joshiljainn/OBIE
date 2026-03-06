"""
Dedupe + Entity Resolution Pipeline

Handles:
- URL-based exact deduplication
- Fuzzy company name matching
- Domain + location + product contextual merge
- Maintains merge history and provenance
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class DedupePipeline:
    """
    Deduplicate leads and resolve buyer entities.
    """
    
    def __init__(self, fuzzy_threshold: float = 0.85):
        """
        Initialize dedupe pipeline.
        
        Args:
            fuzzy_threshold: Threshold for fuzzy matching (0-1)
        """
        self.fuzzy_threshold = fuzzy_threshold
    
    def generate_dedupe_key(self, opportunity: Dict[str, Any]) -> str:
        """
        Generate deterministic dedupe key for exact matching.
        
        Uses: source_url (most reliable unique identifier)
        """
        source_url = opportunity.get("source_url", "").strip().lower()
        
        if not source_url:
            # Fallback to composite key
            composite = f"{opportunity.get('buyer_name_raw', '')}|{opportunity.get('product_text', '')}|{opportunity.get('source_name', '')}"
            return hashlib.md5(composite.encode()).hexdigest()
        
        return hashlib.md5(source_url.encode()).hexdigest()
    
    def find_exact_duplicates(
        self,
        opportunities: List[Dict[str, Any]],
        existing_keys: Set[str] = None,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Find exact duplicates using dedupe keys.
        
        Args:
            opportunities: List of opportunity dicts
            existing_keys: Set of existing dedupe keys to check against
        
        Returns:
            Tuple of (unique_opportunities, duplicate_opportunities)
        """
        seen_keys = existing_keys or set()
        unique = []
        duplicates = []
        
        for opp in opportunities:
            dedupe_key = self.generate_dedupe_key(opp)
            
            if dedupe_key in seen_keys:
                duplicates.append(opp)
                logger.debug(f"Duplicate found: {dedupe_key}")
            else:
                seen_keys.add(dedupe_key)
                unique.append(opp)
        
        return (unique, duplicates)
    
    def find_fuzzy_duplicates(
        self,
        new_opportunity: Dict[str, Any],
        existing_opportunities: List[Dict[str, Any]],
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find fuzzy duplicates using similarity scoring.
        
        Compares:
        - Buyer name (fuzzy)
        - Product (fuzzy)
        - Location (exact)
        - Domain (exact if available)
        
        Args:
            new_opportunity: New opportunity to check
            existing_opportunities: Existing opportunities to compare against
        
        Returns:
            List of (existing_opp, similarity_score) tuples above threshold
        """
        matches = []
        
        for existing in existing_opportunities:
            similarity = self._calculate_similarity(new_opportunity, existing)
            
            if similarity >= self.fuzzy_threshold:
                matches.append((existing, similarity))
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches
    
    def _calculate_similarity(
        self,
        opp1: Dict[str, Any],
        opp2: Dict[str, Any],
    ) -> float:
        """
        Calculate similarity score between two opportunities.
        
        Returns:
            Similarity score 0-1
        """
        scores = []
        weights = []
        
        # 1. Buyer name similarity (fuzzy)
        buyer1 = opp1.get("buyer_name_raw", "").lower()
        buyer2 = opp2.get("buyer_name_raw", "").lower()
        
        if buyer1 and buyer2:
            buyer_similarity = self._string_similarity(buyer1, buyer2)
            scores.append(buyer_similarity)
            weights.append(0.4)  # 40% weight
        
        # 2. Product similarity
        product1 = opp1.get("product_normalized") or opp1.get("product_text", "").lower()
        product2 = opp2.get("product_normalized") or opp2.get("product_text", "").lower()
        
        if product1 and product2:
            if product1 == product2:
                product_sim = 1.0
            else:
                product_sim = self._string_similarity(product1, product2)
            scores.append(product_sim)
            weights.append(0.3)  # 30% weight
        
        # 3. Location match (exact)
        location1 = opp1.get("destination_country")
        location2 = opp2.get("destination_country")
        
        if location1 and location2:
            location_sim = 1.0 if location1 == location2 else 0.0
            scores.append(location_sim)
            weights.append(0.2)  # 20% weight
        
        # 4. Domain match (exact, if available)
        domain1 = opp1.get("domain")
        domain2 = opp2.get("domain")
        
        if domain1 and domain2:
            domain_sim = 1.0 if domain1 == domain2 else 0.0
            scores.append(domain_sim)
            weights.append(0.1)  # 10% weight
        
        # Calculate weighted average
        if not scores:
            return 0.0
        
        total_weight = sum(weights[:len(scores)])
        weighted_sum = sum(s * w for s, w in zip(scores, weights[:len(scores)]))
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate string similarity using Levenshtein-based approach.
        
        Returns:
            Similarity score 0-1
        """
        if not s1 or not s2:
            return 0.0
        
        # Simple approach: use Python's difflib
        import difflib
        return difflib.SequenceMatcher(None, s1, s2).ratio()
    
    def resolve_entity(
        self,
        opportunity: Dict[str, Any],
        existing_buyers: List[Dict[str, Any]],
    ) -> Tuple[Optional[int], str, List[str]]:
        """
        Resolve opportunity to existing buyer entity or create new.
        
        Args:
            opportunity: Opportunity dict
            existing_buyers: List of existing buyer entities
        
        Returns:
            Tuple of (buyer_id, action, reasons)
            - buyer_id: Existing buyer ID if matched, None if new
            - action: 'match', 'create', or 'merge'
            - reasons: List of reason codes
        """
        reasons = []
        
        # 1. Try exact domain match first
        opp_domain = opportunity.get("domain")
        if opp_domain:
            for buyer in existing_buyers:
                if buyer.get("domain") == opp_domain:
                    reasons.append(f"domain_match:{opp_domain}")
                    return (buyer.get("id"), "match", reasons)
        
        # 2. Try fuzzy buyer name match
        opp_buyer = opportunity.get("buyer_name_raw", "").lower()
        
        for buyer in existing_buyers:
            existing_names = [buyer.get("legal_name", "").lower()]
            
            # Add aliases
            import json
            aliases = buyer.get("aliases", "[]")
            try:
                existing_names.extend(json.loads(aliases))
            except:
                pass
            
            for existing_name in existing_names:
                if existing_name:
                    similarity = self._string_similarity(opp_buyer, existing_name)
                    
                    if similarity >= self.fuzzy_threshold:
                        reasons.append(f"name_similarity:{similarity:.2f}")
                        return (buyer.get("id"), "match", reasons)
        
        # 3. No match - create new
        reasons.append("no_matching_buyer")
        return (None, "create", reasons)


class EntityResolutionPipeline:
    """
    Advanced entity resolution for merging buyer records.
    """
    
    def __init__(self):
        self.dedupe = DedupePipeline()
    
    def merge_buyers(
        self,
        buyer1: Dict[str, Any],
        buyer2: Dict[str, Any],
        confidence: float,
    ) -> Dict[str, Any]:
        """
        Merge two buyer entities into one.
        
        Args:
            buyer1: First buyer (primary)
            buyer2: Second buyer (to merge into primary)
            confidence: Merge confidence score
        
        Returns:
            Merged buyer dict
        """
        import json
        from datetime import datetime
        
        merged = buyer1.copy()
        
        # Merge aliases
        existing_aliases = set()
        if buyer1.get("aliases"):
            try:
                existing_aliases.update(json.loads(buyer1["aliases"]))
            except:
                pass
        
        # Add second buyer's name as alias
        if buyer2.get("legal_name"):
            existing_aliases.add(buyer2["legal_name"])
        
        # Add second buyer's aliases
        if buyer2.get("aliases"):
            try:
                existing_aliases.update(json.loads(buyer2["aliases"]))
            except:
                pass
        
        merged["aliases"] = json.dumps(list(existing_aliases))
        
        # Merge source count
        merged["source_count"] = buyer1.get("source_count", 1) + buyer2.get("source_count", 1)
        
        # Update reliability score (weighted average)
        score1 = buyer1.get("reliability_score", 0) or 0
        score2 = buyer2.get("reliability_score", 0) or 0
        merged["reliability_score"] = (score1 + score2) / 2
        
        # Keep most complete contact info
        for field in ["website", "email", "phone", "linkedin_url", "address"]:
            if not merged.get(field) and buyer2.get(field):
                merged[field] = buyer2[field]
        
        # Update timestamps
        merged["merged_at"] = datetime.utcnow().isoformat()
        merged["merge_confidence"] = confidence
        
        return merged
    
    def get_merge_recommendations(
        self,
        buyers: List[Dict[str, Any]],
    ) -> List[Tuple[int, int, float, List[str]]]:
        """
        Find potential buyer merges.
        
        Args:
            buyers: List of buyer entities
        
        Returns:
            List of (buyer1_id, buyer2_id, confidence, reasons) tuples
        """
        recommendations = []
        
        for i, buyer1 in enumerate(buyers):
            for buyer2 in buyers[i+1:]:
                # Skip if already same
                if buyer1.get("id") == buyer2.get("id"):
                    continue
                
                # Calculate similarity
                similarity = self.dedupe._calculate_similarity(
                    {"buyer_name_raw": buyer1.get("legal_name", "")},
                    {"buyer_name_raw": buyer2.get("legal_name", "")},
                )
                
                # Check domain match
                if buyer1.get("domain") and buyer2.get("domain"):
                    if buyer1["domain"] == buyer2["domain"]:
                        similarity = max(similarity, 0.95)
                
                if similarity >= 0.75:  # Lower threshold for recommendations
                    reasons = [f"similarity:{similarity:.2f}"]
                    recommendations.append((
                        buyer1.get("id"),
                        buyer2.get("id"),
                        similarity,
                        reasons,
                    ))
        
        # Sort by confidence
        recommendations.sort(key=lambda x: x[2], reverse=True)
        
        return recommendations
