"""
Enrichment + Verification Pipeline

Enriches leads with:
- Company profile data
- Contact extraction
- Email verification (MX + SMTP)
- Domain validation
"""
import logging
import re
import socket
import smtplib
from typing import Any, Dict, List, Optional, Tuple

import dns.resolver
import httpx

logger = logging.getLogger(__name__)


class EnrichmentPipeline:
    """
    Enrich buyer and opportunity data.
    """
    
    def __init__(self, mode: str = "standard"):
        """
        Initialize enrichment pipeline.
        
        Args:
            mode: "none", "basic", "standard", "full"
        """
        self.mode = mode
    
    async def enrich_buyer(self, buyer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich buyer entity with additional data.
        
        Args:
            buyer_data: Raw buyer data
        
        Returns:
            Enriched buyer data
        """
        enriched = buyer_data.copy()
        
        # Extract domain from website
        if buyer_data.get("website") and not buyer_data.get("domain"):
            enriched["domain"] = self._extract_domain(buyer_data["website"])
        
        # Fetch company profile if domain available
        if enriched.get("domain") and self.mode in ["standard", "full"]:
            profile = await self._fetch_company_profile(enriched["domain"])
            if profile:
                enriched.update(profile)
        
        return enriched
    
    async def enrich_opportunity(
        self,
        opportunity: Dict[str, Any],
        buyer: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Enrich opportunity with additional context.
        """
        enriched = opportunity.copy()
        
        # Add buyer info if available
        if buyer:
            enriched["buyer_domain"] = buyer.get("domain")
            enriched["buyer_industry"] = buyer.get("industry")
        
        return enriched
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        if not url:
            return None
        
        # Remove protocol
        url = url.replace("http://", "").replace("https://", "")
        
        # Remove path
        domain = url.split("/")[0]
        
        # Remove www.
        domain = domain.replace("www.", "")
        
        # Validate
        if "." in domain and len(domain) > 3:
            return domain.lower()
        
        return None
    
    async def _fetch_company_profile(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Fetch company profile from domain.
        
        Uses web scraping to extract company info.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try homepage
                response = await client.get(f"https://{domain}")
                
                if response.status_code != 200:
                    return None
                
                html = response.text
                
                # Extract basic info
                profile = {}
                
                # Look for company name in title
                import re
                title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
                if title_match:
                    profile["company_name_hint"] = title_match.group(1).strip()[:200]
                
                # Look for industry keywords
                industry_keywords = {
                    "construction": ["construction", "building", "contractor"],
                    "manufacturing": ["manufacturing", "manufacturer", "factory"],
                    "trading": ["trading", "import", "export", "distributor"],
                    "technology": ["technology", "software", "IT", "digital"],
                }
                
                html_lower = html.lower()
                for industry, keywords in industry_keywords.items():
                    if any(kw in html_lower for kw in keywords):
                        profile["industry_hint"] = industry
                        break
                
                return profile
                
        except Exception as e:
            logger.debug(f"Failed to fetch company profile for {domain}: {e}")
            return None


class EmailVerificationPipeline:
    """
    Verify email addresses.
    
    Modes:
    - none: Skip verification
    - basic: Syntax check only
    - mx_only: Syntax + MX record check
    - full: Syntax + MX + SMTP check
    """
    
    # Common email providers
    FREE_EMAIL_PROVIDERS = [
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "aol.com", "icloud.com", "mail.com", "protonmail.com",
    ]
    
    # Role-based emails (less valuable)
    ROLE_EMAILS = [
        "info", "contact", "hello", "support", "sales",
        "admin", "office", "general", "enquiry", "help",
    ]
    
    def __init__(self, mode: str = "mx_only"):
        """
        Initialize email verification.
        
        Args:
            mode: Verification mode (none, basic, mx_only, full)
        """
        self.mode = mode
    
    def verify(self, email: str) -> Dict[str, Any]:
        """
        Verify an email address.
        
        Returns:
            Dict with verification results
        """
        result = {
            "email": email,
            "is_valid": False,
            "status": "unknown",
            "confidence": 0.0,
            "reasons": [],
        }
        
        if not email:
            result["status"] = "empty"
            return result
        
        # 1. Syntax check
        syntax_valid = self._check_syntax(email)
        if not syntax_valid:
            result["status"] = "invalid_syntax"
            result["reasons"].append("Invalid email syntax")
            return result
        
        result["is_valid"] = True
        result["reasons"].append("Valid syntax")
        
        if self.mode == "basic":
            result["status"] = "valid"
            result["confidence"] = 0.5
            return result
        
        # 2. MX record check
        domain = email.split("@")[1]
        mx_records = self._check_mx_records(domain)
        
        if not mx_records:
            result["status"] = "no_mx_records"
            result["confidence"] = 0.3
            result["reasons"].append("No MX records found")
            return result
        
        result["reasons"].append("MX records found")
        
        if self.mode == "mx_only":
            result["status"] = "valid"
            result["confidence"] = 0.8
            return result
        
        # 3. SMTP check (optional, can be slow)
        if self.mode == "full":
            smtp_result = self._check_smtp(email, mx_records[0])
            result.update(smtp_result)
        
        return result
    
    def _check_syntax(self, email: str) -> bool:
        """Check email syntax."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))
    
    def _check_mx_records(self, domain: str) -> List[str]:
        """Check MX records for domain."""
        try:
            records = dns.resolver.resolve(domain, "MX")
            mx_servers = [str(r.exchange).rstrip(".") for r in records]
            mx_servers.sort()  # Sort by priority
            return mx_servers
        except Exception as e:
            logger.debug(f"MX check failed for {domain}: {e}")
            return []
    
    def _check_smtp(self, email: str, mx_server: str) -> Dict[str, Any]:
        """
        Check email via SMTP (without sending).
        
        Note: Many servers don't respond accurately to prevent spam.
        """
        result = {
            "smtp_checked": True,
            "status": "unknown",
            "confidence": 0.5,
        }
        
        try:
            # Connect to MX server
            server = smtplib.SMTP(timeout=10)
            server.set_debuglevel(0)
            
            # Connect
            server.connect(mx_server, 25)
            server.helo("example.com")
            server.mail("verify@example.com")
            
            # Check recipient
            code, message = server.rcpt(email)
            server.quit()
            
            if code == 250:
                result["status"] = "valid"
                result["confidence"] = 0.95
            elif code == 550:
                result["status"] = "invalid"
                result["confidence"] = 0.9
            else:
                result["status"] = "catch_all"
                result["confidence"] = 0.5
                
        except Exception as e:
            logger.debug(f"SMTP check failed for {email}: {e}")
            result["status"] = "smtp_error"
            result["confidence"] = 0.3
        
        return result
    
    def is_role_email(self, email: str) -> bool:
        """Check if email is a role-based address."""
        if not email:
            return False
        
        local_part = email.split("@")[0].lower()
        return local_part in self.ROLE_EMAILS
    
    def is_free_provider(self, email: str) -> bool:
        """Check if email is from a free provider."""
        if not email:
            return False
        
        domain = email.split("@")[1].lower()
        return domain in self.FREE_EMAIL_PROVIDERS
    
    def score_email_quality(self, email: str) -> float:
        """
        Score email quality (0-100).
        
        Higher score = more likely to reach decision maker
        """
        if not email:
            return 0.0
        
        score = 50.0  # Base score
        
        # Role emails are less valuable
        if self.is_role_email(email):
            score -= 20
        
        # Free providers are less valuable for B2B
        if self.is_free_provider(email):
            score -= 15
        
        # Personal name emails are more valuable
        local_part = email.split("@")[0].lower()
        if "." in local_part or "_" in local_part:
            # Likely firstname.lastname format
            score += 10
        
        return max(0, min(100, score))


class ContactExtractionPipeline:
    """
    Extract contacts from web pages.
    """
    
    # Email pattern
    EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    
    # Phone patterns
    PHONE_PATTERNS = [
        r"\+?\d[\d\s\-\(\)]{8,}\d",
        r"\(\d{3}\)\s*\d{3}[-.]?\d{4}",
        r"\d{3}[-.]?\d{3}[-.]?\d{4}",
    ]
    
    def extract_from_html(self, html: str) -> Dict[str, List[str]]:
        """
        Extract contact info from HTML.
        
        Returns:
            Dict with emails and phones lists
        """
        result = {
            "emails": [],
            "phones": [],
        }
        
        if not html:
            return result
        
        # Extract emails
        emails = re.findall(self.EMAIL_PATTERN, html)
        result["emails"] = list(set(emails))[:10]  # Limit to 10 unique
        
        # Extract phones
        for pattern in self.PHONE_PATTERNS:
            phones = re.findall(pattern, html)
            result["phones"].extend(phones)
        
        result["phones"] = list(set(result["phones"]))[:5]  # Limit to 5 unique
        
        return result
    
    async def extract_from_url(self, url: str) -> Dict[str, List[str]]:
        """
        Extract contact info from URL.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    return {"emails": [], "phones": []}
                
                return self.extract_from_html(response.text)
                
        except Exception as e:
            logger.debug(f"Failed to extract from {url}: {e}")
            return {"emails": [], "phones": []}
