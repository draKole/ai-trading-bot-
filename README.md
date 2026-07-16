# Drake AI Trading

Professional automated futures trading platform — modular, testable, risk-controlled.

**Status:** Phase 0 — Foundation & Architecture  
**Mode:** PAPER (default) | LIVE disabled until explicit owner approval

## Quick Start

```bash
docker-compose up -d
```

Services:
- **Backend API:** http://localhost:8000 (Swagger: http://localhost:8000/docs)
- **Frontend:** http://localhost:5173
- **PostgreSQL+TimescaleDB:** localhost:5432
- **Redis:** localhost:6379

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full system design.

## Development

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Trading Instruments
MNQ · NQ · MES · ES (extensible)

## Risk Management
All trades pass through an independent risk engine with veto power.
Default mode is PAPER. LIVE requires explicit owner approval.

## License
Proprietary. All rights reserved.
