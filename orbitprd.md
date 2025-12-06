# Orbit PRD

Human-centered dating concierge that lives in iMessage. Orbit interviews users, proposes curated matches, creates/hosts introductions in a 3-person chat, and remains available for private sidebar advice. Tone: casual, concise, lightly warm; proactive but not spammy.

## Goals and Success
- Match-ready profiles gathered with <3 cold-start messages.
- Double-consent intros that feel personal (shared interest/vibe cited in the opener).
- Orbit only speaks when helpful: intro, replies to @Orbit, context cards for stale chats, and sidebars.
- Reliable delivery: new DM pulled from Kafka within seconds; REST egress succeeds with retry/backoff.

## Non-Goals (MVP)
- Long-term compatibility scoring or ranking algorithms.
- Rich media beyond text/emoji and simple attachments.
- Multi-language support.

## User Flow
1) Onboarding (DM): detect new number -> ask 3 prompts  
  - Name + one passion.  
  - Ideal weekend vibe (3 words).  
  - Hard dealbreakers.  
   Store profile; move to BROWSING.  
2) Matching: when in BROWSING, scan for overlap (>=1 shared interest or vibe tag). Propose: "Found [Name]; you both vibe on [shared]. Intro?" -> set both to PENDING_INTRO.  
3) Consent: require "yes" from both. Decline returns both to BROWSING with a brief acknowledgement.  
4) Introduction: create group chat; opener cites shared interest and a personal detail. Set both to IN_ORBIT.  
5) Hosting:  
  - @Orbit mentions -> parse intent and respond.  
  - Stale threshold -> inject a context card (one-liner prompt).  
  - Otherwise stay quiet.  
6) Sidebar: If someone in IN_ORBIT DMs Orbit, respond with advice based on stored interests and recent chat context.  
7) Close-out (future): detect conversation wind-down; thank and optionally ask for feedback; set users back to BROWSING or PAUSED.

## State Machine
- ONBOARDING -> after answering 3 prompts -> BROWSING.  
- BROWSING -> proposed match sent -> PENDING_INTRO.  
- PENDING_INTRO -> both accept -> IN_ORBIT; if decline/no response timeout -> BROWSING.  
- IN_ORBIT -> close-out or long inactivity -> BROWSING; manual opt-out -> PAUSED.  
Persist `conversation_state`, `current_match_id`, `active_group_chat_id`, and timestamps for stale checks.

## Data Model (MVP)
- User: phone_number (E.164, PK), name, status, profile {bio/vibe/interests/dealbreakers}, current_match_id, active_group_chat_id, last_seen_at, last_intro_at, consent flags.  
- Match proposal: id, user_a, user_b, shared_interests, proposed_at, state (proposed/accepted/declined/expired).  
- Storage: start with JSON or SQLite; abstract via `UserStore` so migration is trivial. Ensure atomic writes; backup files in `data/`.

## System Architecture
- KafkaListener: SASL_SSL consumer for the configured topic; commits offsets after successful handling.  
- EventRouter: inspects `chat_handles` to determine DM vs group; dispatches to private or group handler.  
- Engine: onboarding script, matching engine, sidebar logic, stale detection.  
- SeriesClient: REST wrapper to iMessage service (see API section) with retries, backoff, and error logging.  
- Config: environment-driven; no secrets in code.  
- Logging/metrics: structured logs with event type, chat_id, user phone; counters for ingress, sends, failures, retries.

## Transport Contracts
- Ingress (Kafka): topic configured via env; event type `message.received`. Payload (JSON):
  ```
  {
    "event_type": "message.received",
    "data": {
      "chat_id": 12345,
      "text": "...",
      "from_phone": "+1...",
      "chat_handles": ["+1...", "+1..."]
    }
  }
  ```
  DM if `chat_handles` length == 2; group if >2.
- Egress (REST, see openapi.json):  
  - Send: POST `/api/chats/{chat_id}/chat_messages` body `{ "message": { "text": "...", "attachments": [...] } }`  
  - Create chat: POST `/api/chats` with `{ "chat": { "phone_numbers": [...] , "display_name": "Connect: A & B" }, "message": { "text": "Intro..." }, "send_from": "<sender_number>" }` -> returns `chat.id`.  
  - Typing indicator: POST `/api/chats/{id}/start_typing`.  
  - Reaction: POST `/api/chat_messages/{id}/reactions` with type in {love, like, laugh, emphasize, question}.  
  Auth: Bearer token header; base URL configurable.

## Env and Secrets (.env example)
Do not commit actual values. Expected keys:
- `KAFKA_BOOTSTRAP_SERVERS`  
- `KAFKA_TOPIC`  
- `KAFKA_CONSUMER_GROUP`  
- `KAFKA_CLIENT_ID`  
- `KAFKA_SASL_USERNAME`  
- `KAFKA_SASL_PASSWORD` (or API secret)  
- `KAFKA_SECURITY_PROTOCOL=SASL_SSL` and `KAFKA_SASL_MECHANISM=PLAIN`  
- `SERIES_BASE_URL`  
- `SERIES_API_KEY` (Bearer token)  
- `SERIES_SENDER_NUMBER` (E.164)  
Add optional `LOG_LEVEL`, `REQUEST_TIMEOUT_SEC`, `MAX_RETRIES`, `STALE_THRESHOLD_MIN`.

## Conversation Logic Details
- Onboarding prompts use short, friendly tone; send typing indicator before multi-part replies for natural pacing.  
- Proposal message references at least one shared interest or vibe tag.  
- Intro opener template: "Hi! [A], meet [B]. You both vibe on [shared]. [A] just [personal detail]. Have fun" (emoji optional).  
- Stale intervention: after threshold, drop a single prompt then back off.  
- Sidebar advice pulls last seen message in the group plus profile interests to suggest a question or callback.

## Error Handling & Retries
- Kafka: catch and log deserialization errors; skip/park poison messages after N failures.  
- REST: retry idempotent sends with exponential backoff and jitter; surface non-2xx with context (chat_id, user).  
- Persistence: fsync writes for JSON store; guard against partial writes with temp files and rename.  
- Idempotency: de-dup incoming events by message id if provided; otherwise rely on offsets.

## Implementation Plan (code layout in /src)
- `main.py`: wire config, initialize Kafka consumer loop, and call `process_event`.  
- `config.py`: load env, provide typed accessors.  
- `client.py`: SeriesClient with send/create/typing/reaction helpers.  
- `store.py`: UserStore abstraction (JSON/SQLite).  
- `engine.py`: router, handlers, onboarding script, matching engine, sidebar + stale logic.  
- `utils.py`: phone normalization, logging helpers, simple templates.

## Testing Plan
- Unit: parsing event -> routing; state transitions; matching selection; message templates.  
- Integration (local): stub Series API via requests-mock; feed sample Kafka events into `process_event`; verify side effects.  
- Manual: run consumer against dev topic with seeded users; validate intro creation and sidebar responses.

## Operational Notes
- Start consumer with the configured group to preserve offsets.  
- Health: log startup config (without secrets), connection readiness, and per-send latency.  
- Back-pressure: pause/resume Kafka consumption if REST failures spike.  
- Safety: rate-limit sends per chat; enforce a max daily messages per user to avoid spam.  
- Future: move persistence to hosted DB, add analytics, add richer consent (pause/stop keywords).
