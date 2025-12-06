import html
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Iterable, List, Sequence
from urllib.parse import parse_qs, urlparse

from .client import SeriesClient
from .config import Config
from .store import UserStore


def render_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    head_html = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"


def render_page(title: str, body: str) -> str:
    return f"""
    <html>
    <head>
        <title>{html.escape(title)}</title>
        <style>
            body {{ font-family: sans-serif; margin: 24px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            a {{ color: #0366d6; text-decoration: none; }}
            .nav a {{ margin-right: 12px; }}
            .pill {{ padding: 2px 8px; border-radius: 12px; background: #eef; }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="/">Home</a>
            <a href="/users">Users</a>
            <a href="/matches">Matches</a>
            <a href="/chats">Chats</a>
        </div>
        {body}
    </body>
    </html>
    """


def _status_counts(store: UserStore) -> List[str]:
    cur = store.conn.execute("SELECT status, COUNT(1) as c FROM users GROUP BY status ORDER BY status")
    return [f"{row['status'] or 'UNKNOWN'}: {row['c']}" for row in cur.fetchall()]


class DashboardHandler(BaseHTTPRequestHandler):
    store: UserStore
    client: SeriesClient
    cfg: Config
    log = logging.getLogger("orbit.monitor")

    def _write(self, content: str, status: int = 200) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):  # type: ignore[override]
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/":
            self._write(
                render_page(
                    "Orbit Monitor",
                    f"<h1>Orbit Monitor</h1>"
                    f"<p>Status counts: {' | '.join(_status_counts(self.store))}</p>"
                    f"<ul>"
                    f"<li><a href='/users'>Users</a></li>"
                    f"<li><a href='/matches'>Matches</a></li>"
                    f"<li><a href='/chats'>Chats (live via Series API)</a></li>"
                    f"</ul>",
                )
            )
            return

        if path == "/users":
            limit = int(qs.get("limit", ["200"])[0])
            cur = self.store.conn.execute(
                """
                SELECT phone_number, name, status, profile_interests, profile_vibe, last_seen_at, last_dm_chat_id
                FROM users ORDER BY last_seen_at DESC LIMIT ?
                """,
                (limit,),
            )
            rows = [
                (
                    u["phone_number"],
                    u["name"] or "",
                    u["status"] or "",
                    u["profile_interests"] or "",
                    u["profile_vibe"] or "",
                    u["last_seen_at"] or "",
                    u["last_dm_chat_id"] or "",
                )
                for u in cur.fetchall()
            ]
            body = "<h2>Users</h2>" + render_table(
                ["Phone", "Name", "Status", "Interests", "Vibe", "Last seen", "Last DM chat"], rows
            )
            self._write(render_page("Users", body))
            return

        if path == "/matches":
            cur = self.store.conn.execute(
                """
                SELECT id, user_a, user_b, shared_interests, state, user_a_decision, user_b_decision, proposed_at
                FROM matches ORDER BY id DESC LIMIT 200
                """
            )
            rows = [
                (
                    m["id"],
                    m["user_a"],
                    m["user_b"],
                    m["shared_interests"] or "",
                    m["state"] or "",
                    f"{m['user_a_decision']}/{m['user_b_decision']}",
                    m["proposed_at"] or "",
                )
                for m in cur.fetchall()
            ]
            body = "<h2>Matches</h2>" + render_table(
                ["ID", "User A", "User B", "Shared", "State", "Decisions", "Proposed"], rows
            )
            self._write(render_page("Matches", body))
            return

        if path == "/chats":
            if not self.cfg.series_base_url:
                self._write(render_page("Chats", "<p>No SERIES_BASE_URL configured.</p>"))
                return
            try:
                chats = list(self.client.list_chats(per_page=50))
            except Exception as exc:
                self._write(render_page("Chats", f"<p>Error fetching chats: {html.escape(str(exc))}</p>"))
                return
            rows = []
            for c in chats:
                handles = ", ".join(h.get("phone_number", "") for h in c.get("chat_handles", []) if isinstance(h, dict))
                rows.append(
                    (
                        f"<a href='/chat?id={c.get('id')}'>{c.get('id')}</a>",
                        c.get("display_name", ""),
                        "yes" if c.get("group") else "no",
                        handles,
                        c.get("message_count", ""),
                    )
                )
            body = "<h2>Chats</h2>" + render_table(["ID", "Name", "Group", "Handles", "Messages"], rows)
            self._write(render_page("Chats", body))
            return

        if path == "/chat":
            qs_id = qs.get("id", [])
            if not qs_id:
                self._write(render_page("Chat", "<p>Missing chat id.</p>"), status=400)
                return
            chat_id = qs_id[0]
            try:
                messages = list(self.client.list_chat_messages(int(chat_id), per_page=50))
            except Exception as exc:
                self._write(render_page("Chat", f"<p>Error fetching chat {chat_id}: {html.escape(str(exc))}</p>"))
                return
            rows = []
            for m in messages:
                rows.append(
                    (
                        m.get("id", ""),
                        m.get("sent_at", ""),
                        m.get("sent_from", ""),
                        m.get("text", ""),
                        m.get("delivery_status", ""),
                        "yes" if m.get("is_read") else "no",
                    )
                )
            body = f"<h2>Chat {chat_id}</h2>" + render_table(
                ["ID", "Sent at", "From", "Text", "Status", "Read"], rows
            )
            self._write(render_page(f"Chat {chat_id}", body))
            return

        self._write(render_page("Not found", "<p>404 Not Found</p>"), status=404)


def run_server(port: int = 8000) -> None:
    cfg = Config.from_env()
    store = UserStore(cfg.db_path)
    client = SeriesClient(
        cfg.series_base_url,
        cfg.series_api_key,
        timeout=cfg.request_timeout,
        max_retries=cfg.max_retries,
        sender_number=cfg.series_sender_number,
    )

    DashboardHandler.store = store
    DashboardHandler.client = client
    DashboardHandler.cfg = cfg

    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.getLogger("orbit.monitor").info("Monitor listening on http://localhost:%d", port)
    thread.join()


if __name__ == "__main__":
    run_server()
