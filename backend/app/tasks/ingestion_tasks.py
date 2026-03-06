"""
Ingestion Tasks

Celery tasks for data ingestion from sources.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List

from celery import Task

from app.adapters import B2BAdapter, TenderAdapter, SignalsAdapter
from app.config import settings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


class IngestionTask(Task):
    """Base class for ingestion tasks."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log task failures."""
        logger.error(f"Task {task_id} failed: {exc}")


@celery_app.task(base=IngestionTask, bind=True, max_retries=3)
def ingest_source(self, source_name: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Ingest data from a source.
    
    Args:
        source_name: Name of source to ingest from
        config: Source-specific configuration
    
    Returns:
        Dict with ingestion results
    """
    config = config or {"keywords": ["general"]}
    
    logger.info(f"Starting ingestion from {source_name}")
    
    try:
        # Select adapter based on source
        if source_name == "b2b_boards":
            adapter = B2BAdapter(site="tradekey")
        elif source_name == "tenders":
            adapter = TenderAdapter(portal="ted")
        elif source_name == "trade_signals":
            adapter = SignalsAdapter(signal_type="rss")
        else:
            raise ValueError(f"Unknown source: {source_name}")
        
        # Fetch data
        raw_data = adapter.fetch(config)
        
        # Parse into lead signals
        leads = adapter.parse(raw_data)
        
        logger.info(f"Ingested {len(leads)} leads from {source_name}")
        
        return {
            "success": True,
            "source": source_name,
            "leads_count": len(leads),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Ingestion failed for {source_name}: {e}")
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task
def run_scheduled_ingestion():
    """
    Run scheduled ingestion for all active sources.
    
    Called by Celery Beat on schedule.
    """
    logger.info("Running scheduled ingestion")
    
    sources = [
        {"name": "b2b_boards", "config": {"keywords": ["plywood", "steel", "construction"]}},
        {"name": "tenders", "config": {"keywords": ["construction materials"], "days_back": 7}},
        {"name": "trade_signals", "config": {"keywords": ["procurement"]}},
    ]
    
    results = []
    
    for source in sources:
        try:
            result = ingest_source.delay(source["name"], source["config"])
            results.append({
                "source": source["name"],
                "task_id": result.id,
                "status": "queued",
            })
        except Exception as e:
            results.append({
                "source": source["name"],
                "error": str(e),
                "status": "failed",
            })
    
    return {
        "scheduled_at": datetime.utcnow().isoformat(),
        "sources": results,
    }


@celery_app.task
def generate_daily_summary():
    """
    Generate daily summary report.
    
    Called by Celery Beat daily.
    """
    logger.info("Generating daily summary")
    
    # This would query the database for daily stats
    # For now, just log
    return {
        "report_type": "daily_summary",
        "generated_at": datetime.utcnow().isoformat(),
        "status": "completed",
    }
