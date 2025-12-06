# Quick Setup Checklist ✅

Follow these steps to get Orbit running locally:

## 1. Environment Setup

- [ ] Copy `.env.example` to `.env`:
  ```bash
  cp .env.example .env
  ```

- [ ] Open `.env` and fill in the following credentials:

### Required from Series Team:
- [ ] `KAFKA_SASL_PASSWORD` - Your Kafka password
- [ ] `SERIES_BASE_URL` - Series API host URL
- [ ] `SERIES_API_KEY` - Your Series API key
- [ ] `SERIES_SENDER_NUMBER` - Phone number to send from (usually pre-filled)

### Required from OpenRouter:
- [ ] `OPENROUTER_API_KEY` - Get from https://openrouter.ai/
  - Sign up at OpenRouter
  - Add credits to your account
  - Generate an API key

### Optional (already have defaults):
- [ ] `OPENROUTER_MODEL` - Change if you want a different model
- [ ] `DATABASE_PATH` - Change database location (default: `./orbit.db`)
- [ ] `LOG_LEVEL` - Set to `DEBUG` for verbose logging

## 2. Install Dependencies

- [ ] Install Python dependencies:
  ```bash
  pip install -r requirements.txt
  ```

Expected packages:
- kafka-python (Kafka consumer)
- httpx (HTTP client)
- langgraph (Agent framework)
- langchain-core (LLM abstractions)
- langchain-openai (OpenAI integration)
- pydantic (Data validation)
- python-dotenv (Environment variables)

## 3. Verify Setup

- [ ] Check your `.env` file has all required values filled:
  ```bash
  grep -v "^#" .env | grep "changeme\|YOUR_.*_HERE"
  ```
  (Should return nothing if all placeholders are replaced)

- [ ] Verify Python can import dependencies:
  ```bash
  python -c "import kafka, httpx, langgraph; print('✅ All imports successful')"
  ```

## 4. Run the Agent

- [ ] Start Orbit:
  ```bash
  python -m src.main
  ```

- [ ] Look for these startup messages:
  ```
  INFO:orbit:Building LangGraph agent...
  INFO:orbit:Orbit consumer started on topic team.team.xxxxx
  INFO:orbit:Dating agent ready with LangGraph
  ```

## 5. Test the Agent

### Send a test message via iMessage to the Series number

**Expected flow:**

1. **First message (any text)**:
   - Orbit: "Hey! What's your name?"

2. **Reply with your name**:
   - Orbit: "What are you looking for? Something casual, serious, or just exploring?"

3. **Continue through onboarding** (7 questions total)

4. **After onboarding**:
   - Orbit: "Thanks! I'll start looking for great matches. Want me to find someone now?"

5. **Try mentor features**:
   - You: "Help me with an icebreaker"
   - Orbit: (generates conversation starters)

## 6. Debugging

If something goes wrong:

### Check logs:
- [ ] Look at the terminal output for error messages
- [ ] Set `LOG_LEVEL=DEBUG` in `.env` for more details

### Common issues:

**"Missing required env var"**
- Check that `.env` exists in the project root
- Verify all required variables are set

**"LLM request failed"**
- Verify `OPENROUTER_API_KEY` is correct
- Check you have credits at https://openrouter.ai/

**"Kafka connection failed"**
- Verify `KAFKA_SASL_PASSWORD` is correct
- Check with Series team that your credentials are active

**"Database locked"**
- Only run one instance of Orbit at a time
- Delete `orbit.db` and restart if it's corrupted

### Check database:
```bash
sqlite3 orbit.db "SELECT * FROM users;"
sqlite3 orbit.db "SELECT * FROM profiles;"
```

## 7. Next Steps

Once running successfully:

- [ ] Test the complete onboarding flow
- [ ] Try matching with another test user
- [ ] Experiment with mentor features
- [ ] Review logs to understand the flow
- [ ] Check the database to see stored profiles

## Resources

- **Full README**: `README.md`
- **Product Design**: `docs/product_design_spec.md`
- **Implementation Plan**: `docs/implementation_plan.md`
- **API Documentation**: `openapi.json`

---

## Quick Reference

### Start Agent
```bash
python -m src.main
```

### Stop Agent
Press `Ctrl+C`

### View Logs (verbose)
```bash
LOG_LEVEL=DEBUG python -m src.main
```

### Reset Database
```bash
rm orbit.db
python -m src.main  # Will recreate tables
```

### Check Database
```bash
sqlite3 orbit.db ".schema"
sqlite3 orbit.db "SELECT * FROM users;"
```

---

**Need help?** Check the troubleshooting section in `README.md` or review the logs with `LOG_LEVEL=DEBUG`.

Good luck! 🚀
