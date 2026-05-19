from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Availability(str, Enum):
    AVAILABLE = "✅ Available"
    HIDDEN = "⚠️ Hidden by Telegram"
    PRIVATE = "🔒 Private"
    NO_ACCESS = "🚫 Bot has no access"
    NOT_PROVIDED = "❌ Not provided by Telegram API"


class ReportLevel(str, Enum):
    SIMPLE = "simple"
    ADVANCED = "advanced"
    RAW = "raw"


class ReportKind(str, Enum):
    USER = "user"
    MESSAGE = "message"
    FORWARD = "forward"
    CHAT = "chat"
    GROUP = "group"
    CHANNEL = "channel"
    MEDIA = "media"
    CONTACT = "contact"
    LOCATION = "location"
    POLL = "poll"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class ReportField:
    label: str
    value: Any
    status: Availability = Availability.AVAILABLE
    reason: str | None = None
    copy_key: str | None = None
    premium_only: bool = False

    def display_value(self) -> str:
        if self.value not in (None, ""):
            return str(self.value)
        return self.reason or self.status.value


@dataclass(slots=True)
class ReportSection:
    title: str
    fields: list[ReportField] = field(default_factory=list)


@dataclass(slots=True)
class ReportContext:
    kind: ReportKind
    source: str
    sections: list[ReportSection]
    raw: dict[str, Any]
    unavailable: list[ReportField] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    report_id: str | None = None
    owner_user_id: int | None = None
    chat_id: int | None = None
    message_id: int | None = None


@dataclass(slots=True)
class PremiumPlan:
    code: str
    title: str
    days: int
    stars: int


@dataclass(slots=True)
class BroadcastStats:
    total: int = 0
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    invalid: int = 0

    @property
    def remaining(self) -> int:
        return max(self.total - self.sent - self.failed - self.blocked - self.invalid, 0)

