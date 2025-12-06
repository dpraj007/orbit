# Orbit - Series Dating AI Wingman 🚀

A LangGraph-based dating AI agent that builds meaningful connections through conversational profile building, bilateral matching, and personalized mentorship.

## Overview

Orbit extends the Series "AI Friend" model to romantic connections. Instead of swipe-based matching, users build relationships with an AI companion who:
- **Learns about them** through natural conversation
- **Finds genuine matches** using bilateral compatibility scoring
- **Provides mentorship** to help navigate dating conversations authentically

See `docs/product_design_spec.md` for the complete product vision.

## Features

### ✅ Conversational Profile Building
- 7-step onboarding flow that extracts rich profiles through natural dialogue
- Natural language summaries (not rigid forms)
- Progressive disclosure - learns more over time

### ✅ Bilateral Matching
- **Geometric mean scoring**: `√(score_A→B × score_B→A)`
- Ensures both people would value each other
- LLM-powered compatibility assessment

### ✅ Double Opt-In Flow
- Anonymized match pitches (no names until both agree)
- Both parties must say "yes"
- Only then are names revealed and intro made

### ✅ AI Dating Mentor
- Icebreaker generation based on both profiles
- Conversation continuation help
- Context-aware, authentic advice

## Architecture

```
┌─────────────┐
│   Kafka     │  Message events from Series
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         LangGraph Agent                 │
│  ┌────────┐  ┌────────┐  ┌────────┐    │
│  │ Router │─▶│ Nodes  │─▶│Response│    │
│  └────────┘  └────────┘  └────────┘    │
│                                         │
│  Nodes: Onboarding, Matching, Mentor   │
└──────────┬──────────────────────────────┘
           │
           ▼
┌──────────────────────┐  ┌──────────────┐
│   SQLite Database    │  │ Series API   │
│ • users              │  │ (iMessage)   │
│ • profiles           │  └──────────────┘
│ • matches            │
│ • conversation_state │
└──────────────────────┘
```

## Quick Start

### 1. Prerequisites

- Python 3.9+
- Access to Series Kafka cluster (credentials from Series team)
- OpenRouter API key ([get one here](https://openrouter.ai/))

### 2. Setup Environment

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Fill in your credentials in `.env`:**
   ```bash
   # Required - Get from Series team:
   KAFKA_SASL_PASSWORD=your_kafka_password
   SERIES_BASE_URL=https://your_series_host
   SERIES_API_KEY=your_series_api_key

   # Required - Get from OpenRouter:
   OPENROUTER_API_KEY=your_openrouter_key
   ```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Agent

```bash
python -m src.main
```

You should see:
```
INFO:orbit:Building LangGraph agent...
INFO:orbit:Orbit consumer started on topic team.team.xxxxx
INFO:orbit:Dating agent ready with LangGraph
```

## Configuration

### Environment Variables

See `.env.example` for all available options. Key configurations:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_MODEL` | LLM model to use | `x-ai/grok-4.1-fast` |
| `DATABASE_PATH` | SQLite database location | `./orbit.db` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `REQUEST_TIMEOUT_SEC` | API timeout | `10` |

### Recommended Models

- **Fast & Cost-Effective**: `x-ai/grok-4.1-fast` (default)
- **High Quality**: `anthropic/claude-3.5-sonnet`
- **Balanced**: `openai/gpt-4-turbo`

## Usage Examples

### Onboarding Flow

```
User: Hey!
Orbit: Hey! What's your name?

User: I'm Alex
Orbit: What are you looking for? Something casual, serious, or just exploring?

User: Looking for something serious
Orbit: Tell me a bit about yourself - what do you do, what are you into?

... (continues through 7 steps)
```

### Finding a Match

```
User: Find me a match
Orbit: Found a match! They're a thoughtful person who loves hiking and good
       coffee. You both share a passion for travel and outdoor adventures.
       They seem genuine and value deep conversation.

       Interested? Say yes or no.

User: yes
Orbit: Noted! I'm waiting on the other person.

... (when both say yes)

Orbit: Great! I've connected you both. Check your group chat!
```

### Getting Mentor Help

```
User: I need help with an icebreaker
Orbit: Here are some conversation starters:

       1. Ask about their favorite hiking trail in the area
       2. Share that funny story about your trip to Costa Rica
       3. Something playful: "My AI wingman says we'd get along. Thoughts?"

       Which feels most like you?
```

## Project Structure

```
orbit/
├── docs/
│   ├── product_design_spec.md    # Full product vision
│   └── implementation_plan.md    # Technical implementation guide
├── src/
│   ├── agent/
│   │   ├── graph.py              # LangGraph compilation
│   │   ├── state.py              # State schema
│   │   └── nodes/
│   │       ├── load_context.py   # Load user data
│   │       ├── router.py         # Intent classification
│   │       ├── onboarding.py     # Profile building
│   │       ├── matching.py       # Bilateral matching
│   │       ├── mentor.py         # Dating advice
│   │       └── general.py        # Fallback handler
│   ├── prompts/
│   │   ├── router.py             # Intent classification prompts
│   │   ├── onboarding.py         # Profile extraction prompts
│   │   ├── matching.py           # Scoring & pitch prompts
│   │   └── mentor.py             # Icebreaker prompts
│   ├── client.py                 # Series API client
│   ├── store.py                  # SQLite operations
│   ├── llm.py                    # LLM integration
│   ├── engine.py                 # Event processing
│   └── main.py                   # Kafka consumer
├── .env.example                  # Environment template
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Database Schema

### `users`
- User identity and status tracking
- Links to Series phone numbers

### `profiles`
- **Natural language summaries** (profile_summary, looking_for_summary)
- Interests, dealbreakers, communication style
- Completeness tracking

### `matches`
- Bilateral compatibility scores
- Double opt-in status tracking
- Match history

### `conversation_state`
- Current conversation context
- Active match tracking
- Graph node state

## Development

### Running Tests

```bash
# TODO: Add tests
pytest tests/
```

### Debugging

Set `LOG_LEVEL=DEBUG` in `.env` for verbose logging:

```bash
LOG_LEVEL=DEBUG
```

### Viewing Database

```bash
sqlite3 orbit.db

# Useful queries:
SELECT * FROM users;
SELECT * FROM profiles WHERE completeness >= 0.5;
SELECT * FROM matches WHERE status = 'mutual';
```

## Troubleshooting

### "Missing required env var"
Make sure you've copied `.env.example` to `.env` and filled in all required fields.

### "LLM request failed"
Check your `OPENROUTER_API_KEY` is valid and has credits.

### "Kafka connection failed"
Verify your Kafka credentials with the Series team.

### Database locked errors
Make sure only one instance of Orbit is running. SQLite doesn't support concurrent writes well.

## Contributing

This is a hackathon project! Feel free to:
- Add new mentor modes
- Improve matching algorithms
- Add more sophisticated profile building
- Implement feedback loops

## License

See `LICENSE` file.

## Documentation

- **Product Design**: `docs/product_design_spec.md`
- **Implementation Plan**: `docs/implementation_plan.md`
- **Original PRD**: `orbitprd.md`
- **API Spec**: `openapi.json`

## Support

For questions or issues:
1. Check this README
2. Review the documentation in `/docs`
3. Check logs with `LOG_LEVEL=DEBUG`

---

Built with ❤️ for Series Hackathon 2025
