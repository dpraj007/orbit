"""Local folder-based storage for people and group chats."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BASE_DIR = Path("data")


def _safe_phone(phone: str) -> str:
    return phone.replace("+", "plus").replace(" ", "").replace("-", "")


def ensure_person(phone: str, name: Optional[str] = None) -> Path:
    folder = BASE_DIR / "people" / _safe_phone(phone)
    folder.mkdir(parents=True, exist_ok=True)
    profile_file = folder / "profile.json"
    if profile_file.exists():
        try:
            profile = json.loads(profile_file.read_text())
        except Exception:
            profile = {}
    else:
        profile = {}
    profile.setdefault("phone", phone)
    if name:
        profile["name"] = name
    profile_file.write_text(json.dumps(profile, indent=2))
    return folder


def ensure_group(chat_id: int) -> Path:
    folder = BASE_DIR / "groups" / str(chat_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def log_message(
    chat_id: int,
    from_phone: str,
    text: str,
    sent_at: Optional[str],
    attachments: Optional[List[Dict[str, Any]]] = None,
    is_group: bool = False,
) -> None:
    """Store message and attachments to local folder."""
    folder = ensure_group(chat_id) if is_group else ensure_person(from_phone)
    inbox = folder / "inbox"
    inbox.mkdir(exist_ok=True)

    msg_id = f"{sent_at or ''}".replace(" ", "_").replace(":", "_").replace(".", "_")
    if not msg_id or msg_id == "_":
        msg_id = str(int(Path().stat().st_mtime_ns))

    msg_meta = {
        "chat_id": chat_id,
        "from": from_phone,
        "text": text,
        "sent_at": sent_at,
        "attachments": [],
    }

    # Save attachments as files
    if attachments:
        for idx, att in enumerate(attachments, start=1):
            data_b64 = att.get("data_base64")
            filename = att.get("filename") or f"attachment_{msg_id}_{idx}"
            if not data_b64:
                continue
            try:
                import base64

                raw = base64.b64decode(data_b64)
                target = inbox / filename
                target.write_bytes(raw)
                msg_meta["attachments"].append(str(target))
            except Exception:
                pass

    # Write message meta
    meta_file = inbox / f"msg_{msg_id}.json"
    meta_file.write_text(json.dumps(msg_meta, indent=2))


def save_profile(phone: str, profile: Dict[str, Any]) -> None:
    folder = ensure_person(phone)
    profile_file = folder / "profile.json"
    profile_file.write_text(json.dumps(profile, indent=2))


def save_group_meta(chat_id: int, meta: Dict[str, Any]) -> None:
    folder = ensure_group(chat_id)
    meta_file = folder / "group.json"
    meta_file.write_text(json.dumps(meta, indent=2))
