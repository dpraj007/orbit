"""Deterministic agent core to avoid loops and drive demo flows."""
import json
import logging
import time
from typing import Any, Dict, Optional

from .agentic import mentor_response, run_agent
from .. import storage


class AgentCore:
    """Single entrypoint for handling messages. Prioritizes stability over flair."""

    def __init__(self, db: Any, api: Any, fallback_phone: str = "+15555550123") -> None:
        self.db = db
        self.api = api
        self.fallback_phone = fallback_phone
        self.log = logging.getLogger("orbit.agent.core")

    def handle_event(self, event: Dict[str, Any]) -> None:
        """Main handler. Expects event['data'] with chat_id, from_phone, text, is_group, chat_handles."""
        data = event.get("data", {})
        phone = data.get("from_phone")
        chat_id = data.get("chat_id")
        text = (data.get("text") or "").strip()
        is_group = bool(data.get("is_group"))
        chat_handles = data.get("chat_handles") or []

        if not phone or chat_id is None or not text:
            self.log.debug("Skipping event missing essentials: %s", event)
            return

        text_lower = text.lower()
        if is_group and "@orbit" not in text_lower:
            # Silent listen in groups unless invoked
            # Still log the message to local storage
            storage.log_message(chat_id, phone, text, data.get("sent_at"), data.get("attachments"), is_group=True)
            return

        user = self.db.users.get_by_phone(phone)
        if not user:
            user_id = self.db.users.create(phone, chat_id, name=None)
            self.db.profiles.create(user_id)
            user = self.db.users.get_by_id(user_id)
        else:
            # track latest chat_id
            if chat_id and not user["chat_id"]:
                self.db.users.update_chat_id(user["id"], chat_id)

        # Work with a plain dict to avoid sqlite3.Row surprises
        user = dict(user)

        # Log inbound message to local storage
        storage.log_message(chat_id, phone, text, data.get("sent_at"), data.get("attachments"), is_group=is_group)

        user_id = user["id"]
        conv = self.db.conversation_state.get_by_user_id(user_id)
        conv_dict = dict(conv) if conv else {}
        context_raw = conv_dict["context"] if conv_dict.get("context") else None
        try:
            ctx_obj = json.loads(context_raw) if context_raw else {}
        except Exception:
            ctx_obj = {}
        last_resp = ctx_obj.get("last_response")
        last_ts = ctx_obj.get("last_response_ts", 0)
        group_chat_id = ctx_obj.get("group_chat_id")

        # Dedupe guard: do not repeat within 5s
        def should_skip(resp: str) -> bool:
            return resp and resp == last_resp and (time.time() - last_ts) < 5

        connected = bool(conv_dict) and conv_dict.get("current_node") == "connected"

        if is_group:
            # brief mention response in group
            resp = "DM me if you want private tips."
            if should_skip(resp):
                return
            self._send(chat_id, resp)
            self._update_ctx(user_id, ctx_obj, resp)
            return

        # DM flow: use agentic LLM helper for natural replies + auto-intro
        profile = self.db.profiles.get_by_user_id(user_id)
        agent_ctx = {
            "user": user,
            "profile": dict(profile) if profile else {},
            "conversation_state": conv_dict,
            "active_match": None,
        }

        # Quick answer: who am I matched to?
        if connected and "match" in text_lower and "who" in text_lower:
            partner = self._get_last_match_partner(user_id)
            if partner:
                resp = f"You're matched with {partner.get('name') or partner.get('phone_number')}. Want me to loop them in or draft a reply?"
                if not should_skip(resp):
                    self._send(chat_id, resp)
                    self._update_ctx(user_id, ctx_obj, resp)
                return

        result = run_agent(text, agent_ctx, self.db, self.api, self.fallback_phone)
        resp = result.get("response")
        if resp and "just say yes" in resp.lower():
            # sanitize legacy pitch
            resp = "On it. Want me to set up or tweak your match? I can also give feedback."
        if resp and should_skip(resp):
            return

        # Apply any db updates (e.g., create group chat)
        updates = result.get("db_updates") or []
        self._apply_updates(updates, user, ctx_obj)

        # Ensure connected flag if requested
        for uid in result.get("set_connected_ids") or []:
            state_row = self.db.conversation_state.get_by_user_id(uid)
            raw = state_row["context"] if state_row and state_row["context"] else None
            try:
                sc = json.loads(raw) if raw else {}
            except Exception:
                sc = {}
            self.db.conversation_state.upsert(uid, current_node="connected", match_in_progress=None, context=sc)

        if resp:
            self._send(chat_id, resp)
            self._update_ctx(user_id, ctx_obj, resp)

    def _auto_intro(self, user: Dict[str, Any], ctx_obj: Dict[str, Any]) -> None:
        """Auto-introduce fallback match and create group chat."""
        user_id = user["id"]
        chat_id = user.get("chat_id")
        # Ensure fallback user exists
        fallback = self.db.users.get_by_phone(self.fallback_phone)
        if not fallback:
            fb_id = self.db.users.create(self.fallback_phone, None, name="Donald")
            self.db.profiles.create(fb_id)
            self.db.profiles.update_summary(
                fb_id,
                "Easygoing, loves kayaking and cartoons. Down-to-earth and keeps things light. Great with dad jokes.",
                1.0,
            )
            self.db.profiles.update_field(fb_id, "looking_for_summary", "Fun, kind people who like to laugh.")
            fallback = self.db.users.get_by_phone(self.fallback_phone)
        fallback = dict(fallback)
        match_user_id = fallback["id"]

        # Create match and mark mutual
        match_id = self.db.matches.create(user_id, match_user_id, 75.0)
        self.db.matches.force_mutual(match_id)
        self.db.conversation_state.upsert(user_id, current_node="connected", match_in_progress=None)
        self.db.conversation_state.upsert(match_user_id, current_node="connected", match_in_progress=None)

        # Create group chat
        try:
            ua_phone = user["phone_number"]
            ub_phone = fallback["phone_number"]
            intro = "Hi! You both matched. Enjoy connecting. @Orbit for tips."
            result = self.api.create_group_chat([ua_phone, ub_phone], intro, display_name="Match")
            group_chat_id = result.get("chat", {}).get("id") or result.get("id")
        except Exception as exc:
            self.log.error("Failed to create group chat: %s", exc)
            group_chat_id = None

        if group_chat_id:
            # store group chat id in both contexts
            for uid in (user_id, match_user_id):
                state_row = self.db.conversation_state.get_by_user_id(uid)
                raw = state_row["context"] if state_row and state_row["context"] else None
                try:
                    ctx = json.loads(raw) if raw else {}
                except Exception:
                    ctx = {}
                ctx["group_chat_id"] = group_chat_id
                self.db.conversation_state.upsert(uid, current_node="connected", match_in_progress=None, context=ctx)
            # Send a wingman note in the group
            try:
                self.api.send_message(
                    group_chat_id,
                    "I’ll stay quiet here unless you @Orbit. DM me for private pointers anytime.",
                )
            except Exception:
                pass

        # DM confirmation
        if chat_id:
            resp = "Great news! I’m introducing you now. I’ll stay quiet unless you need me."
            self._send(chat_id, resp)
            self._update_ctx(user_id, ctx_obj, resp)

    def _apply_updates(self, updates: Any, user: Dict[str, Any], ctx_obj: Dict[str, Any]) -> None:
        """Apply db_updates produced by run_agent (currently create_group)."""
        if not updates:
            return
        for upd in updates:
            if not isinstance(upd, dict):
                continue
            if upd.get("type") == "create_group":
                ua_id = upd.get("user_a_id")
                ub_id = upd.get("user_b_id")
                ua = self.db.users.get_by_id(ua_id) if ua_id else None
                ub = self.db.users.get_by_id(ub_id) if ub_id else None
                if not ua or not ub:
                    continue
                ua = dict(ua)
                ub = dict(ub)
                try:
                    result = self.api.create_group_chat(
                        [ua["phone_number"], ub["phone_number"]],
                        f"Hi {ua.get('name','there')} and {ub.get('name','friend')}! You’re matched. I’ll stay quiet unless you @Orbit.",
                        display_name="Match",
                    )
                    group_chat_id = result.get("chat", {}).get("id") or result.get("id")
                except Exception as exc:
                    self.log.error("Failed to create group chat: %s", exc)
                    group_chat_id = None

                if group_chat_id:
                    for uid in (ua_id, ub_id):
                        state_row = self.db.conversation_state.get_by_user_id(uid)
                        raw = state_row["context"] if state_row and state_row["context"] else None
                        try:
                            ctx = json.loads(raw) if raw else {}
                        except Exception:
                            ctx = {}
                        ctx["group_chat_id"] = group_chat_id
                        self.db.conversation_state.upsert(uid, current_node="connected", match_in_progress=None, context=ctx)
                    try:
                        self.api.send_message(
                            group_chat_id,
                            "DM me anytime for feedback. I’ll only jump in here if you @Orbit.",
                        )
                    except Exception:
                        pass

    def _get_last_match_partner(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Return the most recent mutual match partner for a user."""
        try:
            cur = self.db.matches.conn.execute(
                """
                SELECT * FROM matches
                WHERE (user_a_id = ? OR user_b_id = ?) AND status='mutual'
                ORDER BY id DESC LIMIT 1
                """,
                (user_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            partner_id = row["user_b_id"] if row["user_a_id"] == user_id else row["user_a_id"]
            partner = self.db.users.get_by_id(partner_id)
            return dict(partner) if partner else None
        except Exception:
            return None

    def _send(self, chat_id: int, text: str) -> None:
        # Sanitize any legacy canned line
        lowered = text.lower()
        if "want me to find you a match" in lowered and "just say yes" in lowered:
            text = "Ready when you are—say if you want a new intro or feedback on your opener."
        try:
            self.log.info("Send -> chat %s: %s", chat_id, text[:120])
            self.api.send_with_typing(chat_id, text)
        except Exception as exc:
            self.log.error("Send failed: %s", exc)

    def _update_ctx(self, user_id: int, ctx_obj: Dict[str, Any], resp: str) -> None:
        ctx_obj = ctx_obj or {}
        ctx_obj.update({"last_response": resp, "last_response_ts": time.time()})
        try:
            self.db.conversation_state.upsert(user_id, context=ctx_obj)
        except Exception:
            pass
