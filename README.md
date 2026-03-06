# OBIE - Export Buyer Intent Engine

**Production-grade B2B buyer discovery, scoring, and outreach platform for exporters.**

---

## 🎯 What This Does

OBIE helps exporters find **active import buyers** with high purchase intent by:

1. **Ingesting** from multiple sources (tenders, B2B boards, trade signals)
2. **Normalizing** into a canonical data model
3. **Scoring** leads with explainable intent algorithms
4. **Enriching** with contact details and verification
5. **Deduplicating** across sources with entity resolution
6. **Surfacing** hot buyers via dashboard, reports, and CRM integrations

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         OBIE Platform                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   B2B Boards │  │   Tenders    │  │ Trade Signals│          │
│  │   Adapter    │  │   Adapter    │  │   Adapter    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┴─────────────────┘                   │
│                           │                                     │
│                  ┌────────▼────────┐                            │
│                  │  Ingestion Queue │ (Redis + Celery)          │
│                  └────────┬────────┘                            │
│                           │                                     │
│         ┌─────────────────┼─────────────────┐                  │
│         │                 │                 │                   │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐            │
│  │  Normalize  │  │   Dedupe    │  │   Enrich    │            │
│  │  Pipeline   │  │   Engine    │  │   Pipeline  │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                 │                 │                   │
│         └─────────────────┼─────────────────┘                   │
│                           │                                     │
│                  ┌────────▼────────┐                            │
│                  │  Intent Scorer  │ (Configurable weights)     │
│                  └────────┬────────┘                            │
│                           │                                     │
│                  ┌────────▼────────┐                            │
│                  │   PostgreSQL    │                            │
│                  │   (Lead Store)  │                            │
│                  └────────┬────────┘                            │
│                           │                                     │
│         ┌─────────────────┼─────────────────┐                  │
│         │                 │                 │                   │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐            │
│  │  FastAPI    │  │  Dashboard  │  │   Reports   │            │
│  │   REST API  │  │   (React)   │  │   Engine    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
obie/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Settings, env vars
│   │   ├── database.py          # DB connection, sessions
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # SQLAlchemy base
│   │   │   ├── buyer.py         # BuyerEntity
│   │   │   ├── opportunity.py   # Opportunity
│   │   │   ├── contact.py       # Contact
│   │   │   ├── intent.py        # IntentScore
│   │   │   └── source.py        # Source, SourceHealth
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── buyer.py         # Pydantic schemas
│   │   │   ├── opportunity.py
│   │   │   ├── contact.py
│   │   │   └── api.py           # Request/Response schemas
│   │   │
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # SourceAdapter interface
│   │   │   ├── b2b_adapter.py   # B2B boards (TradeKey, etc.)
│   │   │   ├── tender_adapter.py# Tenders (TED, SAM.gov)
│   │   │   └── signals_adapter.py# Social/trade signals
│   │   │
│   │   ├── pipelines/
│   │   │   ├── __init__.py
│   │   │   ├── ingestion.py     # Queue ingestion
│   │   │   ├── normalization.py # Canonical model
│   │   │   ├── dedupe.py        # Entity resolution
│   │   │   ├── enrichment.py    # Contact enrichment
│   │   │   └── scoring.py       # Intent scoring
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── leads.py     # Lead CRUD
│   │   │   │   ├── buyers.py    # Buyer entities
│   │   │   │   ├── sources.py   # Source management
│   │   │   │   ├── reports.py   # Reports, exports
│   │   │   │   └── webhooks.py  # CRM webhooks
│   │   │   └── deps.py          # Dependencies
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── lead_service.py  # Lead business logic
│   │   │   ├── crm_service.py   # CRM integrations
│   │   │   └── email_service.py # Email verification
│   │   │
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py    # Celery config
│   │   │   ├── ingestion_tasks.py# Async ingestion
│   │   │   └── enrichment_tasks.py# Async enrichment
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── logging.py       # Structured logging
│   │       ├── metrics.py       # Prometheus metrics
│   │       └── helpers.py       # Utilities
│   │
│   ├── alembic/
│   │   ├── versions/            # DB migrations
│   │   └── env.py
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py          # Test fixtures
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   │
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   └── pytest.ini
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── LeadFeed.tsx
│   │   │   ├── LeadDetail.tsx
│   │   │   ├── SourceHealth.tsx
│   │   │   └── ...
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Leads.tsx
│   │   │   ├── Reports.tsx
│   │   │   └── Settings.tsx
│   │   ├── api/                 # API client
│   │   ├── store/               # Redux/Zustand
│   │   └── App.tsx
│   │
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
│
├── docker-compose.yml           # Local dev stack
├── docker-compose.prod.yml      # Production stack
├── Makefile                     # Common commands
├── .env.example                 # Environment template
└── README.md                    # This file
```

---

## 🚀 Quick Start (Development)

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker + Docker Compose
- Redis (for Celery)
- PostgreSQL 15+

### 1. Clone & Setup

```bash
git clone https://github.com/joshiljainn/OBIE.git
cd OBIE

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Environment Variables

```bash
# Copy example
cp .env.example .env

# Edit with your values:
# - DATABASE_URL
# - REDIS_URL
# - GROQ_API_KEY (for LLM enrichment)
# - SECRET_KEY
```

### 3. Start Services (Docker)

```bash
# From project root
docker-compose up -d  # Starts Postgres, Redis

# Run migrations
cd backend
alembic upgrade head

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery workers
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4

# Start frontend (in another terminal)
cd frontend
npm run dev
```

### 4. Access

- **Dashboard:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Admin (future):** http://localhost:8000/admin

---

## 🔌 Source Adapters

### Built-in Adapters (v1)

| Adapter | Sources | Status |
|---------|---------|--------|
| B2B Boards | TradeKey, go4WorldBusiness, EC21 | 🟡 Beta |
| Tenders | EU TED, SAM.gov, UN GM | 🟡 Beta |
| Trade Signals | Reddit, LinkedIn (public) | 🔴 Limited |

### Add a Custom Adapter

```python
from app.adapters.base import SourceAdapter, LeadSignal

class MyCustomAdapter(SourceAdapter):
    SOURCE_NAME = "my_custom_source"
    
    async def fetch(self, config: dict) -> list[LeadSignal]:
        # Implement fetching logic
        pass
    
    async def parse(self, raw: dict) -> list[LeadSignal]:
        # Implement parsing logic
        pass
```

Register in `app/adapters/__init__.py`.

---

## 📊 Intent Scoring

Scores are calculated with **configurable weights**:

```yaml
# config/scoring_profiles.yaml
textile_exporter:
  weights:
    recency: 0.25
    product_fit: 0.20
    demand_specificity: 0.20
    buyer_reliability: 0.15
    contactability: 0.10
    urgency: 0.10
  
  thresholds:
    S: 85
    A: 70
    B: 50
    C: 0
```

**Score breakdown is stored** for every lead (explainable AI).

---

## 📈 Key Metrics

Track these in the **Source Health** dashboard:

| Metric | Description | Target |
|--------|-------------|--------|
| Source Success Rate | % successful fetches | >95% |
| Parse Yield Rate | % raw → valid leads | >60% |
| Valid Lead Rate | % passing quality checks | >70% |
| Duplicate Rate | % deduped leads | <30% |
| Verification Pass Rate | % emails verified | >50% |
| Lead-to-Meeting Rate | Manual input | Track weekly |

---

## 🔐 Compliance & Ethics

- **GDPR-aware:** Only B2B contact data, deletion API available
- **ToS Respect:** Robots.txt honored, rate limiting enforced
- **No Private Data:** Public sources only, no login bypassing
- **Data Retention:** Configurable (default: 2 years)

---

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit

# Integration tests (requires Docker)
docker-compose -f docker-compose.test.yml up --abort-on-container-exit

# E2E tests
pytest tests/e2e --browser=chromium
```

---

## 📦 Deployment

### Production Stack

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Deploy
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### Environment Variables (Production)

```bash
DATABASE_URL=postgresql://user:pass@db:5432/obie
REDIS_URL=redis://redis:6379/0
SECRET_KEY=<32-char-random>
GROQ_API_KEY=<your-key>
ENV=production
LOG_LEVEL=INFO
```

---

## 🎯 Roadmap

### M1: Foundation (Week 1)
- [x] Architecture design
- [ ] Schema + migrations
- [ ] Adapter interface + 1 working adapter
- [ ] Scoring v1
- [ ] Dashboard basic

### M2: Quality (Week 2)
- [ ] Dedupe/entity resolution
- [ ] Enrichment + verification
- [ ] Source health metrics
- [ ] Reports engine

### M3: Commercial (Week 3)
- [ ] CRM exports (HubSpot, Pipedrive)
- [ ] Outreach assist (email drafts)
- [ ] User scoring profiles
- [ ] Role-based access

### M4: Optimization (Week 4)
- [ ] Precision/recall tuning
- [ ] Performance hardening
- [ ] Documentation
- [ ] Pilot onboarding

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Write tests
4. Submit a PR

---

## 📄 License

MIT License - See LICENSE file

---

## 📞 Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Email: [your-email@example.com]

---

**Built for exporters who need reliable, actionable buyer intelligence—not just noisy lead lists.**
