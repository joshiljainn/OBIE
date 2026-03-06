# Adapters Package
"""
Source Adapters

Each adapter implements the SourceAdapter interface to fetch and parse
leads from a specific data source (B2B boards, tenders, signals, etc.)
"""

from app.adapters.base import SourceAdapter, LeadSignal
from app.adapters.b2b_adapter import B2BAdapter
from app.adapters.tender_adapter import TenderAdapter
from app.adapters.signals_adapter import SignalsAdapter

__all__ = [
    "SourceAdapter",
    "LeadSignal",
    "B2BAdapter",
    "TenderAdapter",
    "SignalsAdapter",
]
