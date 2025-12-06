# Series Dating: Implementation Plan

## Overview

A LangGraph-based dating AI agent that consumes messages via Kafka, processes through an intent-driven graph, stores profiles in SQLite (with natural language summaries), and responds via the iMessage REST API.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SERIES DATING                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐         ┌──────────────────────────────────────────┐     │
│   │    Kafka     │         │            LangGraph Agent               │     │
│   │   Consumer   │────────▶│  ┌────────┐  ┌────────┐  ┌────────┐     │     │
│   │              │         │  │ Router │─▶│ Nodes  │─▶│Response│     │     │
│   └──────────────┘         │  └────────┘  └────────┘  └────────┘     │     │
│                            └──────────────────┬───────────────────────┘     │
│                                               │                              │
│                                               ▼                              │
│   ┌──────────────┐         ┌──────────────────────────────────────────┐     │
│   │   iMessage   │◀────────│              SQLite DB                   │     │
│   │   REST API   │         │  • users • profiles • matches • chats   │     │
│   └──────────────┘         └──────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
series-dating/
├── main.py                     # Entry point, starts Kafka consumer loop
├── config.py                   # Environment vars, API keys, Kafka config
│
├── kafka/
│   ├── __init__.py
│   ├── consumer.py             # Kafka consumer setup and message loop
│   └── schemas.py              # Pydantic models for Kafka message formats
│
├── api/
│   ├── __init__.py
│   ├── client.py               # iMessage API client wrapper
│   └── models.py               # Pydantic models for API requests/responses
│
├── db/
│   ├── __init__.py
│   ├── database.py             # SQLite connection, init tables
│   ├── models.py               # SQLAlchemy/dataclass models
│   └── queries.py              # CRUD operations for users, profiles, matches
│
├── agent/
│   ├── __init__.py
│   ├── graph.py                # LangGraph definition (nodes, edges, compile)
│   ├── state.py                # TypedDict state schema
│   ├── router.py               # Intent classification node
│   └── nodes/
│       ├── __init__.py
│       ├── onboarding.py       # Profile building node
│       ├── matching.py         # Match suggestions and decisions
│       └── mentor.py           # Dating advice and icebreakers
│
├── prompts/
│   ├── __init__.py
│   ├── router.py               # Intent classification prompts
│   ├── onboarding.py           # Profile extraction prompts
│   ├── matching.py             # Match pitch generation prompts
│   └── mentor.py               # Mentor response prompts
│
├── utils/
│   ├── __init__.py
│   └── llm.py                  # LLM client setup (OpenAI/Anthropic)
│
└── requirements.txt
```

---

## Database Schema (SQLite)

### Tables

#### `users`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment ID |
| phone_number | TEXT UNIQUE | E.164 format |
| chat_id | INTEGER | iMessage chat ID for this user |
| name | TEXT | User's name (once shared) |
| created_at | TIMESTAMP | First interaction |
| updated_at | TIMESTAMP | Last interaction |
| dating_enabled | BOOLEAN | Opted into dating |
| status | TEXT | onboarding / active / paused |

#### `profiles`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment ID |
| user_id | INTEGER FK | References users.id |
| profile_summary | TEXT | **Natural language** - who they are |
| looking_for_summary | TEXT | **Natural language** - what they want |
| dealbreakers | TEXT | Comma-separated dealbreakers |
| interests | TEXT | Comma-separated interests |
| communication_style | TEXT | warm / witty / direct / analytical |
| relationship_goal | TEXT | casual / serious / exploring |
| completeness | FLOAT | 0.0 to 1.0 |
| onboarding_step | INTEGER | Current step in onboarding |
| updated_at | TIMESTAMP | Last update |

#### `matches`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment ID |
| user_a_id | INTEGER FK | First user |
| user_b_id | INTEGER FK | Second user |
| bilateral_score | FLOAT | Combined compatibility |
| status | TEXT | pending_a / pending_b / mutual / rejected |
| user_a_decision | TEXT | yes / no / pending |
| user_b_decision | TEXT | yes / no / pending |
| created_at | TIMESTAMP | When suggested |
| resolved_at | TIMESTAMP | When decided |

#### `conversation_state`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment ID |
| user_id | INTEGER FK | References users.id |
| current_node | TEXT | Where in graph flow |
| context | TEXT | JSON blob of conversation context |
| match_in_progress | INTEGER | FK to matches if discussing one |
| updated_at | TIMESTAMP | Last state change |

---

## LangGraph Agent Design

### State Schema

```python
class DatingState(TypedDict):
    # Input
    user_id: int
    phone_number: str
    chat_id: int
    message: str
    
    # Loaded context
    user: dict | None
    profile: dict | None
    conversation_state: dict | None
    active_match: dict | None
    
    # Routing
    intent: str
    
    # Output
    response: str
    next_node: str | None
    db_updates: list[dict]
```

### Graph Structure

```
          ┌─────────────────┐
          │  load_context   │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ classify_intent │
          └────────┬────────┘
                   │
     ┌─────────────┼─────────────┬──────────────┐
     ▼             ▼             ▼              ▼
┌─────────┐  ┌──────────┐  ┌─────────┐   ┌──────────┐
│onboard  │  │ matching │  │ mentor  │   │ general  │
└────┬────┘  └────┬─────┘  └────┬────┘   └────┬─────┘
     │            │             │              │
     └────────────┴─────────────┴──────────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ save_and_respond│
               └─────────────────┘
```

### Node Descriptions

#### `load_context`
- Query user by phone_number
- Load profile if exists
- Load conversation_state
- Load active match if any

#### `classify_intent`
- LLM call to classify message
- Categories: `onboarding`, `match_decision`, `mentor`, `general`, `settings`
- Use conversation_state to inform (e.g., if waiting for match response)

#### `onboarding_node`
- Check completeness score
- Determine next question based on onboarding_step
- Extract info from user message via LLM
- Update natural language summaries
- Increment step, update completeness

#### `matching_node`
- Sub-intents: `suggest_match`, `process_decision`, `announce_mutual`
- Generate anonymized pitch from match's profile_summary
- Handle yes/no decisions
- Check for mutual match → trigger reveal

#### `mentor_node`
- Sub-modes: `icebreaker`, `continue`, `advice`
- Load both profiles (user + match)
- Generate contextual suggestions
- Keep it suggestions, not scripts

#### `save_and_respond`
- Apply db_updates to SQLite
- Call iMessage API to send response
- Handle typing indicator

---

## Kafka Consumer Structure

```python
# Pseudocode

def main():
    consumer = setup_kafka_consumer()
    api_client = setup_api_client()
    db = setup_database()
    graph = build_langgraph()
    
    for message in consumer:
        try:
            event = parse_kafka_event(message)
            
            state = {
                "phone_number": event.sender,
                "message": event.text,
                "chat_id": event.chat_id,
            }
            
            result = graph.invoke(state)
            
            if result.get("response"):
                api_client.send_with_typing(
                    chat_id=result["chat_id"],
                    text=result["response"]
                )
                
        except Exception as e:
            log_error(e)
            # Optionally send fallback message
```

---

## Natural Language Profile System

### Why Natural Language?

- LLM can directly use summaries for matching/mentor prompts
- More nuanced than rigid JSON fields
- Easy to update incrementally
- Human-readable for debugging

### Profile Summary Format

```
"{Name} is a {age}-year-old {occupation} at {school/company}. 
They come across as {communication_style} with {personality_traits}. 
Into {interests}. Values {values}. 
{Additional_context_from_conversations}."
```

### Looking-For Summary Format

```
"{Name} is looking for someone {key_traits}. 
They want {relationship_type} and value {priorities}. 
Dealbreaker: {dealbreakers}."
```

### Update Prompt Template

```
You are updating a dating profile based on new conversation.

Current profile: {current_summary}
New message from user: {message}

Extract any new information and generate an updated summary.
Keep it 2-4 sentences, warm and natural.
Preserve existing info unless contradicted.

Output the updated summary only.
```

---

## Matching Logic

### Bilateral Scoring (LLM-Based)

For each potential match, ask LLM:

```
Rate compatibility 0-100 between these profiles.

Person A: {profile_a_summary}
Looking for: {profile_a_looking_for}

Person B: {profile_b_summary}  
Looking for: {profile_b_looking_for}

Consider: shared interests, compatible styles, mutual fit to preferences.
Respond: {"score": X, "reason": "brief explanation"}
```

Calculate: `bilateral = sqrt(score_a_to_b * score_b_to_a)`

### Match Flow

1. Find candidates above threshold (e.g., 60)
2. Sort by bilateral score
3. Pitch top match to user (anonymized)
4. Record decision
5. If both yes → reveal and connect

---

## API Client Methods

```python
class SeriesAPI:
    def get_or_create_chat(phone: str) -> int
    def send_message(chat_id: int, text: str) -> dict
    def start_typing(chat_id: int) -> None
    def stop_typing(chat_id: int) -> None
    def get_messages(chat_id: int, limit: int) -> list
    def add_reaction(message_id: int, type: str) -> None
```

---

## Onboarding Flow

### Steps

1. **Intro** - "Hey! I hear you want to try dating on Series..."
2. **Name** - "What should I call you?"
3. **Goal** - "What are you looking for? Casual, serious, or just exploring?"
4. **About** - "Tell me a bit about yourself - what do you do, what are you into?"
5. **Interests** - "What do you do for fun? Hobbies, passions?"
6. **Looking for** - "What matters to you in a partner?"
7. **Dealbreakers** - "Anything that's a hard no for you?"
8. **Complete** - "Got it! I'll start looking for matches..."

### Step Logic

- Each step has target fields to extract
- LLM extracts info → updates profile
- If extraction confident → advance step
- If unclear → ask clarifying question
- Completeness = steps_done / total_steps

---

## Mentor: Icebreaker Generation

### Input
- User profile summary
- Match profile summary

### Prompt

```
Generate 3 conversation openers for {user_name} to send to their match.

About {user_name}: {user_profile}
About their match: {match_profile}

Create openers that:
- Reference something specific they share
- Match {user_name}'s communication style
- Are open-ended
- Avoid generic greetings

Return as numbered list.
```

---

## Execution Timeline

| Hours | Focus | Deliverable |
|-------|-------|-------------|
| 1-2 | Setup | Kafka connected, SQLite tables, project structure |
| 3-5 | Agent foundation | LangGraph skeleton, router, load_context |
| 6-9 | Onboarding | Full onboarding flow, profile building |
| 10-13 | Matching | Scoring, suggestions, opt-in flow |
| 14-17 | Mentor | Icebreaker generation working |
| 18-21 | Integration | End-to-end testing, polish |
| 22-24 | Demo | Prep pitch, backup recording |

---

## Critical Path (Must Work)

1. Kafka → receives message ✓
2. Router → classifies intent ✓
3. Onboarding → builds profile ✓
4. Matching → suggests match ✓
5. API → sends response ✓

Everything else is enhancement.

---

## Environment Variables

```
KAFKA_BOOTSTRAP_SERVERS=pkc-619z3.us-east1.gcp.confluent.cloud:9092
KAFKA_TOPIC=team.team.b75820cf492645e28fbe38fc7857e8d5
KAFKA_API_KEY=4edc45be-d69b-4df2-b3f0-cd5529e97144
KAFKA_API_SECRET=<from dashboard>
KAFKA_GROUP_ID=team-cg-b75820cf492645e28fbe38fc7857e8d5

IMESSAGE_API_BASE_URL=<provided at hackathon>
IMESSAGE_API_KEY=<your team key>

ANTHROPIC_API_KEY=<your key>
# or OPENAI_API_KEY=<your key>

DATABASE_PATH=./series_dating.db
```

---

## Dependencies

```
langgraph>=0.0.40
langchain-anthropic>=0.1.0
kafka-python>=2.0.2
httpx>=0.25.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```

---

*Ready to build. Good luck!* 🚀
