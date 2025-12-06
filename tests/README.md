# Orbit Test Suite

This test suite implements the testing plan from `docs/testing_plan.md` to validate the Orbit dating agent logic layer without requiring Kafka brokers or real API calls.

## Structure

```
tests/
├── conftest.py              # Pytest fixtures (db_fx, api_stub, runner, event_fx)
├── helpers/
│   ├── event_builder.py     # Build KafkaEvent-like dicts for testing
│   ├── api_stub.py          # SeriesAPI stub that records calls
│   └── runner.py            # TestRunner for executing events through graph
├── unit/                    # Fast, deterministic unit tests
│   ├── test_config.py
│   ├── test_schemas.py
│   ├── test_router.py
│   ├── test_onboarding.py
│   ├── test_matching.py
│   └── test_mentor.py
├── integration/             # Full flow tests with stubbed dependencies
│   ├── test_onboarding_flow.py
│   ├── test_matching_flow.py
│   └── test_group_skip.py
├── simulation/               # LLM-simulated persona conversations
│   ├── personas.py          # Persona definitions
│   ├── driver.py            # ConversationDriver for LLM simulation
│   └── test_persona_conversations.py
└── edge/                    # Edge cases and error handling
    ├── test_malformed_input.py
    └── test_db_constraints.py
```

## Running Tests

### Fast Unit Tests (No LLM)
```bash
pytest tests/unit -v -m "not llm_slow"
```

### Integration Tests
```bash
pytest tests/integration -v
```

### LLM Simulation Tests (Requires OPENROUTER_API_KEY)
```bash
pytest tests/simulation -v -m llm_slow
```

### All Tests with Coverage
```bash
pytest --cov=src --cov-report=html --cov-branch
```

### Specific Test
```bash
pytest tests/integration/test_onboarding_flow.py::TestOnboardingFlow::test_complete_onboarding_happy_path -v
```

## Test Markers

- `@pytest.mark.unit` - Fast, deterministic unit tests
- `@pytest.mark.integration` - Integration tests with stubbed dependencies
- `@pytest.mark.llm_slow` - Tests that use real LLM calls (opt-in)

## Environment Setup

For LLM simulation tests, set:
```bash
export OPENROUTER_API_KEY=your-key-here
```

## Coverage Targets

- Core agent nodes: ≥90%
- Overall: ≥85% statements + branches

