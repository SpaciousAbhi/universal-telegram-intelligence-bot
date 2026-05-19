from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)


def trim_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(limit - 32, 0)].rstrip() + "\n\n... trimmed for Telegram limit"


def user_mention(user_id: int, full_name: str | None = None) -> str:
    label = escape(full_name or str(user_id))
    return f'<a href="tg://user?id={user_id}">{label}</a>'

