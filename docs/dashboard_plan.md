# Orbit Dashboard: Implementation Plan

## Executive Summary

A lightweight monitoring dashboard for the Orbit dating agent that provides real-time visibility into users, profiles, matches, and agent activity. Designed to be demo-ready within 2-3 hours.

---

## Feasibility Assessment

### ✅ What We Can Expose (Already Available)

| Data Source | What's Available | Effort |
|-------------|------------------|--------|
| **Users Table** | phone, name, status, created_at, dating_enabled | Low |
| **Profiles Table** | profile_summary, looking_for_summary, interests, dealbreakers, completeness, onboarding_step | Low |
| **Matches Table** | user pairs, bilateral_score, status, decisions, timestamps | Low |
| **Conversation State** | current_node, context JSON, match_in_progress | Low |
| **Agent Routing** | Intent classification (needs event logging) | Medium |
| **Live Messages** | Kafka events (needs in-memory buffer) | Medium |

### 🔧 What Needs to Be Added

1. **Event logging table** - Store processed messages for history view
2. **In-memory event buffer** - For real-time dashboard updates
3. **Dashboard API endpoints** - FastAPI routes
4. **Frontend UI** - HTML + TailwindCSS + Alpine.js

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORBIT + DASHBOARD                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐      ┌──────────────────────────────────────────┐         │
│  │    Kafka     │─────▶│           Main Agent Loop                │         │
│  │   Consumer   │      │  (existing: src/main.py)                 │         │
│  └──────────────┘      └───────────────────┬──────────────────────┘         │
│                                            │                                 │
│                                            │ logs events                     │
│                                            ▼                                 │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                        SQLite Database                            │       │
│  │  users │ profiles │ matches │ conversation_state │ event_log     │       │
│  └────────────────────────────────┬─────────────────────────────────┘       │
│                                   │                                          │
│                                   │ queries                                  │
│                                   ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                    Dashboard API (FastAPI)                        │       │
│  │  GET /api/users      GET /api/matches     GET /api/events        │       │
│  │  GET /api/profiles   GET /api/stats       SSE /api/live          │       │
│  └────────────────────────────────┬─────────────────────────────────┘       │
│                                   │                                          │
│                                   │ serves                                   │
│                                   ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                    Dashboard UI (HTML/JS)                         │       │
│  │  TailwindCSS + Alpine.js + htmx                                  │       │
│  │  • Users panel    • Matches panel    • Live feed                 │       │
│  │  • Profile cards  • Stats overview   • Agent flow viz            │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack Choice

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Backend** | FastAPI | Async, modern, pairs with httpx |
| **CSS** | TailwindCSS (CDN) | Beautiful UI, no build step |
| **Reactivity** | Alpine.js | Lightweight, no npm required |
| **Live Updates** | htmx + SSE | Real-time without WebSocket complexity |
| **Templates** | Jinja2 | Built into FastAPI, familiar syntax |

**Why not React/Vue?**
- Hackathon constraint: no time for npm/webpack setup
- Single-file deployment is faster to iterate
- CDN-based tools work immediately

---

## Database Additions

### New Table: `event_log`

```sql
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_id INTEGER,
    phone_number TEXT,
    event_type TEXT NOT NULL,         -- 'message_in', 'message_out', 'intent', 'match_created', etc.
    intent TEXT,                       -- classified intent if applicable
    node TEXT,                         -- which node processed
    message_preview TEXT,              -- first 100 chars of message
    metadata TEXT,                     -- JSON blob for extra data
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_user ON event_log(user_id);
```

---

## API Endpoints

### Dashboard Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Dashboard HTML page |
| `GET` | `/api/stats` | Overview statistics |
| `GET` | `/api/users` | List all users with profiles |
| `GET` | `/api/users/{id}` | Single user detail |
| `GET` | `/api/profiles` | All profiles with user info |
| `GET` | `/api/matches` | All matches with user names |
| `GET` | `/api/events` | Recent event log (paginated) |
| `GET` | `/api/events/stream` | SSE endpoint for live events |

### Response Schemas

```python
# Stats Response
{
    "total_users": 12,
    "active_users": 8,
    "onboarding_users": 4,
    "total_matches": 5,
    "mutual_matches": 2,
    "pending_matches": 3,
    "avg_profile_completeness": 0.72,
    "events_today": 45
}

# User List Response
{
    "users": [
        {
            "id": 1,
            "phone_number": "+1234567890",
            "name": "Alex",
            "status": "active",
            "dating_enabled": true,
            "created_at": "2025-12-06T10:00:00Z",
            "profile": {
                "completeness": 0.85,
                "onboarding_step": 7,
                "relationship_goal": "serious",
                "profile_summary": "Alex is a software engineer..."
            }
        }
    ]
}

# Match List Response
{
    "matches": [
        {
            "id": 1,
            "user_a": {"id": 1, "name": "Alex"},
            "user_b": {"id": 2, "name": "Jordan"},
            "bilateral_score": 78.5,
            "status": "mutual",
            "user_a_decision": "yes",
            "user_b_decision": "yes",
            "created_at": "2025-12-06T12:00:00Z"
        }
    ]
}

# Event Stream (SSE)
data: {"type": "message_in", "user": "Alex", "preview": "I'm looking for...", "timestamp": "..."}
data: {"type": "intent", "user": "Alex", "intent": "onboarding", "node": "onboarding"}
data: {"type": "message_out", "user": "Alex", "preview": "Great! Tell me more...", "timestamp": "..."}
```

---

## UI Design

### Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🪐 Orbit Dashboard                                    [Live ●] 12:34:56 PM  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │   👥 12     │ │   💚 8      │ │   💕 5      │ │   ✨ 2      │            │
│  │   Users     │ │   Active    │ │   Matches   │ │   Mutual    │            │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘            │
│                                                                              │
├────────────────────────────────────────┬────────────────────────────────────┤
│  Users & Profiles                      │  Live Event Feed                   │
│  ┌──────────────────────────────────┐  │  ┌────────────────────────────────┐│
│  │ 🟢 Alex        [85%] ████████░░  │  │  │ 12:34:56 → Alex                ││
│  │    "Looking for serious..."      │  │  │ Intent: onboarding              ││
│  │    Goal: Serious | Step: 7/8     │  │  │ "Tell me about yourself"        ││
│  ├──────────────────────────────────┤  │  ├────────────────────────────────┤│
│  │ 🟡 Jordan      [60%] ██████░░░░  │  │  │ 12:34:42 ← Jordan              ││
│  │    "Creative soul who..."        │  │  │ Response sent                   ││
│  │    Goal: Exploring | Step: 5/8   │  │  │ "What are your interests?"      ││
│  ├──────────────────────────────────┤  │  ├────────────────────────────────┤│
│  │ 🔵 Sam         [100%] ██████████ │  │  │ 12:33:15 💕 Match Created       ││
│  │    "Engineer by day..."          │  │  │ Alex ↔ Jordan (score: 78)       ││
│  │    Goal: Serious | Step: 8/8     │  │  │                                 ││
│  └──────────────────────────────────┘  │  └────────────────────────────────┘│
│                                        │                                     │
├────────────────────────────────────────┴────────────────────────────────────┤
│  Matches                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────┤
│  │ Alex ↔ Jordan    Score: 78    Status: 🟡 pending_b    A: ✅ B: ⏳       │
│  │ Sam ↔ Riley      Score: 85    Status: 💚 mutual       A: ✅ B: ✅       │
│  │ Chris ↔ Taylor   Score: 62    Status: ❌ rejected     A: ✅ B: ❌       │
│  └──────────────────────────────────────────────────────────────────────────┤
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Color Scheme (Dark Theme)

```css
:root {
    --bg-primary: #0f0f23;      /* Deep space blue */
    --bg-secondary: #1a1a3e;    /* Card backgrounds */
    --bg-tertiary: #252550;     /* Hover states */
    --accent-primary: #7c3aed;  /* Purple - brand */
    --accent-success: #10b981;  /* Green - active/mutual */
    --accent-warning: #f59e0b;  /* Amber - pending */
    --accent-danger: #ef4444;   /* Red - rejected */
    --text-primary: #e2e8f0;    /* Light text */
    --text-secondary: #94a3b8;  /* Muted text */
    --border: #374151;          /* Subtle borders */
}
```

### Key UI Components

1. **Stats Cards** - Top row with key metrics, animated counters
2. **User List** - Expandable cards with profile preview, progress bar
3. **Match List** - Table view with status badges, bilateral scores
4. **Live Feed** - Auto-scrolling event stream with color-coded types
5. **Agent Flow** - Simple visualization of intent → node routing

---

## File Structure

```
src/
├── dashboard/
│   ├── __init__.py
│   ├── app.py              # FastAPI application
│   ├── routes.py           # API endpoints
│   ├── queries.py          # Dashboard-specific queries
│   └── templates/
│       └── index.html      # Single-page dashboard
│
├── db/
│   ├── database.py         # Add event_log table
│   └── queries.py          # Add EventLogQueries class
│
└── main.py                 # Add event logging calls
```

---

## Implementation Steps

### Phase 1: Database & Logging (30 min)

1. Add `event_log` table to `database.py`
2. Create `EventLogQueries` class in `queries.py`
3. Add logging calls to `main.py` process_event function
4. Add logging calls to each node (router, onboarding, matching, mentor)

### Phase 2: Dashboard API (45 min)

1. Create `src/dashboard/app.py` with FastAPI app
2. Implement `/api/stats` endpoint
3. Implement `/api/users` and `/api/profiles` endpoints
4. Implement `/api/matches` endpoint
5. Implement `/api/events` endpoint
6. Implement `/api/events/stream` SSE endpoint

### Phase 3: Dashboard UI (60 min)

1. Create `templates/index.html` with base structure
2. Add TailwindCSS + Alpine.js + htmx via CDN
3. Build stats cards section
4. Build users/profiles panel
5. Build matches panel
6. Build live event feed with SSE connection

### Phase 4: Integration & Polish (30 min)

1. Add dashboard startup to main.py (run in thread)
2. Test end-to-end flow
3. Add error handling and loading states
4. Polish styling and animations

---

## Running the Dashboard

### Option A: Separate Process (Recommended for Demo)

```bash
# Terminal 1: Run main agent
python -m src.main

# Terminal 2: Run dashboard
python -m src.dashboard.app
# Dashboard at http://localhost:8080
```

### Option B: Integrated (Single Process)

```python
# In main.py, run dashboard in background thread
import threading
from src.dashboard.app import create_app

def start_dashboard():
    import uvicorn
    app = create_app(db)
    uvicorn.run(app, host="0.0.0.0", port=8080)

threading.Thread(target=start_dashboard, daemon=True).start()
```

---

## Demo Script

1. **Open dashboard** at `http://localhost:8080`
2. **Show empty state** - "No users yet"
3. **Send first message** via iMessage to trigger onboarding
4. **Watch live feed** update in real-time
5. **Show user appear** with profile building progress
6. **Complete onboarding** - watch completeness reach 100%
7. **Trigger match** - show match appear with bilateral score
8. **Both accept** - show status change to "mutual"
9. **Highlight** the bilateral scoring and double opt-in flow

---

## Time Estimate

| Phase | Time | Cumulative |
|-------|------|------------|
| Database & Logging | 30 min | 30 min |
| Dashboard API | 45 min | 1h 15min |
| Dashboard UI | 60 min | 2h 15min |
| Integration & Polish | 30 min | 2h 45min |
| **Total** | **~3 hours** | |

---

## Dependencies to Add

```
# Add to requirements.txt
fastapi>=0.100.0
uvicorn>=0.23.0
jinja2>=3.1.0
sse-starlette>=1.6.0
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| SSE not working | Fall back to polling every 2s |
| SQLite locking | Use WAL mode, separate connections |
| UI takes too long | Start with minimal layout, add features |
| Dashboard crashes agent | Run in separate process |

---

## Future Enhancements (Post-Hackathon)

- [ ] User detail modal with full conversation history
- [ ] Match analytics (score distribution, conversion rates)
- [ ] Agent flow diagram with live highlighting
- [ ] Profile editing via dashboard
- [ ] Message replay/debugging tools
- [ ] Export data to CSV
- [ ] Authentication for dashboard access

---

*Document Version: 1.0*
*Created: December 6, 2025*
*Estimated Build Time: 3 hours*

