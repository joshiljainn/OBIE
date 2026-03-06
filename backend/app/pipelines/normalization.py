"""
Normalization Pipeline

Converts raw LeadSignal objects into canonical Opportunity model.
Handles:
- Product normalization
- Location/country parsing
- Quantity parsing
- Budget/currency parsing
- Date parsing
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.adapters.base import LeadSignal

logger = logging.getLogger(__name__)


class NormalizationPipeline:
    """
    Normalizes raw lead signals into canonical format.
    """
    
    # Country name to ISO code mapping (partial, expand as needed)
    COUNTRY_MAP = {
        "united states": "US",
        "usa": "US",
        "america": "US",
        "united kingdom": "GB",
        "uk": "GB",
        "england": "GB",
        "germany": "DE",
        "france": "FR",
        "italy": "IT",
        "spain": "ES",
        "netherlands": "NL",
        "uae": "AE",
        "united arab emirates": "AE",
        "dubai": "AE",
        "saudi arabia": "SA",
        "china": "CN",
        "india": "IN",
        "pakistan": "PK",
        "bangladesh": "BD",
        "vietnam": "VN",
        "thailand": "TH",
        "malaysia": "MY",
        "indonesia": "ID",
        "turkey": "TR",
        "egypt": "EG",
        "nigeria": "NG",
        "kenya": "KE",
        "south africa": "ZA",
        "australia": "AU",
        "canada": "CA",
        "brazil": "BR",
        "mexico": "MX",
        "russia": "RU",
        "poland": "PL",
        "belgium": "BE",
        "austria": "AT",
        "sweden": "SE",
        "norway": "NO",
        "denmark": "DK",
        "finland": "FI",
    }
    
    # Currency symbols to codes
    CURRENCY_MAP = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "¥": "JPY",
        "₹": "INR",
        "د.إ": "AED",
        "﷼": "SAR",
    }
    
    # Quantity unit normalization
    UNIT_MAP = {
        "ton": "tons",
        "tonne": "tons",
        "tonnes": "tons",
        "mt": "tons",
        "metric ton": "tons",
        "kg": "kg",
        "kilogram": "kg",
        "kilograms": "kg",
        "piece": "pieces",
        "pieces": "pieces",
        "pcs": "pieces",
        "unit": "units",
        "units": "units",
        "container": "containers",
        "containers": "containers",
        "box": "boxes",
        "boxes": "boxes",
        "carton": "cartons",
        "cartons": "cartons",
    }
    
    def __init__(self):
        pass
    
    def normalize(self, signal: LeadSignal) -> Dict[str, Any]:
        """
        Normalize a LeadSignal into canonical format.
        
        Returns:
            Dictionary suitable for Opportunity model creation
        """
        normalized = {
            # Basic fields
            "title": self._extract_title(signal),
            "description": signal.description or signal.product_text[:500],
            "buyer_name_raw": signal.buyer_name,
            "buyer_type": self._classify_buyer_type(signal.buyer_type, signal.description),
            
            # Product
            "product_text": signal.product_text,
            "product_normalized": self._normalize_product(signal.product_text),
            
            # Quantity
            "quantity_text": signal.quantity_text,
            "quantity_value": None,
            "quantity_unit": None,
            
            # Budget
            "budget_text": signal.budget_text,
            "budget_value": None,
            "budget_currency": None,
            
            # Location
            "destination_country": None,
            "destination_city": None,
            
            # Timing
            "deadline": self._parse_deadline(signal.deadline_text),
            "published_at": signal.published_at,
            
            # Source
            "source_name": signal.source_name,
            "source_url": signal.source_url,
            "source_reference_id": signal.source_reference_id,
            "raw_payload": str(signal.raw_payload)[:10000] if signal.raw_payload else None,
            
            # Metadata
            "extraction_confidence": signal.extraction_confidence,
        }
        
        # Parse quantity
        if signal.quantity_text:
            qty_value, qty_unit = self._parse_quantity(signal.quantity_text)
            normalized["quantity_value"] = qty_value
            normalized["quantity_unit"] = qty_unit
        
        # Parse budget
        if signal.budget_text:
            budget_value, budget_currency = self._parse_budget(signal.budget_text)
            normalized["budget_value"] = budget_value
            normalized["budget_currency"] = budget_currency
        
        # Parse location
        if signal.location_text:
            country, city = self._parse_location(signal.location_text)
            normalized["destination_country"] = country
            normalized["destination_city"] = city
        
        return normalized
    
    def _extract_title(self, signal: LeadSignal) -> str:
        """Extract/generate title from signal."""
        # Use product text as base
        title = signal.product_text[:200]
        
        # Add buyer name if available
        if signal.buyer_name and signal.buyer_name != "Unknown Buyer":
            title = f"{signal.buyer_name}: {title[:150]}"
        
        return title[:500]
    
    def _classify_buyer_type(self, provided_type: Optional[str], description: Optional[str]) -> str:
        """Classify buyer type from hints."""
        if provided_type:
            return provided_type
        
        text = (description or "").lower()
        
        if "government" in text or "ministry" in text:
            return "Government"
        elif "distributor" in text or "distribution" in text:
            return "Distributor"
        elif "importer" in text or "import" in text:
            return "Importer"
        elif "wholesaler" in text or "wholesale" in text:
            return "Wholesaler"
        elif "retailer" in text or "retail" in text:
            return "Retailer"
        elif "manufacturer" in text or "manufacturing" in text:
            return "Manufacturer"
        
        return "Unknown"
    
    def _normalize_product(self, product_text: str) -> Optional[str]:
        """Normalize product description to category."""
        if not product_text:
            return None
        
        text = product_text.lower()
        
        # Simple keyword-based categorization
        categories = {
            "plywood": ["plywood", "wood panel", "mdf", "particle board"],
            "steel": ["steel", "iron", "metal sheet", "rebar"],
            "textiles": ["fabric", "textile", "yarn", "cotton", "polyester"],
            "ceramics": ["ceramic", "tile", "porcelain"],
            "electronics": ["electronic", "component", "circuit", "semiconductor"],
            "machinery": ["machine", "equipment", "industrial"],
            "chemicals": ["chemical", "polymer", "resin", "plastic"],
            "food": ["food", "agricultural", "grain", "rice", "wheat"],
            "construction": ["construction", "building material", "cement", "concrete"],
        }
        
        for category, keywords in categories.items():
            if any(kw in text for kw in keywords):
                return category.capitalize()
        
        return None
    
    def _parse_quantity(self, quantity_text: str) -> Tuple[Optional[float], Optional[str]]:
        """Parse quantity text into value and unit."""
        if not quantity_text:
            return (None, None)
        
        text = quantity_text.lower()
        
        # Pattern: number + optional unit
        pattern = r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(tons?|tonnes?|mt|kg|kilograms?|pieces?|pcs|units?|containers?|boxes?|cartons?)?"
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            try:
                value_str = match.group(1).replace(",", "")
                value = float(value_str)
                
                unit_raw = match.group(2)
                unit = self.UNIT_MAP.get(unit_raw.lower(), unit_raw) if unit_raw else None
                
                return (value, unit)
            except (ValueError, AttributeError):
                pass
        
        return (None, None)
    
    def _parse_budget(self, budget_text: str) -> Tuple[Optional[float], Optional[str]]:
        """Parse budget text into value and currency."""
        if not budget_text:
            return (None, None)
        
        text = budget_text
        
        # Pattern: currency symbol + number
        pattern = r"([\$€£¥₹د\.إ﷼]?)\s*(\d+(?:,\d{3})*(?:\.\d+)?)(?:\s*(million|billion|mn|bn|m|b))?"
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            try:
                currency_symbol = match.group(1)
                value_str = match.group(2).replace(",", "")
                multiplier = match.group(3)
                
                value = float(value_str)
                
                # Apply multiplier
                if multiplier:
                    mult = multiplier.lower()
                    if mult in ["million", "mn", "m"]:
                        value *= 1_000_000
                    elif mult in ["billion", "bn", "b"]:
                        value *= 1_000_000_000
                
                # Map currency symbol to code
                currency = self.CURRENCY_MAP.get(currency_symbol, "USD") if currency_symbol else "USD"
                
                return (value, currency)
            except (ValueError, AttributeError):
                pass
        
        return (None, None)
    
    def _parse_location(self, location_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse location text into country and city."""
        if not location_text:
            return (None, None)
        
        text = location_text.lower()
        
        # Look for country in map
        for country_name, country_code in self.COUNTRY_MAP.items():
            if country_name in text:
                # Try to extract city (word before country)
                city = None
                city_pattern = rf"(\w+)\s+{country_name}"
                city_match = re.search(city_pattern, text)
                if city_match:
                    city = city_match.group(1).capitalize()
                
                return (country_code, city)
        
        return (None, None)
    
    def _parse_deadline(self, deadline_text: Optional[str]) -> Optional[datetime]:
        """Parse deadline text into datetime."""
        if not deadline_text:
            return None
        
        text = deadline_text.strip()
        
        # Try common date formats
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        
        # Try to extract date from text
        date_pattern = r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})"
        match = re.search(date_pattern, text)
        if match:
            date_str = match.group(1)
            for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        
        return None
