# orbit

Series dating wingman that consumes Kafka events, runs an LLM-driven agent, and replies via the iMessage REST API.

## Setup
Quickstart: `./spool.sh` (creates `.venv`, installs deps, loads `.env`, runs).

1) Create `.env` from `.env.example` and fill secrets (Kafka, Series API, OpenRouter key). The sample uses `https://series-hackathon-service-202642739529.us-east1.run.app` for `SERIES_BASE_URL`; replace if needed.  
2) `pip install -r requirements.txt` (or let `./spool.sh` handle it)  
3) Run consumer: `python -m src.main` (or `INGRESS_MODE=api ./spool.sh` for REST polling)

## Monitor
Lightweight read-only dashboard: `python -m src.monitor` (defaults to http://localhost:8000). Shows users, matches, chats/messages (if SERIES creds provided).

## Notes
- LLM: defaults to OpenRouter `x-ai/grok-4.1-fast`.  
- Persistence: SQLite at `DATABASE_PATH` (default `./orbit.db`).  
- PRD: see `orbitprd.md`.
