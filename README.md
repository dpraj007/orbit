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

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` from `.env.example`:

```bash
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=pkc-619z3.us-east1.gcp.confluent.cloud:9092
KAFKA_TOPIC=team.team.<your_topic_id>
KAFKA_CONSUMER_GROUP=team-cg-<your_group_id>
KAFKA_CLIENT_ID=orbit-consumer
KAFKA_SASL_USERNAME=<your_kafka_key>
KAFKA_SASL_PASSWORD=<your_kafka_secret>

# Series API Configuration
SERIES_BASE_URL=<series_api_url>
SERIES_API_KEY=<your_api_key>
SERIES_SENDER_NUMBER=<phone_number>

# LLM Configuration (OpenRouter)
OPENROUTER_API_KEY=<your_openrouter_key>
OPENROUTER_MODEL=x-ai/grok-2-1212

# Database
DATABASE_PATH=./orbit.db

# Logging
LOG_LEVEL=INFO
```

### 3. Run the Agent

```bash
python -m src.main
```

The agent will:
1. Initialize the database with all tables
2. Connect to Kafka and start consuming
3. Process messages through the LangGraph pipeline
4. Respond via Series iMessage API

## How It Works

### User Journey

1. **New User** → Receives first onboarding question
2. **Onboarding** → 7 questions to build natural language profile
3. **Active** → Profile complete, ready for matching
4. **Match Suggested** → AI suggests a bilateral match with anonymized pitch
5. **Decision** → User says yes/no
6. **Mutual Match** → Both said yes → Group chat created
7. **Mentor Available** → Can request icebreakers, advice, etc.

### Intent Classification

The router analyzes messages and classifies into:
- `onboarding` - Building profile
- `match_decision` - Responding to match suggestion
- `mentor` - Asking for dating advice
- `general` - Other conversations

### Bilateral Scoring Algorithm

For each potential match:
1. LLM scores how well Person A matches Person B's preferences (0-100)
2. LLM scores how well Person B matches Person A's preferences (0-100)
3. Calculate bilateral score: `sqrt(score_a * score_b)`
4. Only suggest matches above threshold (60+)

This ensures **both** people benefit from the match.

### Natural Language Profiles

Instead of rigid JSON fields, profiles are stored as natural language summaries:

**Profile Summary Example:**
```
"Alex is a 24-year-old software engineer passionate about climbing and cooking.
They come across as warm and thoughtful. Values intellectual connection and
someone who shares their love of the outdoors."
```

**Looking For Summary Example:**
```
"Alex is looking for someone genuine and adventurous. They want something
serious and value good communication. Dealbreaker: lack of ambition."
```

This allows the LLM to directly use summaries for matching without complex field mapping.

## Database Schema

### users
- `id`, `phone_number`, `chat_id`, `name`
- `created_at`, `updated_at`
- `dating_enabled`, `status`

### profiles
- `id`, `user_id` (FK)
- `profile_summary` (natural language)
- `looking_for_summary` (natural language)
- `dealbreakers`, `interests`
- `communication_style`, `relationship_goal`
- `completeness` (0.0 - 1.0), `onboarding_step`

### matches
- `id`, `user_a_id`, `user_b_id` (FKs)
- `bilateral_score` (geometric mean)
- `status` (pending_a/pending_b/mutual/rejected)
- `user_a_decision`, `user_b_decision`
- `created_at`, `resolved_at`

### conversation_state
- `id`, `user_id` (FK)
- `current_node` (where in agent flow)
- `context` (JSON blob)
- `match_in_progress` (FK to matches)

## LLM Integration

Uses **OpenRouter** for flexible model access:
- Default: `x-ai/grok-2-1212` (fast, good reasoning)
- Configured via `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`
- All prompts in `src/prompts/` for easy iteration

## Development

### Running Tests
```bash
# TODO: Add pytest tests
pytest tests/
```

### Adding a New Node

1. Create node function in `src/agent/nodes/your_node.py`
2. Add prompt templates in `src/prompts/your_node.py`
3. Register in `src/agent/graph.py`
4. Update router in `src/agent/router.py`

### Modifying Prompts

All prompts are in `src/prompts/`. Edit and restart - no code changes needed.

## Production Considerations

- **Rate Limiting**: OpenRouter has rate limits - consider caching
- **Costs**: LLM calls cost money - bilateral scoring is 2x calls per match
- **Privacy**: Profile summaries contain PII - encrypt at rest
- **Scale**: SQLite is fine for prototype, use Postgres for production
- **Monitoring**: Add metrics for match quality, user engagement

## Documentation

- **Implementation Plan**: `docs/implementation_plan.md`
- **Product Design Spec**: `docs/product_design_spec.md`
- **OpenAPI Spec**: `openapi.json`

## License

See `LICENSE`

## Built With

- **LangGraph** - State machine orchestration
- **LangChain** - LLM abstractions
- **OpenRouter** - LLM API gateway
- **Kafka** - Event streaming
- **SQLite** - Database
- **Pydantic** - Data validation
- **httpx** - HTTP client

---

**Status**: ✅ Full implementation complete per plan

**Last Updated**: December 6, 2025
