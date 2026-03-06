"""
Prometheus Metrics Configuration
"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry


# ─────────────────────────────────────────────────────────────
# Metrics Registry
# ─────────────────────────────────────────────────────────────

registry = CollectorRegistry()


# ─────────────────────────────────────────────────────────────
# Counters (only increase)
# ─────────────────────────────────────────────────────────────

leads_ingested_total = Counter(
    "obie_leads_ingested_total",
    "Total number of leads ingested",
    ["source", "status"],
    registry=registry,
)

leads_scored_total = Counter(
    "obie_leads_scored_total",
    "Total number of leads scored",
    ["tier"],
    registry=registry,
)

api_requests_total = Counter(
    "obie_api_requests_total",
    "Total API requests",
    ["endpoint", "method", "status_code"],
    registry=registry,
)


# ─────────────────────────────────────────────────────────────
# Histograms (distribution of values)
# ─────────────────────────────────────────────────────────────

ingestion_duration = Histogram(
    "obie_ingestion_duration_seconds",
    "Time spent ingesting from sources",
    ["source"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
    registry=registry,
)

api_request_duration = Histogram(
    "obie_api_request_duration_seconds",
    "API request duration",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
    registry=registry,
)


# ─────────────────────────────────────────────────────────────
# Gauges (can go up or down)
# ─────────────────────────────────────────────────────────────

active_sources = Gauge(
    "obie_active_sources",
    "Number of active data sources",
    registry=registry,
)

leads_in_pipeline = Gauge(
    "obie_leads_in_pipeline",
    "Number of leads currently in processing pipeline",
    registry=registry,
)


# ─────────────────────────────────────────────────────────────
# Setup Function
# ─────────────────────────────────────────────────────────────

def setup_metrics(app) -> None:
    """
    Setup metrics middleware for FastAPI app.
    """
    from starlette.middleware import Middleware
    from starlette.requests import Request
    from starlette.responses import Response
    import time
    
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        # Record request duration
        api_request_duration.labels(endpoint=request.url.path).observe(duration)
        
        # Record request count
        api_requests_total.labels(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
        ).inc()
        
        return response
