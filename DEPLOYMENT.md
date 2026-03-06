# OBIE Deployment Guide

**Production-grade deployment instructions for the Export Buyer Intent Engine.**

---

## 📋 Prerequisites

- Docker 20+ and Docker Compose 2+
- 4GB+ RAM recommended
- PostgreSQL 15+ (or use Docker)
- Redis 7+ (or use Docker)
- Python 3.11+ (for local development)

---

## 🚀 Quick Start (Development)

### 1. Clone and Setup

```bash
git clone https://github.com/joshiljainn/OBIE.git
cd OBIE
```

### 2. Configure Environment

```bash
# Copy example env file
cp backend/.env.example backend/.env

# Edit with your values (optional for local dev)
nano backend/.env
```

### 3. Start Services

```bash
# Start all services (Postgres, Redis, Backend, Celery)
docker-compose up -d

# Check status
docker-compose ps
```

### 4. Run Migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 5. Verify

```bash
# API health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs

# Celery monitor (Flower)
open http://localhost:5555
```

---

## 🏭 Production Deployment

### 1. Environment Configuration

Create `.env` file with production values:

```bash
# Required
ENV=production
SECRET_KEY=<32-character-random-string>
POSTGRES_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>

# Optional (recommended)
GROQ_API_KEY=<your-groq-key>

# Database
DATABASE_URL=postgresql://obie:<password>@db:5432/obie
```

### 2. Build and Start

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### 3. Verify Production Deploy

```bash
# Health check
curl http://localhost:8000/health

# Check logs
docker-compose -f docker-compose.prod.yml logs -f backend

# Check metrics
curl http://localhost:8000/metrics
```

---

## 📊 Monitoring

### Prometheus Metrics

Metrics are exposed at `/metrics`:

- `obie_leads_ingested_total` - Total leads ingested
- `obie_leads_scored_total` - Total leads scored by tier
- `obie_api_requests_total` - API request count
- `obie_ingestion_duration_seconds` - Ingestion latency
- `obie_active_sources` - Number of active sources

### Celery Monitoring

Flower dashboard at `http://localhost:5555`:

- Task queue status
- Worker health
- Task success/failure rates

### Log Aggregation

Logs are in JSON format for easy aggregation:

```bash
# View backend logs
docker-compose logs -f backend

# View Celery logs
docker-compose logs -f celery_worker

# Export logs
docker-compose logs backend > logs/backend.log
```

---

## 🔧 Configuration

### Scoring Configuration

Edit `backend/.env`:

```ini
# Weights (must sum to ~1.0)
SCORING_RECENCY_WEIGHT=0.25
SCORING_PRODUCT_FIT_WEIGHT=0.20
SCORING_DEMAND_SPECIFICITY_WEIGHT=0.20
SCORING_BUYER_RELIABILITY_WEIGHT=0.15
SCORING_CONTACTABILITY_WEIGHT=0.10
SCORING_URGENCY_WEIGHT=0.10

# Tier thresholds
SCORING_S_TIER_THRESHOLD=85
SCORING_A_TIER_THRESHOLD=70
SCORING_B_TIER_THRESHOLD=50
```

### Rate Limiting

```ini
RATE_LIMIT_PER_MINUTE=60
REQUEST_DELAY=1.0
```

### Email Verification

```ini
# Modes: none, basic, mx_only, full
EMAIL_VERIFICATION_MODE=mx_only
```

---

## 🗄️ Database Management

### Backup

```bash
# PostgreSQL backup
docker-compose exec db pg_dump -U obie obie > backup_$(date +%Y%m%d).sql

# Restore
docker-compose exec -T db psql -U obie obie < backup_20260305.sql
```

### Migrations

```bash
# Create new migration
cd backend
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Reset (WARNING: destructive)
alembic downgrade base && alembic upgrade head
```

---

## 📈 Scaling

### Horizontal Scaling

```yaml
# docker-compose.prod.yml
services:
  backend:
    deploy:
      replicas: 3
  
  celery_worker:
    deploy:
      replicas: 5
```

### Resource Limits

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
```

---

## 🔐 Security Checklist

- [ ] Change all default passwords
- [ ] Set strong `SECRET_KEY`
- [ ] Enable HTTPS (use reverse proxy like nginx/traefik)
- [ ] Restrict database access to internal network only
- [ ] Enable firewall rules
- [ ] Set up regular security updates
- [ ] Configure log retention policy
- [ ] Enable backup encryption

---

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Check if DB is running
docker-compose ps db

# Check DB logs
docker-compose logs db

# Test connection
docker-compose exec backend python -c "from app.database import check_db_health; import asyncio; print(asyncio.run(check_db_health()))"
```

### Celery Worker Issues

```bash
# Check worker status
docker-compose exec backend celery -A app.tasks.celery_app inspect active

# Restart workers
docker-compose restart celery_worker
```

### High Memory Usage

```bash
# Check container stats
docker stats

# Restart if needed
docker-compose restart
```

---

## 📞 Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Check health: `curl http://localhost:8000/health`
3. Check metrics: `curl http://localhost:8000/metrics`

---

## 🎯 Post-Deployment Checklist

- [ ] Health endpoint returns healthy
- [ ] Database migrations applied
- [ ] At least one source configured and active
- [ ] Celery workers running (check Flower)
- [ ] Backups configured
- [ ] Monitoring alerts configured
- [ ] API keys configured (if using)
- [ ] CORS configured for frontend domain

---

**Deployed successfully? Run the demo to verify:**

```bash
python demo.py
```
