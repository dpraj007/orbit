# Orbit - AI Dating Wingman

A LangGraph-based dating AI agent that consumes messages via Kafka, processes through an intent-driven graph, stores profiles in SQLite with natural language summaries, and responds via the iMessage REST API.

## Architecture

Orbit uses a sophisticated **LangGraph state machine** with the following flow:

```
┌─────────────┐
│   Kafka     │
│  Consumer   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│              LangGraph Agent Pipeline                    │
├─────────────────────────────────────────────────────────┤
│  load_context → classify_intent → [nodes] → respond    │
│                                                          │
│  Nodes:                                                  │
│  • Onboarding - Natural language profile building       │
│  • Matching - Bilateral LLM-based compatibility scoring │
│  • Mentor - Dating advice (icebreakers, prep, debrief)  │
│  • General - Fallback handler                           │
└─────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐      ┌─────────────┐
│  SQLite DB  │      │  Series API │
│  (profiles, │      │  (iMessage) │
│   matches)  │      └─────────────┘
└─────────────┘
```

## Project Structure

```
orbit/
├── src/
│   ├── kafka/              # Kafka consumer and schemas
│   │   ├── consumer.py     # Kafka consumer setup
│   │   └── schemas.py      # Pydantic message models
│   │
│   ├── api/                # Series iMessage API client
│   │   ├── client.py       # API wrapper with retry logic
│   │   └── models.py       # Request/response models
│   │
│   ├── db/                 # Database layer
│   │   ├── database.py     # SQLite connection & schema
│   │   ├── models.py       # Data models
│   │   └── queries.py      # CRUD operations
│   │
│   ├── agent/              # LangGraph agent
│   │   ├── graph.py        # Graph definition & compilation
│   │   ├── state.py        # State schema (TypedDict)
│   │   ├── router.py       # Intent classification & routing
│   │   └── nodes/          # Processing nodes
│   │       ├── onboarding.py   # Profile building
│   │       ├── matching.py     # Bilateral matching
│   │       └── mentor.py       # Dating guidance
│   │
│   ├── prompts/            # LLM prompts
│   │   ├── router.py       # Intent classification
│   │   ├── onboarding.py   # Profile extraction
│   │   ├── matcher.py      # Compatibility scoring
│   │   └── mentor.py       # Guidance prompts
│   │
│   ├── utils/              # Utilities
│   │   ├── llm.py          # LLM client (OpenRouter)
│   │   └── (helpers)
│   │
│   ├── config.py           # Configuration
│   └── main.py             # Entry point
│
├── docs/                   # Documentation
│   ├── implementation_plan.md
│   └── product_design_spec.md
│
├── requirements.txt
└── .env.example
```

## Features

### ✅ Implemented

1. **LangGraph State Machine**
   - Sophisticated agent flow with conditional routing
   - Intent classification based on user status
   - Modular node architecture

2. **Natural Language Profile Building**
   - 7-step onboarding questionnaire
   - Extracts: name, relationship goals, interests, communication style, dealbreakers
   - Builds natural language summaries (not rigid JSON fields)

3. **Bilateral LLM-Based Matching**
   - Calculates compatibility using LLM scoring in both directions
   - Uses geometric mean: `sqrt(score_a_to_b * score_b_to_a)`
   - Ensures mutual value, not one-sided attraction
   - Generates personalized, anonymized match pitches

4. **Double Opt-In Flow**
   - Both users must say "yes" before introduction
   - Tracks match state (pending_a, pending_b, mutual, rejected)
   - Creates group chat on mutual match

5. **AI Mentor Modes**
   - **Icebreaker**: Generates 3 conversation starters
   - **Continuation**: Helps unstuck conversations
   - **Pre-Date Prep**: Provides date preparation advice
   - **Post-Date Debrief**: Processes date experiences
   - **Recovery**: Supports through rejection/ghosting

6. **Complete Database Schema**
   - `users` - User accounts
   - `profiles` - Natural language profiles with completeness scoring
   - `matches` - Bilateral matches with scores
   - `conversation_state` - Agent flow tracking

7. **Production-Ready Infrastructure**
   - Kafka consumer with auto-commit
   - API retry logic with exponential backoff
   - Comprehensive error handling
   - Logging throughout

## Setup
Quickstart: `./spool.sh` (creates `.venv`, installs deps, loads `.env`, runs).

1) Create `.env` from `.env.example` and fill secrets (Kafka, Series API, OpenRouter key). The sample uses `https://series-hackathon-service-202642739529.us-east1.run.app` for `SERIES_BASE_URL`; replace if needed.  
2) `pip install -r requirements.txt` (or let `./spool.sh` handle it)  
3) Run consumer: `python -m src.main` (or `INGRESS_MODE=api ./spool.sh` for REST polling)

### Fastlane demo (Leon ↔ Dhairyasheel intro)
- Set `OPENROUTER_API_KEY` (and optionally `OPENAI_API_KEY` if you prefer) plus Series API creds.
- Run `python -m src.fastlane` to auto-DM Leon, collect a reply, ask for an intro, assume Dhairyasheel says yes, create a group chat, and interject on @Orbit in the group. Uses typing indicators and Grok via OpenRouter.

## Monitor
Lightweight read-only dashboard: `python -m src.monitor` (defaults to http://localhost:8000). Shows users, matches, chats/messages (if SERIES creds provided).

## Notes
- LLM: defaults to OpenRouter `x-ai/grok-4.1-fast`.  
- Persistence: SQLite at `DATABASE_PATH` (default `./orbit.db`).  
- PRD: see `orbitprd.md`.
