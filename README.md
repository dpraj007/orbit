# orbit

Series dating wingman that consumes Kafka events, runs an LLM-driven agent, and replies via the iMessage REST API.

## Setup
1) Create `.env` from `.env.example` and fill secrets (Kafka, Series API, OpenRouter key).  
2) `pip install -r requirements.txt`  
3) Run consumer: `python -m src.main`

## Notes
- LLM: defaults to OpenRouter `x-ai/grok-4.1-fast`.  
- Persistence: SQLite at `DATABASE_PATH` (default `./orbit.db`).  
- PRD: see `orbitprd.md`.
