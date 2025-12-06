# Orbit Backend Testing Plan (LLM-Simulated E2E)

## Overview

This plan enables testing the full Orbit logic layer—LangGraph agent, DB operations, and API payload generation—without Kafka brokers or real iMessage API calls. An LLM simulates realistic user conversations to exercise all agent paths.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         TEST HARNESS                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────┐     ┌──────────────────────────────────────────┐    │
│  │   LLM Persona   │     │           LangGraph Agent                 │    │
│  │   Simulator     │────▶│  (process_event with stubbed deps)        │    │
│  └─────────────────┘     └──────────────────────────────────────────┘    │
│         │                              │                                  │
│         │                              ▼                                  │
│         │                 ┌──────────────────────────────────────────┐   │
│         │                 │         SQLite (in-memory)               │   │
│         │                 └──────────────────────────────────────────┘   │
│         │                              │                                  │
│         ▼                              ▼                                  │
│  ┌─────────────────┐     ┌──────────────────────────────────────────┐   │
│  │  Assert Agent   │◀────│        SeriesAPI Stub                     │   │
│  │   Responses     │     │   (records calls, no network)             │   │
│  └─────────────────┘     └──────────────────────────────────────────┘   │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Goals

1. **Logic Validation**: Verify onboarding, matching, mentor, fallback, and routing work correctly
2. **State Progression**: Confirm DB state updates (profiles, matches, conversation_state) are correct
3. **API Payloads**: Assert outbound messages to SeriesAPI have correct shape and content
4. **Error Handling**: Test graceful degradation on LLM failures, malformed inputs
5. **Realistic Scenarios**: Use LLM to generate human-like conversation flows

---

## Test Harness Components

### 1. Event Builder (`tests/helpers/event_builder.py`)

```python
def build_event(
    phone: str = "+15551234567",
    chat_id: int = 1001,
    text: str = "Hello",
    message_id: int | None = None,
    chat_handles: list[str] | None = None,
) -> dict:
    """Build a dict matching KafkaEvent schema for direct process_event calls."""
    return {
        "event_type": "message",
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {
            "text": text,
            "from_phone": phone,
            "chat_id": chat_id,
            "message_id": message_id or random.randint(1000, 9999),
            "chat_handles": chat_handles or [phone, "+15550000000"],
            "attachments": [],
        },
    }
```

### 2. SeriesAPI Stub (`tests/helpers/api_stub.py`)

```python
@dataclass
class APICall:
    method: str
    chat_id: int | None
    payload: dict
    timestamp: datetime

class SeriesAPIStub:
    """Records all API calls without network I/O."""
    
    def __init__(self):
        self.calls: list[APICall] = []
        self.group_chat_counter = 5000
    
    def send_message(self, chat_id: int, text: str, **kwargs):
        self.calls.append(APICall("send_message", chat_id, {"text": text, **kwargs}, utc_now()))
        return {"id": random.randint(1, 9999)}
    
    def send_with_typing(self, chat_id: int, text: str, delay: float = 0):
        self.calls.append(APICall("send_with_typing", chat_id, {"text": text}, utc_now()))
        return {"id": random.randint(1, 9999)}
    
    def create_group_chat(self, phone_numbers: list, initial_text: str, **kwargs):
        self.group_chat_counter += 1
        self.calls.append(APICall("create_group_chat", None, {
            "phone_numbers": phone_numbers,
            "text": initial_text,
            **kwargs
        }, utc_now()))
        return {"chat": {"id": self.group_chat_counter}}
    
    def start_typing(self, chat_id: int): pass
    def stop_typing(self, chat_id: int): pass
    
    def get_messages_to(self, chat_id: int) -> list[str]:
        """Get all messages sent to a specific chat."""
        return [c.payload["text"] for c in self.calls if c.chat_id == chat_id]
    
    def reset(self):
        self.calls.clear()
```

### 3. Test Runner (`tests/helpers/runner.py`)

```python
@dataclass
class RunResult:
    response: str
    db_state: dict  # Snapshot of user, profile, conversation_state
    api_calls: list[APICall]
    trace: list[str]  # Node transitions
    error: str | None

class TestRunner:
    """Executes events through the graph and captures results."""
    
    def __init__(self, db: Database, api_stub: SeriesAPIStub):
        self.db = db
        self.api = api_stub
        self.graph = build_graph(db, api_stub)
        self.log = logging.getLogger("test.runner")
        self.traces: list[str] = []
    
    def run_event(self, event: dict) -> RunResult:
        """Process single event, return structured result."""
        self.api.reset()  # Clear API call history
        
        try:
            kafka_event = KafkaEvent.from_dict(event)
            phone = kafka_event.data.from_phone
            chat_id = kafka_event.data.chat_id
            text = (kafka_event.data.text or "").strip()
            
            initial_state = {
                "phone_number": phone,
                "chat_id": chat_id,
                "message": text,
                "db_updates": [],
            }
            
            result = self.graph.invoke(initial_state)
            
            # Capture DB state after run
            user = self.db.users.get_by_phone(phone)
            profile = self.db.profiles.get_by_user_id(user["id"]) if user else None
            conv_state = self.db.conversation_state.get_by_user_id(user["id"]) if user else None
            
            return RunResult(
                response=result.get("response", ""),
                db_state={
                    "user": dict(user) if user else None,
                    "profile": dict(profile) if profile else None,
                    "conversation_state": dict(conv_state) if conv_state else None,
                },
                api_calls=self.api.calls.copy(),
                trace=self.traces.copy(),
                error=result.get("error"),
            )
            
        except Exception as exc:
            self.log.exception("Event processing failed")
            return RunResult("", {}, [], [], str(exc))
    
    def run_conversation(self, events: list[dict]) -> list[RunResult]:
        """Run a sequence of events, returning all results."""
        return [self.run_event(e) for e in events]
```

### 4. Pytest Fixtures (`tests/conftest.py`)

```python
import pytest
import sqlite3
from src.db import Database
from tests.helpers.api_stub import SeriesAPIStub
from tests.helpers.runner import TestRunner

@pytest.fixture
def db_fx(tmp_path):
    """In-memory SQLite database for isolation."""
    db = Database(":memory:")
    yield db
    db.close()

@pytest.fixture
def api_stub():
    """Fresh API stub per test."""
    return SeriesAPIStub()

@pytest.fixture
def runner(db_fx, api_stub):
    """Test runner with fresh DB and API stub."""
    return TestRunner(db_fx, api_stub)

@pytest.fixture
def event_fx():
    """Factory for building test events."""
    from tests.helpers.event_builder import build_event
    return build_event
```

---

## LLM Persona Simulator

### Overview

The simulator uses an LLM to roleplay as different user personas, generating realistic conversation turns that exercise the full agent flow.

### Persona Schema (`tests/simulation/personas.py`)

```python
@dataclass
class Persona:
    name: str
    age: int
    occupation: str
    personality: str  # "outgoing", "shy", "analytical", "playful"
    relationship_goal: str  # "casual", "serious", "exploring"
    interests: list[str]
    communication_style: str  # "verbose", "terse", "emoji-heavy"
    quirks: list[str]  # Unique behaviors like typos, slang
    
PERSONAS = [
    Persona(
        name="Alex",
        age=25,
        occupation="Software Engineer",
        personality="analytical",
        relationship_goal="serious",
        interests=["hiking", "cooking", "board games"],
        communication_style="verbose",
        quirks=["uses technical metaphors", "asks clarifying questions"],
    ),
    Persona(
        name="Jordan",
        age=28,
        occupation="Marketing Manager",
        personality="outgoing",
        relationship_goal="exploring",
        interests=["music festivals", "yoga", "travel"],
        communication_style="emoji-heavy",
        quirks=["uses lots of exclamation points!", "references pop culture"],
    ),
    Persona(
        name="Sam",
        age=23,
        occupation="Grad Student",
        personality="shy",
        relationship_goal="serious",
        interests=["reading", "indie films", "coffee shops"],
        communication_style="terse",
        quirks=["gives short answers", "takes time to open up"],
    ),
]
```

### Conversation Driver (`tests/simulation/driver.py`)

```python
from langchain_openai import ChatOpenAI

SIMULATOR_SYSTEM_PROMPT = """
You are roleplaying as a user on a dating app talking to an AI assistant named Orbit.

YOUR PERSONA:
- Name: {name}
- Age: {age}
- Occupation: {occupation}
- Personality: {personality}
- Looking for: {relationship_goal}
- Interests: {interests}
- Communication style: {communication_style}
- Quirks: {quirks}

CURRENT CONTEXT:
- Conversation history so far:
{conversation_history}

- Orbit's last message:
{agent_response}

INSTRUCTIONS:
- Respond naturally as this persona would
- Stay in character with the communication style and quirks
- If Orbit asks a question, answer it authentically as your persona
- Don't break character or mention you're an AI
- Keep responses realistic (1-3 sentences typically)
- If you want to end the conversation, respond with exactly: [END]

Generate your next message:
"""

class ConversationDriver:
    """Drives multi-turn conversations using LLM-simulated personas."""
    
    def __init__(
        self,
        runner: TestRunner,
        llm: ChatOpenAI | None = None,
        max_turns: int = 20,
        token_budget: int = 5000,
    ):
        self.runner = runner
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        self.max_turns = max_turns
        self.token_budget = token_budget
        self.tokens_used = 0
    
    def generate_user_response(
        self, persona: Persona, history: list[tuple[str, str]], agent_response: str
    ) -> str | None:
        """Generate next user message based on persona and context."""
        
        history_text = "\n".join([
            f"User: {u}\nOrbit: {a}" for u, a in history
        ]) or "(conversation just started)"
        
        prompt = SIMULATOR_SYSTEM_PROMPT.format(
            name=persona.name,
            age=persona.age,
            occupation=persona.occupation,
            personality=persona.personality,
            relationship_goal=persona.relationship_goal,
            interests=", ".join(persona.interests),
            communication_style=persona.communication_style,
            quirks=", ".join(persona.quirks),
            conversation_history=history_text,
            agent_response=agent_response,
        )
        
        result = self.llm.invoke(prompt)
        self.tokens_used += result.response_metadata.get("token_usage", {}).get("total_tokens", 100)
        
        response = result.content.strip()
        
        if "[END]" in response or self.tokens_used >= self.token_budget:
            return None
        
        return response
    
    def run_full_conversation(
        self,
        persona: Persona,
        phone: str = "+15551234567",
        chat_id: int = 1001,
        initial_message: str | None = None,
    ) -> ConversationResult:
        """Run complete conversation until natural end or limits reached."""
        
        history: list[tuple[str, str]] = []
        results: list[RunResult] = []
        
        # Start with initial message or generate one
        user_message = initial_message or f"Hey! I'm {persona.name}"
        
        for turn in range(self.max_turns):
            # Run user message through agent
            event = build_event(phone=phone, chat_id=chat_id, text=user_message)
            result = self.runner.run_event(event)
            results.append(result)
            
            history.append((user_message, result.response))
            
            # Check for natural end conditions
            if "I'll start looking for matches" in result.response:
                # Onboarding complete
                break
            
            # Generate next user response
            user_message = self.generate_user_response(persona, history, result.response)
            
            if user_message is None:
                break
        
        return ConversationResult(
            persona=persona,
            turns=history,
            results=results,
            tokens_used=self.tokens_used,
        )

@dataclass
class ConversationResult:
    persona: Persona
    turns: list[tuple[str, str]]  # (user_msg, agent_msg) pairs
    results: list[RunResult]
    tokens_used: int
    
    @property
    def final_db_state(self) -> dict:
        return self.results[-1].db_state if self.results else {}
    
    @property
    def onboarding_completed(self) -> bool:
        user = self.final_db_state.get("user", {})
        return user.get("status") == "active"
```

---

## Test Scenarios

### 1. Unit Tests (`tests/unit/`)

#### Config & Environment

```python
# tests/unit/test_config.py
def test_config_requires_kafka_vars(monkeypatch):
    monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
    with pytest.raises(RuntimeError, match="Missing required env var"):
        Config.from_env()

def test_config_defaults(monkeypatch, set_required_env):
    cfg = Config.from_env()
    assert cfg.log_level == "INFO"
    assert cfg.max_retries == 3
```

#### Kafka Schema Parsing

```python
# tests/unit/test_schemas.py
def test_kafka_event_missing_data():
    event = KafkaEvent.from_dict({})
    assert event.data.text is None
    assert event.data.chat_handles == []

def test_kafka_event_full():
    event = KafkaEvent.from_dict({
        "event_type": "message",
        "data": {"text": "hello", "from_phone": "+1234", "chat_id": 100}
    })
    assert event.data.text == "hello"
```

#### Router Intent Classification

```python
# tests/unit/test_router.py
def test_route_onboarding_user_goes_to_onboarding(runner, event_fx):
    result = runner.run_event(event_fx(text="Hi there"))
    assert result.db_state["user"]["status"] == "onboarding"

def test_route_match_decision_when_active_match(db_fx, runner, event_fx):
    # Seed user with active match
    user_id = db_fx.users.create("+1555", 100)
    db_fx.profiles.create(user_id)
    db_fx.users.update_status(user_id, "active")
    match_id = db_fx.matches.create(user_id, 999, 75.0)
    db_fx.conversation_state.upsert(user_id, match_in_progress=match_id)
    
    result = runner.run_event(event_fx(phone="+1555", text="yes"))
    # Should route to matching node
    assert "match" in result.response.lower() or "waiting" in result.response.lower()
```

#### Onboarding Node

```python
# tests/unit/test_onboarding.py
def test_onboarding_extracts_name(runner, event_fx):
    runner.run_event(event_fx(text="Hi"))  # First contact
    result = runner.run_event(event_fx(text="Alex, I love hiking"))
    
    assert result.db_state["profile"]["onboarding_step"] >= 1

def test_onboarding_completes_after_all_steps(runner, event_fx):
    messages = [
        "Alex, passionate about technology",
        "Looking for something serious",
        "I'm a software engineer who loves building things",
        "Someone kind, smart, and adventurous",
        "Smoking is a dealbreaker",
        "Friends say I'm warm and thoughtful",
        "Hiking, coffee shops, and board game nights",
    ]
    
    for msg in messages:
        result = runner.run_event(event_fx(text=msg))
    
    assert result.db_state["user"]["status"] == "active"
    assert result.db_state["profile"]["completeness"] == 1.0
```

#### Matching Node

```python
# tests/unit/test_matching.py
def test_bilateral_score_calculation(db_fx):
    from src.agent.nodes.matching import calculate_bilateral_score
    
    profile_a = {"profile_summary": "Outgoing, loves hiking", "looking_for_summary": "Active partner"}
    profile_b = {"profile_summary": "Adventurous, fitness enthusiast", "looking_for_summary": "Fun companion"}
    
    score, reason = calculate_bilateral_score(profile_a, profile_b)
    assert 0 <= score <= 100
    assert len(reason) > 0

def test_match_rejection_clears_state(db_fx, runner, event_fx):
    # Setup active match
    user_id = db_fx.users.create("+1555", 100)
    db_fx.profiles.create(user_id)
    db_fx.profiles.update_summary(user_id, "Test user", 1.0)
    db_fx.users.update_status(user_id, "active")
    
    other_id = db_fx.users.create("+1666", 101)
    db_fx.profiles.create(other_id)
    
    match_id = db_fx.matches.create(user_id, other_id, 75.0)
    db_fx.conversation_state.upsert(user_id, current_node="match_decision", match_in_progress=match_id)
    
    result = runner.run_event(event_fx(phone="+1555", text="no thanks"))
    
    assert "keep looking" in result.response.lower()
    assert result.db_state["conversation_state"]["match_in_progress"] is None
```

#### Mentor Node

```python
# tests/unit/test_mentor.py
def test_mentor_detects_icebreaker_mode():
    from src.agent.nodes.mentor import detect_mentor_mode
    
    assert detect_mentor_mode("need some icebreaker ideas") == "icebreaker"
    assert detect_mentor_mode("help me start the conversation") == "icebreaker"

def test_mentor_generates_icebreakers(db_fx, runner, event_fx):
    # Setup matched users
    user_id = db_fx.users.create("+1555", 100)
    db_fx.profiles.create(user_id)
    db_fx.profiles.update_summary(user_id, "Loves hiking and cooking", 1.0)
    db_fx.users.update_status(user_id, "active")
    
    other_id = db_fx.users.create("+1666", 101)
    db_fx.profiles.create(other_id)
    db_fx.profiles.update_summary(other_id, "Yoga enthusiast, world traveler", 1.0)
    
    match_id = db_fx.matches.create(user_id, other_id, 80.0)
    db_fx.matches.update_decision(match_id, user_id, "yes")
    db_fx.matches.update_decision(match_id, other_id, "yes")
    db_fx.conversation_state.upsert(user_id, current_node="connected", match_in_progress=match_id)
    
    result = runner.run_event(event_fx(phone="+1555", text="give me some icebreaker ideas"))
    
    # Should return conversation starters
    assert len(result.response) > 50
```

---

### 2. Integration Tests (`tests/integration/`)

#### Full Onboarding Flow

```python
# tests/integration/test_onboarding_flow.py
def test_complete_onboarding_happy_path(runner, event_fx):
    """Walk through complete onboarding with realistic answers."""
    phone = "+15559876543"
    chat_id = 2001
    
    conversations = [
        ("Hey!", "What's your name"),
        ("I'm Taylor, and I'm really into photography", "looking for"),
        ("Something serious, ready to settle down", "about yourself"),
        ("I'm a product designer at a startup. Love creative work!", "partner"),
        ("Someone curious, kind, and has their own passions", "dealbreaker"),
        ("Dishonesty and lack of ambition", "communication"),
        ("My friends say I'm thoughtful and a good listener", "weekend"),
        ("Coffee shop in the morning, maybe a hike, dinner with friends", "matches"),
    ]
    
    for user_msg, expected_in_response in conversations:
        result = runner.run_event(event_fx(phone=phone, chat_id=chat_id, text=user_msg))
        assert expected_in_response.lower() in result.response.lower() or result.db_state["user"]["status"] == "active"
    
    # Verify final state
    assert result.db_state["user"]["status"] == "active"
    assert result.db_state["profile"]["completeness"] == 1.0
    assert "taylor" in result.db_state["profile"]["profile_summary"].lower()
```

#### Matching Flow with Two Users

```python
# tests/integration/test_matching_flow.py
def test_mutual_match_creates_group(db_fx, api_stub, runner, event_fx):
    """Two users match and get connected via group chat."""
    
    # Setup User A (completed onboarding)
    user_a_phone = "+15551111111"
    user_a_chat = 1001
    user_a_id = db_fx.users.create(user_a_phone, user_a_chat)
    db_fx.profiles.create(user_a_id)
    db_fx.profiles.update_summary(user_a_id, "Alex loves hiking and tech", 1.0)
    db_fx.profiles.update_field(user_a_id, "looking_for_summary", "Active, curious partner")
    db_fx.users.update_status(user_a_id, "active")
    
    # Setup User B
    user_b_phone = "+15552222222"
    user_b_chat = 1002
    user_b_id = db_fx.users.create(user_b_phone, user_b_chat)
    db_fx.profiles.create(user_b_id)
    db_fx.profiles.update_summary(user_b_id, "Jordan is adventurous and outgoing", 1.0)
    db_fx.profiles.update_field(user_b_id, "looking_for_summary", "Someone thoughtful and active")
    db_fx.users.update_status(user_b_id, "active")
    
    # User A requests match
    result_a = runner.run_event(event_fx(phone=user_a_phone, chat_id=user_a_chat, text="find me a match"))
    assert "want an intro" in result_a.response.lower()
    
    # User A says yes
    result_a_yes = runner.run_event(event_fx(phone=user_a_phone, chat_id=user_a_chat, text="yes"))
    
    # User B says yes (they got notified)
    result_b_yes = runner.run_event(event_fx(phone=user_b_phone, chat_id=user_b_chat, text="yes"))
    
    # Check group chat was created
    group_calls = [c for c in api_stub.calls if c.method == "create_group_chat"]
    assert len(group_calls) >= 1
    assert user_a_phone in group_calls[0].payload["phone_numbers"]
    assert user_b_phone in group_calls[0].payload["phone_numbers"]
```

#### Group Chat Skip Logic

```python
# tests/integration/test_group_skip.py
def test_group_message_without_mention_skipped(runner, event_fx):
    """Group messages without @orbit should be ignored."""
    
    event = event_fx(
        text="Hey everyone, what's up?",
        chat_handles=["+1555", "+1666", "+1777"],  # 3 = group
    )
    
    # Process shouldn't crash, but also shouldn't respond
    from src.main import process_event
    import logging
    
    # This should complete without sending any response
    # (In real test, would verify no api calls made)

def test_group_message_with_mention_processed(db_fx, runner, event_fx):
    """Group messages with @orbit should be processed."""
    
    phone = "+15551234567"
    user_id = db_fx.users.create(phone, 3001)
    db_fx.profiles.create(user_id)
    db_fx.users.update_status(user_id, "active")
    
    event = event_fx(
        phone=phone,
        chat_id=3001,
        text="@orbit help me with an icebreaker",
        chat_handles=[phone, "+1666", "+1777"],
    )
    
    result = runner.run_event(event)
    assert result.response  # Should get a response
```

---

### 3. LLM Simulation Tests (`tests/simulation/`)

```python
# tests/simulation/test_persona_conversations.py
import pytest
from tests.simulation.driver import ConversationDriver
from tests.simulation.personas import PERSONAS

@pytest.mark.llm_slow
class TestPersonaSimulations:
    
    def test_analytical_persona_completes_onboarding(self, runner):
        """Analytical persona should complete onboarding with detailed answers."""
        driver = ConversationDriver(runner, max_turns=15)
        persona = PERSONAS[0]  # Alex - analytical
        
        result = driver.run_full_conversation(
            persona,
            initial_message="Hi, I heard about this dating feature and want to try it"
        )
        
        assert result.onboarding_completed
        assert len(result.turns) >= 7  # At least the onboarding questions
        assert result.tokens_used < 3000
    
    def test_shy_persona_handles_onboarding(self, runner):
        """Shy/terse persona should still complete onboarding."""
        driver = ConversationDriver(runner, max_turns=20)
        persona = PERSONAS[2]  # Sam - shy
        
        result = driver.run_full_conversation(
            persona,
            initial_message="hey"
        )
        
        # Might take more turns due to terse answers
        assert result.onboarding_completed or len(result.turns) >= 10
    
    def test_multiple_personas_get_matched(self, runner, db_fx):
        """Simulate two personas completing onboarding and matching."""
        driver = ConversationDriver(runner, max_turns=12)
        
        # Run Alex through onboarding
        alex_result = driver.run_full_conversation(
            PERSONAS[0],
            phone="+15551111111",
            chat_id=1001,
            initial_message="Hey! Ready to find someone special"
        )
        
        # Run Jordan through onboarding  
        driver.tokens_used = 0  # Reset token counter
        jordan_result = driver.run_full_conversation(
            PERSONAS[1],
            phone="+15552222222", 
            chat_id=1002,
            initial_message="Hiii!! Super excited to try this 🎉"
        )
        
        # Both should complete onboarding
        assert alex_result.onboarding_completed
        assert jordan_result.onboarding_completed
        
        # Verify both profiles exist and are searchable
        alex_profile = db_fx.profiles.get_by_user_id(
            db_fx.users.get_by_phone("+15551111111")["id"]
        )
        jordan_profile = db_fx.profiles.get_by_user_id(
            db_fx.users.get_by_phone("+15552222222")["id"]
        )
        
        assert alex_profile["completeness"] == 1.0
        assert jordan_profile["completeness"] == 1.0
```

---

## Edge Cases & Error Handling

### Malformed Input Tests

```python
# tests/edge/test_malformed_input.py
def test_empty_message(runner, event_fx):
    result = runner.run_event(event_fx(text=""))
    assert result.response  # Should still respond
    assert not result.error

def test_whitespace_only_message(runner, event_fx):
    result = runner.run_event(event_fx(text="   \n\t  "))
    assert result.response

def test_missing_phone(runner):
    event = {"data": {"text": "hello", "chat_id": 100}}
    result = runner.run_event(event)
    # Should handle gracefully

def test_extremely_long_message(runner, event_fx):
    long_text = "a" * 10000
    result = runner.run_event(event_fx(text=long_text))
    assert result.response
```

### LLM Failure Handling

```python
# tests/edge/test_llm_failures.py
def test_llm_timeout_graceful_fallback(runner, event_fx, monkeypatch):
    """Agent should provide fallback response on LLM timeout."""
    from src.utils import llm
    
    def mock_llm_that_fails(*args, **kwargs):
        raise TimeoutError("LLM timeout")
    
    monkeypatch.setattr(llm, "get_llm", lambda: type("MockLLM", (), {"invoke": mock_llm_that_fails})())
    
    result = runner.run_event(event_fx(text="find me a match"))
    
    # Should get a fallback response, not crash
    assert result.response or result.error

def test_llm_invalid_json_response(runner, event_fx, monkeypatch):
    """Agent should handle malformed LLM responses."""
    # Mock LLM to return non-JSON for scoring
    # Verify fallback score is used
```

### Database Constraint Tests

```python
# tests/edge/test_db_constraints.py
def test_duplicate_phone_number(db_fx):
    """Creating user with duplicate phone should fail gracefully."""
    db_fx.users.create("+15551234567", 100)
    
    # Second create with same phone should not duplicate
    user = db_fx.users.get_by_phone("+15551234567")
    assert user is not None

def test_match_with_self_prevented(db_fx):
    """User should not be able to match with themselves."""
    user_id = db_fx.users.create("+1555", 100)
    
    # Matching logic should exclude self
    candidates = db_fx.matches.get_candidates_for_user(user_id)
    assert user_id not in [c["user_id"] for c in candidates]
```

---

## Running Tests

### Commands

```bash
# Run all unit tests (fast, deterministic)
pytest tests/unit -v -m "not llm_slow"

# Run integration tests
pytest tests/integration -v

# Run LLM simulation tests (slower, uses real LLM)
pytest tests/simulation -v -m llm_slow

# Run everything with coverage
pytest --cov=src --cov-report=html --cov-branch

# Run specific scenario
pytest tests/integration/test_matching_flow.py::test_mutual_match_creates_group -v
```

### Environment Setup

```bash
# .env.test
DATABASE_PATH=:memory:
OPENROUTER_API_KEY=your-key-for-llm-tests
LOG_LEVEL=DEBUG

# For simulation tests only
SIMULATION_TOKEN_BUDGET=5000
SIMULATION_MAX_TURNS=20
```

### Pytest Configuration

```ini
# pytest.ini
[pytest]
markers =
    unit: Fast, deterministic unit tests
    integration: Integration tests with stubbed dependencies
    llm_slow: Tests that use real LLM calls (opt-in)
    
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

filterwarnings =
    ignore::DeprecationWarning
```

---

## Coverage Targets

| Component | Target | Notes |
|-----------|--------|-------|
| `src/agent/nodes/*` | ≥90% | Core logic |
| `src/agent/router.py` | ≥85% | Routing logic |
| `src/db/queries.py` | ≥90% | CRUD operations |
| `src/kafka/schemas.py` | 100% | Simple parsing |
| `src/api/client.py` | ≥70% | Network code (partially mocked) |
| **Overall** | ≥85% | Statements + branches |

---

## Metrics & Evaluation

### Conversation Quality Heuristics

For LLM-simulated tests, evaluate:

1. **State Progression**: Onboarding step increments correctly
2. **Response Relevance**: Agent responses address user input
3. **No Forbidden Strings**: No "[ERROR]", "undefined", raw JSON in responses
4. **Completion Rate**: % of simulated personas completing onboarding
5. **Turn Efficiency**: Average turns to complete onboarding (target: 7-10)

### Automated Checks

```python
def evaluate_conversation(result: ConversationResult) -> dict:
    return {
        "completed": result.onboarding_completed,
        "turns": len(result.turns),
        "tokens": result.tokens_used,
        "has_errors": any(r.error for r in result.results),
        "responses_relevant": all(
            len(r.response) > 20 for r in result.results
        ),
    }
```

---

*Document Version: 2.0*
*Updated: December 6, 2025*
*Focus: LLM-simulated E2E testing without Kafka/API dependencies*
