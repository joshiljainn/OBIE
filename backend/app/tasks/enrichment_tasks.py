"""
Enrichment Tasks

Celery tasks for lead enrichment.
"""
import logging
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.pipelines.enrichment import EnrichmentPipeline, EmailVerificationPipeline

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def enrich_lead(self, lead_id: int) -> dict:
    """
    Enrich a single lead with contact info.
    
    Args:
        lead_id: Opportunity ID to enrich
    
    Returns:
        Enrichment results
    """
    logger.info(f"Starting enrichment for lead {lead_id}")
    
    try:
        # This would fetch the lead from DB
        # For now, just simulate
        enrichment_pipeline = EnrichmentPipeline(mode="standard")
        
        # Simulated enrichment
        result = {
            "lead_id": lead_id,
            "enriched_at": datetime.utcnow().isoformat(),
            "status": "completed",
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Enrichment failed for lead {lead_id}: {e}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task(bind=True, max_retries=2)
def verify_email(self, email: str) -> dict:
    """
    Verify an email address.
    
    Args:
        email: Email to verify
    
    Returns:
        Verification results
    """
    logger.info(f"Verifying email: {email}")
    
    try:
        verifier = EmailVerificationPipeline(mode="mx_only")
        result = verifier.verify(email)
        
        result["verified_at"] = datetime.utcnow().isoformat()
        
        return result
        
    except Exception as e:
        logger.error(f"Email verification failed for {email}: {e}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task
def batch_enrich(lead_ids: list) -> dict:
    """
    Enrich multiple leads in batch.
    
    Args:
        lead_ids: List of opportunity IDs
    
    Returns:
        Batch enrichment results
    """
    logger.info(f"Starting batch enrichment for {len(lead_ids)} leads")
    
    results = []
    
    for lead_id in lead_ids:
        try:
            result = enrich_lead.delay(lead_id)
            results.append({
                "lead_id": lead_id,
                "task_id": result.id,
                "status": "queued",
            })
        except Exception as e:
            results.append({
                "lead_id": lead_id,
                "error": str(e),
                "status": "failed",
            })
    
    return {
        "batch_id": datetime.utcnow().isoformat(),
        "total": len(lead_ids),
        "results": results,
    }
