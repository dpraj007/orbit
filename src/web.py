"""Pastel dashboard for Orbit state + quick actions."""
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .api import SeriesAPI
from .config import Config
from .db import Database
from .fastlane import DHAIRYA_PHONE, LEON_PHONE, ensure_tester_profiles, run_fastlane, send_with_typing
from .utils import get_llm, setup_logger

# Try to import Kafka consumer
try:
    from .kafka import build_consumer, KafkaEvent
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

# Shared error list for toast notifications
_errors: list[dict] = []
_errors_lock = threading.Lock()

# Live events from Kafka
_live_events: list[dict] = []
_live_events_lock = threading.Lock()

# Fastlane state tracking
_fastlane_state: dict = {"stage": "idle", "chat_id": None, "activity": []}
_fastlane_lock = threading.Lock()


def add_error(source: str, message: str) -> None:
    """Add an error to the shared error list."""
    import time
    with _errors_lock:
        _errors.append({"source": source, "message": message, "ts": time.time()})
        # Keep only last 50 errors
        while len(_errors) > 50:
            _errors.pop(0)


def get_errors(since: float = 0) -> list[dict]:
    """Get errors since timestamp."""
    with _errors_lock:
        return [e for e in _errors if e["ts"] > since]


def clear_errors() -> None:
    """Clear all errors."""
    with _errors_lock:
        _errors.clear()


# Queue for fastlane to consume Kafka messages
_fastlane_inbox: list[dict] = []
_fastlane_inbox_lock = threading.Lock()


def add_live_event(event: dict) -> None:
    """Add a live event from Kafka."""
    with _live_events_lock:
        _live_events.append({**event, "ts": time.time()})
        # Keep only last 100 events
        while len(_live_events) > 100:
            _live_events.pop(0)
    # Also push to fastlane inbox if it's a message from a known user
    if event.get("is_known") and event.get("text"):
        with _fastlane_inbox_lock:
            _fastlane_inbox.append(event)


def get_fastlane_inbox() -> list[dict]:
    """Get and clear pending Kafka messages for fastlane."""
    with _fastlane_inbox_lock:
        msgs = list(_fastlane_inbox)
        _fastlane_inbox.clear()
        return msgs


def inject_fastlane_message(from_phone: str, text: str, chat_id: int = 0) -> None:
    """Inject a fake message into fastlane inbox for testing."""
    import time
    with _fastlane_inbox_lock:
        _fastlane_inbox.append({
            "from_phone": from_phone,
            "text": text,
            "chat_id": chat_id,
            "message_id": int(time.time() * 1000),
            "is_known": True,
        })


def get_live_events(since: float = 0) -> list[dict]:
    """Get live events since timestamp."""
    with _live_events_lock:
        return [e for e in _live_events if e.get("ts", 0) > since]


def update_fastlane_state(stage: str = None, chat_id: int = None, activity: str = None) -> None:
    """Update fastlane state for dashboard."""
    with _fastlane_lock:
        if stage is not None:
            _fastlane_state["stage"] = stage
        if chat_id is not None:
            _fastlane_state["chat_id"] = chat_id
        if activity is not None:
            _fastlane_state["activity"].append({"msg": activity, "ts": time.time()})
            # Keep last 20 activities
            _fastlane_state["activity"] = _fastlane_state["activity"][-20:]


def get_fastlane_state() -> dict:
    """Get current fastlane state."""
    with _fastlane_lock:
        return dict(_fastlane_state)


class OrbitWeb(BaseHTTPRequestHandler):
    cfg: Config
    db: Database
    api: SeriesAPI
    log: logging.Logger
    llm = None
    fastlane_thread: threading.Thread | None = None
    fastlane_stop: threading.Event | None = None

    def _json(self, payload, status: int = 200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, content: str, status: int = 200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_GET(self):  # type: ignore[override]
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html(self._page())
            return
        if parsed.path == "/api/summary":
            self._json(self._summary())
            return
        if parsed.path == "/api/fastlane/status":
            state = get_fastlane_state()
            self._json({
                "running": self.fastlane_thread is not None and self.fastlane_thread.is_alive(),
                "stage": state["stage"],
                "chat_id": state["chat_id"],
                "activity": state["activity"][-10:]  # Last 10 activities
            })
            return
        if parsed.path == "/api/live":
            qs = parse_qs(parsed.query)
            since = float(qs.get("since", ["0"])[0])
            self._json({"events": get_live_events(since)})
            return
        if parsed.path == "/api/errors":
            qs = parse_qs(parsed.query)
            since = float(qs.get("since", ["0"])[0])
            self._json({"errors": get_errors(since)})
            return
        if parsed.path == "/api/messages":
            qs = parse_qs(parsed.query)
            chat_id = int(qs.get("chat_id", ["0"])[0])
            msgs = self.api.list_chat_messages(chat_id, per_page=50)
            self._json({"messages": msgs})
            return
        self._html("<h1>404</h1>", status=404)

    def do_POST(self):  # type: ignore[override]
        parsed = urlparse(self.path)
        body = self._read_body()

        if parsed.path == "/api/ping-leon":
            self._action_ping_leon()
            return
        if parsed.path == "/api/intro":
            self._action_intro()
            return
        if parsed.path == "/api/fastlane/start":
            self._action_fastlane_start()
            return
        if parsed.path == "/api/fastlane/stop":
            self._action_fastlane_stop()
            return
        if parsed.path == "/api/errors/clear":
            clear_errors()
            self._json({"ok": True})
            return
        if parsed.path == "/api/send":
            chat_id = int(body.get("chat_id") or 0)
            text = (body.get("text") or "").strip()
            if not chat_id or not text:
                self._json({"error": "chat_id and text required"}, status=400)
                return
            try:
                self.api.start_typing(chat_id)
            except Exception:
                pass
            self.api.send_message(chat_id, text)
            self._json({"ok": True})
            return
        if parsed.path == "/api/simulate-leon":
            # Simulate a message from Leon for testing when Kafka isn't working
            text = (body.get("text") or "").strip()
            if not text:
                self._json({"error": "text required"}, status=400)
                return
            inject_fastlane_message(LEON_PHONE, text)
            self.log.info("Simulated Leon message: %s", text)
            self._json({"ok": True})
            return

        self._html("<h1>404</h1>", status=404)

    def _summary(self) -> dict:
        users = []
        for row in self.db.conn.execute(
            """
            SELECT u.id, u.phone_number, u.name, u.status, u.updated_at, p.profile_summary, p.looking_for_summary
            FROM users u
            LEFT JOIN profiles p ON p.user_id = u.id
            ORDER BY u.updated_at DESC
            LIMIT 200
            """
        ).fetchall():
            users.append(
                {
                    "id": row["id"],
                    "phone": row["phone_number"],
                    "name": row["name"] or "",
                    "status": row["status"] or "",
                    "updated_at": row["updated_at"] or "",
                    "summary": row["profile_summary"] or "",
                    "looking_for": row["looking_for_summary"] or "",
                }
            )

        matches = []
        for row in self.db.conn.execute(
            """
            SELECT m.id, ua.phone_number as user_a, ub.phone_number as user_b,
                   m.bilateral_score, m.status, m.user_a_decision, m.user_b_decision, m.created_at
            FROM matches m
            JOIN users ua ON ua.id = m.user_a_id
            JOIN users ub ON ub.id = m.user_b_id
            ORDER BY m.id DESC
            LIMIT 200
            """
        ).fetchall():
            matches.append(
                {
                    "id": row["id"],
                    "user_a": row["user_a"],
                    "user_b": row["user_b"],
                    "score": row["bilateral_score"],
                    "status": row["status"],
                    "decisions": f"{row['user_a_decision']}/{row['user_b_decision']}",
                    "created_at": row["created_at"],
                }
            )

        chats = []
        try:
            for chat in self.api.list_chats(per_page=50):
                handles = ", ".join(
                    h.get("phone_number", "") for h in chat.get("chat_handles", []) if isinstance(h, dict)
                )
                chats.append(
                    {
                        "id": chat.get("id"),
                        "name": chat.get("display_name", ""),
                        "group": chat.get("group"),
                        "handles": handles,
                        "message_count": chat.get("message_count"),
                    }
                )
        except Exception as exc:
            self.log.warning("List chats failed: %s", exc)

        return {"users": users, "matches": matches, "chats": chats}

    def _action_ping_leon(self):
        self._ensure_llm()
        ensure_tester_profiles(self.db)
        leon = self.db.users.get_by_phone(LEON_PHONE)
        chat_id = leon["chat_id"] if leon else None
        if not chat_id:
            try:
                created = self.api.create_chat(LEON_PHONE, "")
                # API returns {"data": {"id": ..., ...}} per OpenAPI spec
                chat_id = created.get("data", {}).get("id") or created.get("id")
                if leon and chat_id:
                    self.db.users.update_chat_id(leon["id"], chat_id)
            except Exception as exc:
                add_error("ping-leon", f"Failed to create chat: {exc}")
                self._json({"error": str(exc)}, status=500)
                return
        if not chat_id:
            add_error("ping-leon", "No chat for Leon")
            self._json({"error": "No chat for Leon"}, status=500)
            return
        try:
            opener = self.llm.invoke(
                "Write a 2-sentence, cotton-candy warm DM as Orbit to Leon to start chatting."
            ).content
            send_with_typing(self.api, chat_id, opener)
        except Exception as exc:
            add_error("ping-leon", f"Failed to send message: {exc}")
            self._json({"error": str(exc)}, status=500)
            return
        self._json({"ok": True, "chat_id": chat_id})

    def _action_intro(self):
        self._ensure_llm()
        ensure_tester_profiles(self.db)
        try:
            intro = self.llm.invoke(
                "Write a breezy intro between Leon and Dhairyasheel citing coffee and sci-fi. 1-2 sentences."
            ).content
            created = self.api.create_group_chat([LEON_PHONE, DHAIRYA_PHONE], intro, display_name="Connect")
            # API returns {"data": {"id": ..., ...}} per OpenAPI spec
            gid = created.get("data", {}).get("id") or created.get("id")
            if gid:
                send_with_typing(
                    self.api,
                    gid,
                    "I'll hang back. If you need me, @Orbit for a nudge. Have fun!",
                    delay=0.8,
                )
            self._json({"ok": True, "group_chat_id": gid})
        except Exception as exc:
            add_error("intro", f"Failed to create intro: {exc}")
            self._json({"error": str(exc)}, status=500)

    def _ensure_llm(self):
        if self.llm is None:
            self.llm = get_llm(temperature=0.7)

    def _action_fastlane_start(self):
        if self.fastlane_thread and self.fastlane_thread.is_alive():
            self._json({"running": True})
            return
        self._ensure_llm()
        ensure_tester_profiles(self.db)
        self.fastlane_stop = threading.Event()
        self.fastlane_thread = threading.Thread(
            target=run_fastlane,
            args=(self.cfg, self.db, self.api),
            kwargs={
                "llm": self.llm,
                "log": self.log,
                "stop_event": self.fastlane_stop,
                "on_error": add_error,
                "on_state_change": update_fastlane_state,
                "get_kafka_inbox": get_fastlane_inbox,
            },
            daemon=True,
        )
        self.fastlane_thread.start()
        self._json({"running": True})

    def _action_fastlane_stop(self):
        if self.fastlane_stop:
            self.fastlane_stop.set()
        if self.fastlane_thread:
            self.fastlane_thread.join(timeout=2)
        self.fastlane_thread = None
        self.fastlane_stop = None
        update_fastlane_state(stage="idle", chat_id=None, activity="Demo stopped")
        self._json({"running": False})

    def _page(self) -> str:
        return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Orbit Dashboard</title>
  <style>
    :root {{
      --bg: radial-gradient(circle at 20% 20%, #ffe7ff 0, #ffdff5 25%, #f3d9ff 45%, #d5c7ff 70%, #b9b4ff 100%);
      --card: rgba(255, 255, 255, 0.74);
      --accent: #d26bff;
      --accent2: #ff7ac6;
      --text: #2d1b3c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
    }}
    header {{
      padding: 24px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      letter-spacing: 0.5px;
    }}
    .pill {{
      background: linear-gradient(120deg, var(--accent), var(--accent2));
      color: #fff;
      padding: 10px 16px;
      border-radius: 999px;
      font-weight: 600;
      box-shadow: 0 10px 30px rgba(210, 107, 255, 0.35);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      padding: 0 32px 32px;
    }}
    .card {{
      background: var(--card);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(255,255,255,0.4);
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 15px 40px rgba(142, 102, 255, 0.15);
    }}
    .card h2 {{
      margin: 0 0 12px;
      font-size: 18px;
    }}
    .list {{ max-height: 360px; overflow: auto; padding-right: 8px; }}
    .row {{
      padding: 10px;
      border-radius: 12px;
      margin-bottom: 8px;
      background: rgba(255,255,255,0.8);
    }}
    .row small {{ color: #6b557a; display: block; margin-top: 4px; }}
    .row.clickable {{ cursor: pointer; }}
    .row.clickable:hover {{ background: rgba(210, 107, 255, 0.15); }}
    .msg {{ padding: 8px 12px; border-radius: 10px; margin-bottom: 6px; max-width: 80%; }}
    .msg.sent {{ background: linear-gradient(120deg, var(--accent), var(--accent2)); color: #fff; margin-left: auto; }}
    .msg.received {{ background: rgba(255,255,255,0.9); }}
    .msg small {{ font-size: 11px; opacity: 0.7; }}
    #convo-modal {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 999; align-items: center; justify-content: center; }}
    #convo-modal.open {{ display: flex; }}
    #convo-box {{ background: #fff; border-radius: 16px; width: 90%; max-width: 500px; max-height: 80vh; display: flex; flex-direction: column; }}
    #convo-header {{ padding: 16px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }}
    #convo-messages {{ flex: 1; overflow: auto; padding: 16px; display: flex; flex-direction: column; }}
    #convo-footer {{ padding: 12px; border-top: 1px solid #eee; display: flex; gap: 8px; }}
    #convo-footer input {{ flex: 1; }}
    button {{
      background: linear-gradient(120deg, var(--accent), var(--accent2));
      border: none;
      color: #fff;
      border-radius: 12px;
      padding: 10px 14px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 10px 24px rgba(210, 107, 255, 0.4);
      transition: transform 0.1s ease;
    }}
    button:active {{ transform: translateY(1px); }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }}
    .badge {{ background: #f5e9ff; color: #7c4fd1; padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
    .input-row {{ display: flex; gap: 8px; margin-top: 8px; }}
    input {{
      flex: 1;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid rgba(0,0,0,0.08);
      font-size: 14px;
    }}
    #toast-container {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      z-index: 1000;
      max-width: 400px;
    }}
    .toast {{
      background: #ff4757;
      color: #fff;
      padding: 12px 16px;
      border-radius: 12px;
      box-shadow: 0 8px 24px rgba(255, 71, 87, 0.4);
      animation: slideIn 0.3s ease;
      cursor: pointer;
      font-size: 13px;
    }}
    .toast strong {{
      display: block;
      margin-bottom: 4px;
    }}
    @keyframes slideIn {{
      from {{ transform: translateX(100%); opacity: 0; }}
      to {{ transform: translateX(0); opacity: 1; }}
    }}
    .demo-btn {{
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      text-align: left;
      padding: 12px 16px;
      min-width: 180px;
    }}
    .demo-btn .title {{ font-size: 14px; font-weight: 600; }}
    .demo-btn .desc {{ font-size: 11px; opacity: 0.85; margin-top: 4px; font-weight: normal; }}
    .demo-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    .status-panel {{
      background: rgba(45, 27, 60, 0.05);
      border-radius: 12px;
      padding: 12px;
      margin-top: 12px;
    }}
    .status-panel h3 {{ margin: 0 0 8px; font-size: 14px; }}
    .activity-log {{ font-size: 12px; max-height: 150px; overflow: auto; }}
    .activity-log div {{ padding: 4px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }}
    .chat-row {{ display: flex; align-items: center; gap: 12px; }}
    .chat-row .chat-info {{ flex: 1; min-width: 0; }}
    .chat-row .chat-preview {{ font-size: 12px; color: #6b557a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .chat-row .chat-meta {{ font-size: 11px; color: #999; }}
    .chat-row .msg-count {{ background: var(--accent); color: #fff; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 600; }}
    .live-indicator {{ display: inline-block; width: 8px; height: 8px; background: #2ecc71; border-radius: 50%; margin-right: 6px; animation: pulse 1.5s infinite; }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
    .stage-badge {{ background: #2ecc71; color: #fff; padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
    .stage-badge.idle {{ background: #95a5a6; }}
    .stage-badge.wait_leon {{ background: #3498db; }}
    .stage-badge.ask_intro {{ background: #9b59b6; }}
    .stage-badge.group_live {{ background: #2ecc71; }}
    .stage-badge.done {{ background: #7f8c8d; }}
  </style>
</head>
<body>
  <div id="toast-container"></div>
  <div id="convo-modal" onclick="if(event.target===this)closeConvo()">
    <div id="convo-box">
      <div id="convo-header">
        <strong id="convo-title">Chat</strong>
        <button onclick="closeConvo()" style="padding:6px 12px">✕</button>
      </div>
      <div id="convo-messages"></div>
      <div id="convo-footer">
        <input id="convo-input" type="text" placeholder="Type a message..." onkeydown="if(event.key==='Enter')sendConvoMsg()" />
        <button onclick="sendConvoMsg()">Send</button>
      </div>
    </div>
  </div>
  <header>
    <div>
      <h1>🚀 Orbit Control</h1>
      <div class="pill"><span class="live-indicator"></span>Live Dashboard</div>
    </div>
  </header>
  
  <!-- Demo Actions Section -->
  <div style="padding: 0 32px 16px; display: flex; gap: 12px; flex-wrap: wrap;">
    <button class="demo-btn" onclick="pingLeon()" id="btn-ping">
      <span class="title">💬 DM Leon</span>
      <span class="desc">Send a friendly opener to Leon's phone</span>
    </button>
    <button class="demo-btn" onclick="intro()" id="btn-intro">
      <span class="title">🤝 Create Intro</span>
      <span class="desc">Introduce Leon ↔ Dhairyasheel in a group chat</span>
    </button>
    <button class="demo-btn" onclick="toggleFastlane()" id="fastlane-btn">
      <span class="title">⚡ Auto Demo</span>
      <span class="desc" id="fastlane-desc">Run the full onboarding flow automatically</span>
    </button>
  </div>
  
  <div class="grid">
    <!-- Fastlane Status Panel -->
    <div class="card">
      <h2>🎯 Demo Status</h2>
      <div id="fastlane-status">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
          <span>State:</span>
          <span class="stage-badge idle" id="stage-badge">idle</span>
          <span id="watching-chat" style="font-size:12px;color:#666;"></span>
        </div>
        <div class="status-panel">
          <h3>Activity Log</h3>
          <div class="activity-log" id="activity-log">No activity yet...</div>
        </div>
        <div class="input-row" style="margin-top:12px;">
          <input id="simulate-text" type="text" placeholder="Simulate Leon's reply..." onkeydown="if(event.key==='Enter')simulateLeon()" />
          <button onclick="simulateLeon()" style="background:#3498db;">📱 Fake Leon</button>
        </div>
        <small style="color:#999;display:block;margin-top:4px;">Use this when Kafka isn't delivering messages</small>
      </div>
    </div>
    
    <!-- Chats Panel -->
    <div class="card">
      <h2>💬 Chats</h2>
      <div id="chats" class="list"></div>
      <div class="input-row">
        <input id="chat-id" type="text" placeholder="Chat ID" style="width:80px;flex:none;" />
        <input id="chat-text" type="text" placeholder="Send a message..." />
        <button onclick="sendMsg()">Send</button>
      </div>
    </div>
    
    <!-- Live Events Panel -->
    <div class="card">
      <h2><span class="live-indicator"></span>Live Events</h2>
      <div id="live-events" class="list" style="font-size:13px;">
        <div style="color:#999;">Waiting for messages...</div>
      </div>
    </div>
    
    <!-- Users Panel -->
    <div class="card">
      <h2>👥 Users</h2>
      <div id="users" class="list"></div>
    </div>
    
    <!-- Matches Panel -->
    <div class="card">
      <h2>❤️ Matches</h2>
      <div id="matches" class="list"></div>
    </div>
  </div>
  <script>
    const SENDER_NUM = '{self.cfg.series_sender_number}';
    
    // Fetch and render summary data
    async function fetchSummary() {{
      try {{
        const res = await fetch('/api/summary');
        const data = await res.json();
        renderUsers(data.users);
        renderMatches(data.matches);
        renderChats(data.chats);
      }} catch (e) {{ console.error('fetchSummary error:', e); }}
    }}
    
    function renderUsers(users) {{
      const el = document.getElementById('users');
      if (!users.length) {{
        el.innerHTML = '<div style="color:#999;padding:8px;">No users yet</div>';
        return;
      }}
      el.innerHTML = users.map(u => `
        <div class="row">
          <strong>${{u.name || '—'}} (${{u.phone.slice(-4)}})</strong>
          <div class="badge">${{u.status || 'new'}}</div>
          <small>${{u.summary || 'No summary yet'}}</small>
        </div>`).join('');
    }}
    
    function renderMatches(matches) {{
      const el = document.getElementById('matches');
      if (!matches.length) {{
        el.innerHTML = '<div style="color:#999;padding:8px;">No matches yet</div>';
        return;
      }}
      el.innerHTML = matches.map(m => `
        <div class="row">
          <strong>#${{m.id}}: ${{m.user_a.slice(-4)}} ↔ ${{m.user_b.slice(-4)}}</strong>
          <div class="badge">${{m.status}} | ${{m.score || 0}}</div>
        </div>`).join('');
    }}
    
    function renderChats(chats) {{
      const el = document.getElementById('chats');
      if (!chats.length) {{
        el.innerHTML = '<div style="color:#999;padding:8px;">No chats yet. Click "DM Leon" to start!</div>';
        return;
      }}
      el.innerHTML = chats.map(c => {{
        const phones = c.handles.split(', ').map(p => p.slice(-4)).join(', ');
        return `
        <div class="row clickable chat-row" onclick="openConvo(${{c.id}}, '${{c.handles.replace(/'/g, "\\'")}}')">
          <div class="chat-info">
            <strong>${{c.name || 'Chat ' + c.id}}</strong>
            <div class="chat-preview">${{phones}}</div>
          </div>
          <span class="badge">${{c.group ? '👥 group' : '💬 dm'}}</span>
          ${{c.message_count ? `<span class="msg-count">${{c.message_count}}</span>` : ''}}
        </div>`;
      }}).join('');
    }}
    
    // Demo button actions
    async function pingLeon() {{
      const btn = document.getElementById('btn-ping');
      btn.disabled = true;
      btn.querySelector('.desc').textContent = 'Sending...';
      try {{
        await fetch('/api/ping-leon', {{method:'POST'}});
        btn.querySelector('.desc').textContent = 'Message sent!';
        setTimeout(() => btn.querySelector('.desc').textContent = "Send a friendly opener to Leon's phone", 2000);
      }} catch (e) {{
        btn.querySelector('.desc').textContent = 'Failed - try again';
      }}
      btn.disabled = false;
      fetchSummary();
    }}
    
    async function intro() {{
      const btn = document.getElementById('btn-intro');
      btn.disabled = true;
      btn.querySelector('.desc').textContent = 'Creating intro...';
      try {{
        await fetch('/api/intro', {{method:'POST'}});
        btn.querySelector('.desc').textContent = 'Group chat created!';
        setTimeout(() => btn.querySelector('.desc').textContent = 'Introduce Leon ↔ Dhairyasheel in a group chat', 2000);
      }} catch (e) {{
        btn.querySelector('.desc').textContent = 'Failed - try again';
      }}
      btn.disabled = false;
      fetchSummary();
    }}
    
    async function toggleFastlane() {{
      const status = await getFastlaneStatus();
      if (status.running) {{
        await fetch('/api/fastlane/stop', {{method:'POST'}});
      }} else {{
        await fetch('/api/fastlane/start', {{method:'POST'}});
      }}
      await refreshFastlaneStatus();
    }}
    
    async function getFastlaneStatus() {{
      const res = await fetch('/api/fastlane/status');
      return await res.json();
    }}
    
    async function refreshFastlaneStatus() {{
      try {{
        const status = await getFastlaneStatus();
        const btn = document.getElementById('fastlane-btn');
        const desc = document.getElementById('fastlane-desc');
        const badge = document.getElementById('stage-badge');
        const watchEl = document.getElementById('watching-chat');
        const activityEl = document.getElementById('activity-log');
        
        // Update button
        if (status.running) {{
          btn.querySelector('.title').textContent = '⏹ Stop Demo';
          desc.textContent = 'Demo is running - click to stop';
        }} else {{
          btn.querySelector('.title').textContent = '⚡ Auto Demo';
          desc.textContent = 'Run the full onboarding flow automatically';
        }}
        
        // Update stage badge
        const stage = status.stage || 'idle';
        badge.textContent = stage.replace('_', ' ');
        badge.className = 'stage-badge ' + stage;
        
        // Update watching chat
        if (status.chat_id) {{
          watchEl.textContent = `Watching chat #${{status.chat_id}}`;
        }} else {{
          watchEl.textContent = '';
        }}
        
        // Update activity log
        if (status.activity && status.activity.length) {{
          activityEl.innerHTML = status.activity.slice(-10).reverse().map(a => {{
            const time = new Date(a.ts * 1000).toLocaleTimeString();
            return `<div><span style="color:#999;">${{time}}</span> ${{a.msg}}</div>`;
          }}).join('');
        }} else {{
          activityEl.innerHTML = '<div style="color:#999;">No activity yet. Start the demo!</div>';
        }}
      }} catch (e) {{ console.error('refreshFastlaneStatus error:', e); }}
    }}
    
    // Send message
    async function sendMsg() {{
      const chatInput = document.getElementById('chat-id');
      const textInput = document.getElementById('chat-text');
      const chat = chatInput.value;
      const text = textInput.value;
      if (!chat || !text) return;
      await fetch('/api/send', {{
        method:'POST',
        headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{chat_id: Number(chat), text}})
      }});
      textInput.value = '';
      if (currentChatId == chat) await loadMessages();
    }}
    
    // Simulate Leon message (for testing when Kafka isn't working)
    async function simulateLeon() {{
      const input = document.getElementById('simulate-text');
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      await fetch('/api/simulate-leon', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{text}})
      }});
      refreshFastlaneStatus();
    }}
    
    // Live events polling
    let lastLiveTs = Date.now() / 1000;
    async function fetchLiveEvents() {{
      try {{
        const res = await fetch(`/api/live?since=${{lastLiveTs}}`);
        const data = await res.json();
        if (data.events && data.events.length) {{
          const el = document.getElementById('live-events');
          for (const evt of data.events) {{
            const div = document.createElement('div');
            div.className = 'row' + (evt.is_known ? ' known-user' : '');
            div.style.animation = 'slideIn 0.3s ease';
            if (!evt.is_known) div.style.opacity = '0.5';  // Dim unknown users
            const time = new Date(evt.ts * 1000).toLocaleTimeString();
            const phone = evt.from_phone ? evt.from_phone.slice(-4) : '?';
            const knownBadge = evt.is_known ? '<span class="badge" style="background:#2ecc71;color:#fff;">ours</span>' : '';
            div.innerHTML = `<strong>${{evt.event_type || 'msg'}}</strong> ${{knownBadge}} <span class="badge">${{time}}</span><br/><small>...${{phone}} → chat #${{evt.chat_id || '?'}}: ${{(evt.text || '').slice(0, 40)}}</small>`;
            el.prepend(div);
            // Keep only last 20
            while (el.children.length > 20) el.lastChild.remove();
            if (evt.ts > lastLiveTs) lastLiveTs = evt.ts;
          }}
        }}
      }} catch (e) {{}}
    }}
    
    // Error toasts
    let lastErrorTs = Date.now() / 1000;
    async function fetchErrors() {{
      try {{
        const res = await fetch(`/api/errors?since=${{lastErrorTs}}`);
        const data = await res.json();
        for (const err of data.errors) {{
          showToast(err.source, err.message);
          if (err.ts > lastErrorTs) lastErrorTs = err.ts;
        }}
      }} catch (e) {{}}
    }}
    
    function showToast(source, message) {{
      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.innerHTML = `<strong>⚠️ ${{source}}</strong>${{message.slice(0, 200)}}`;
      toast.onclick = () => toast.remove();
      container.appendChild(toast);
      setTimeout(() => toast.remove(), 8000);
    }}
    
    // Conversation modal
    let currentChatId = null;
    let convoInterval = null;
    
    async function openConvo(chatId, title) {{
      currentChatId = chatId;
      document.getElementById('convo-title').textContent = `Chat #${{chatId}}`;
      document.getElementById('convo-modal').classList.add('open');
      document.getElementById('chat-id').value = chatId;
      await loadMessages();
      convoInterval = setInterval(loadMessages, 1500);  // Faster polling when open
    }}
    
    function closeConvo() {{
      document.getElementById('convo-modal').classList.remove('open');
      currentChatId = null;
      if (convoInterval) clearInterval(convoInterval);
    }}
    
    async function loadMessages() {{
      if (!currentChatId) return;
      try {{
        const res = await fetch(`/api/messages?chat_id=${{currentChatId}}`);
        const data = await res.json();
        const el = document.getElementById('convo-messages');
        const wasAtBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 50;
        
        el.innerHTML = (data.messages || []).map(m => {{
          const isSent = m.sent_from === SENDER_NUM || m.is_from_me;
          const time = m.sent_at ? new Date(m.sent_at).toLocaleTimeString() : '';
          const phone = m.sent_from ? m.sent_from.slice(-4) : '';
          return `<div class="msg ${{isSent ? 'sent' : 'received'}}"><div>${{m.text || ''}}</div><small>${{phone}} · ${{time}}</small></div>`;
        }}).join('');
        
        if (wasAtBottom) el.scrollTop = el.scrollHeight;
      }} catch (e) {{ console.error(e); }}
    }}
    
    async function sendConvoMsg() {{
      const input = document.getElementById('convo-input');
      const text = input.value.trim();
      if (!text || !currentChatId) return;
      input.value = '';
      await fetch('/api/send', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{chat_id: currentChatId, text}})
      }});
      await loadMessages();
    }}
    
    // Initialize
    fetchSummary();
    refreshFastlaneStatus();
    setInterval(fetchSummary, 5000);
    setInterval(refreshFastlaneStatus, 2000);
    setInterval(fetchLiveEvents, 1000);
    setInterval(fetchErrors, 3000);
  </script>
</body>
</html>
        """


def _run_kafka_consumer(cfg: Config, log: logging.Logger, db: Database) -> None:
    """Run Kafka consumer in background thread to populate live events."""
    if not KAFKA_AVAILABLE:
        log.info("Kafka not available, skipping live events consumer")
        return
    try:
        consumer = build_consumer(cfg)
        log.info("Kafka consumer started for topic: %s", cfg.kafka_topic)
        for msg in consumer:
            try:
                evt = KafkaEvent.from_dict(msg.value)
                from_phone = evt.data.from_phone
                
                # Soft filter: check if sender is in our DB (other teams may share the iMessage number)
                is_known = False
                if from_phone:
                    user = db.users.get_by_phone(from_phone)
                    is_known = user is not None
                
                # Also check chat_handles for known phones
                if not is_known and evt.data.chat_handles:
                    for handle in evt.data.chat_handles:
                        if handle.phone_number and not handle.is_me:
                            user = db.users.get_by_phone(handle.phone_number)
                            if user:
                                is_known = True
                                if not from_phone:
                                    from_phone = handle.phone_number
                                break
                
                log.info("Kafka event: type=%s from=%s chat=%s known=%s text=%s",
                         evt.event_type, from_phone, evt.data.chat_id, is_known,
                         (evt.data.text or "")[:50])
                
                add_live_event({
                    "event_type": evt.event_type,
                    "text": evt.data.text,
                    "from_phone": from_phone,
                    "chat_id": evt.data.chat_id,
                    "message_id": evt.data.message_id,
                    "is_known": is_known,  # Flag for dashboard to highlight
                })
            except Exception as e:
                log.warning("Failed to parse Kafka event: %s", e)
    except Exception as e:
        log.warning("Kafka consumer error: %s", e)
        add_error("kafka", f"Consumer error: {e}")


def run_server(port: int = 8080) -> None:
    cfg = Config.from_env()
    log = setup_logger(cfg.log_level)
    db = Database(cfg.db_path)
    api = SeriesAPI(
        cfg.series_base_url,
        cfg.series_api_key,
        timeout=cfg.request_timeout,
        max_retries=cfg.max_retries,
        sender_number=cfg.series_sender_number,
    )
    ensure_tester_profiles(db)

    OrbitWeb.cfg = cfg
    OrbitWeb.db = db
    OrbitWeb.api = api
    OrbitWeb.log = log

    # Start Kafka consumer thread for live events
    kafka_thread = threading.Thread(target=_run_kafka_consumer, args=(cfg, log, db), daemon=True)
    kafka_thread.start()

    server = HTTPServer(("localhost", port), OrbitWeb)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("Orbit dashboard on http://localhost:%d", port)
    thread.join()


if __name__ == "__main__":
    run_server()
