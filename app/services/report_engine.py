from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.models import Availability, ReportContext, ReportField, ReportKind, ReportSection


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _full_name(user: Any) -> str | None:
    if not user:
        return None
    first = _get(user, "first_name")
    last = _get(user, "last_name")
    return " ".join(part for part in [first, last] if part) or _get(user, "full_name")


def _raw(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return {"value": str(obj)}


def _unavailable(label: str, status: Availability, reason: str) -> ReportField:
    return ReportField(label=label, value=None, status=status, reason=reason)


class ReportEngine:
    def user_profile(self, user: Any, stored_user: dict[str, Any] | None = None) -> ReportContext:
        user_id = _get(user, "id")
        username = _get(user, "username")
        full_name = _full_name(user)
        generated = datetime.now(timezone.utc)
        fields = [
            ReportField("Telegram User ID", user_id, copy_key="user_id"),
            ReportField("First name", _get(user, "first_name"), Availability.NOT_PROVIDED, "Not set by user."),
            ReportField("Last name", _get(user, "last_name"), Availability.NOT_PROVIDED, "Not set by user."),
            ReportField("Username", f"@{username}" if username else None, Availability.NOT_PROVIDED, "User has no username", "username"),
            ReportField("Full name", full_name, Availability.NOT_PROVIDED, "Name is not available."),
            ReportField("Account type", "bot" if _get(user, "is_bot") else "user"),
            ReportField("Language code", _get(user, "language_code"), Availability.NOT_PROVIDED, "Not provided by Telegram API"),
            ReportField("Premium status", bool(_get(user, "is_premium"))),
            ReportField("Verified/scam/fake/restricted flags", None, Availability.NOT_PROVIDED, "Not available for normal Bot API user reports."),
            ReportField("Profile link", f"https://t.me/{username}" if username else None, Availability.NOT_PROVIDED, "User has no username", "link"),
            ReportField("Mention link", f"tg://user?id={user_id}" if user_id else None, copy_key="mention"),
            ReportField("First seen by bot", (stored_user or {}).get("first_seen_at"), Availability.NOT_PROVIDED, "Not seen before this report"),
            ReportField("Last active in bot", (stored_user or {}).get("last_active_at"), Availability.NOT_PROVIDED, "Not available yet"),
            ReportField("Report generated time", generated.isoformat()),
        ]
        return ReportContext(
            kind=ReportKind.USER,
            source="private_user",
            sections=[ReportSection("👤 User Identity Card", fields)],
            raw={"user": _raw(user), "stored_user": stored_user or {}},
            unavailable=[f for f in fields if f.status != Availability.AVAILABLE and not f.value],
            generated_at=generated,
            owner_user_id=user_id,
        )

    def message_report(self, message: Any) -> ReportContext:
        chat = _get(message, "chat")
        sender = _get(message, "from_user") or _get(message, "sender_chat")
        reply = _get(message, "reply_to_message")
        forward_origin = _get(message, "forward_origin") or self._legacy_forward_origin(message)
        media = self._media_fields(message)
        entities = self._entity_fields(message)
        kind = self._detect_kind(message, forward_origin, media)
        message_id = _get(message, "message_id")
        chat_id = _get(chat, "id")
        date = _get(message, "date")
        text = _get(message, "text") or _get(message, "caption")
        sections = [
            ReportSection(
                "🧾 Message Report",
                [
                    ReportField("Message ID", message_id, copy_key="message_id"),
                    ReportField("Sender ID", _get(sender, "id"), Availability.NOT_PROVIDED, "Sender not provided by Telegram API", "user_id"),
                    ReportField("Sender name", _full_name(sender) or _get(sender, "title"), Availability.NOT_PROVIDED, "Sender name unavailable"),
                    ReportField("Sender username", f"@{_get(sender, 'username')}" if _get(sender, "username") else None, Availability.NOT_PROVIDED, "Sender has no public username", "username"),
                    ReportField("Chat ID", chat_id, copy_key="chat_id"),
                    ReportField("Chat title/type", self._chat_label(chat)),
                    ReportField("Message type", self._message_type(message)),
                    ReportField("Text/caption length", len(text or "")),
                    ReportField("Date/time", date.isoformat() if hasattr(date, "isoformat") else date, Availability.NOT_PROVIDED, "Not provided by Telegram API"),
                    ReportField("Topic/thread ID", _get(message, "message_thread_id"), Availability.NOT_PROVIDED, "Not a forum topic message"),
                ],
            )
        ]
        if reply:
            sections.append(
                ReportSection(
                    "↩️ Reply Info",
                    [
                        ReportField("Replied message ID", _get(reply, "message_id"), copy_key="reply_message_id"),
                        ReportField("Replied user ID", _get(_get(reply, "from_user"), "id"), Availability.NOT_PROVIDED, "Replied sender unavailable"),
                    ],
                )
            )
        if forward_origin:
            sections.append(self._forward_section(forward_origin, message))
        if entities:
            sections.append(ReportSection("🔗 Entities", entities))
        if media:
            sections.append(ReportSection("📦 File / Media", media))
        unavailable = [field for section in sections for field in section.fields if field.status != Availability.AVAILABLE and not field.value]
        return ReportContext(
            kind=kind,
            source="telegram_message",
            sections=sections,
            raw={"message": _raw(message), "forward_origin": _raw(forward_origin)},
            unavailable=unavailable,
            owner_user_id=_get(sender, "id"),
            chat_id=chat_id,
            message_id=message_id,
        )

    def _legacy_forward_origin(self, message: Any) -> dict[str, Any] | None:
        if _get(message, "forward_from") or _get(message, "forward_from_chat") or _get(message, "forward_sender_name"):
            return {
                "type": "legacy",
                "sender_user": _raw(_get(message, "forward_from")),
                "sender_chat": _raw(_get(message, "forward_from_chat")),
                "sender_name": _get(message, "forward_sender_name"),
                "date": _get(message, "forward_date"),
            }
        return None

    def _forward_section(self, origin: Any, message: Any) -> ReportSection:
        origin_type = _get(origin, "type", "unknown")
        sender_user = _get(origin, "sender_user") or _get(origin, "sender_user_id")
        sender_chat = _get(origin, "chat") or _get(origin, "sender_chat")
        sender_name = _get(origin, "sender_user_name") or _get(origin, "sender_name")
        post_id = _get(origin, "message_id") or _get(message, "forward_from_message_id")
        date = _get(origin, "date") or _get(message, "forward_date")
        hidden = not (sender_user or sender_chat or sender_name)
        result = "Source visible"
        if hidden:
            result = "Original source is hidden by Telegram privacy settings."
        elif sender_chat and not _get(sender_chat, "username"):
            result = "Source partially visible. Telegram provided chat title/ID fields, but public access may be private."
        fields = [
            ReportField("Forwarded source type", origin_type),
            ReportField("Original user/channel/group", _full_name(sender_user) or _get(sender_chat, "title") or sender_name, Availability.HIDDEN, "Original source is hidden by Telegram privacy settings."),
            ReportField("Source ID", _get(sender_user, "id") or _get(sender_chat, "id"), Availability.HIDDEN, "Hidden by Telegram privacy", "chat_id"),
            ReportField("Source username", self._username(_get(sender_user, "username") or _get(sender_chat, "username")), Availability.NOT_PROVIDED, "Source has no public username or Telegram did not provide it", "username"),
            ReportField("Forward date", date.isoformat() if hasattr(date, "isoformat") else date, Availability.NOT_PROVIDED, "Not provided by Telegram API"),
            ReportField("Forwarded channel post ID", post_id, Availability.NOT_PROVIDED, "Not provided by Telegram API"),
            ReportField("Source trace result", result),
        ]
        return ReportSection("🔎 Source Trace Result", fields)

    def _entity_fields(self, message: Any) -> list[ReportField]:
        entities = list(_get(message, "entities", []) or []) + list(_get(message, "caption_entities", []) or [])
        fields: list[ReportField] = []
        by_type: dict[str, int] = {}
        for entity in entities:
            etype = _get(entity, "type", "unknown")
            by_type[etype] = by_type.get(etype, 0) + 1
        for etype, count in sorted(by_type.items()):
            fields.append(ReportField(etype.replace("_", " ").title(), count))
        if not fields:
            fields.append(_unavailable("Entities", Availability.NOT_PROVIDED, "No Telegram entities were provided for this message"))
        return fields

    def _media_fields(self, message: Any) -> list[ReportField]:
        candidates = [
            ("photo", _get(message, "photo")),
            ("video", _get(message, "video")),
            ("document", _get(message, "document")),
            ("sticker", _get(message, "sticker")),
            ("voice", _get(message, "voice")),
            ("audio", _get(message, "audio")),
            ("animation", _get(message, "animation")),
            ("video_note", _get(message, "video_note")),
        ]
        media_type = None
        media = None
        for name, value in candidates:
            if value:
                media_type = name
                media = value[-1] if name == "photo" and isinstance(value, list) else value
                break
        if _get(message, "contact"):
            return [
                ReportField("Contact user ID", _get(_get(message, "contact"), "user_id"), Availability.NOT_PROVIDED, "Telegram did not link this contact to a user"),
                ReportField("Phone number", _get(_get(message, "contact"), "phone_number")),
            ]
        if _get(message, "location"):
            return [
                ReportField("Latitude", _get(_get(message, "location"), "latitude")),
                ReportField("Longitude", _get(_get(message, "location"), "longitude")),
            ]
        if _get(message, "poll"):
            return [
                ReportField("Poll ID", _get(_get(message, "poll"), "id")),
                ReportField("Poll question", _get(_get(message, "poll"), "question")),
            ]
        if not media:
            return []
        return [
            ReportField("File type", media_type),
            ReportField("File ID", _get(media, "file_id"), copy_key="file_id"),
            ReportField("Unique file ID", _get(media, "file_unique_id"), Availability.NOT_PROVIDED, "Not provided by Telegram API"),
            ReportField("File size", _get(media, "file_size"), Availability.NOT_PROVIDED, "Not provided by Telegram API"),
            ReportField("MIME type", _get(media, "mime_type"), Availability.NOT_PROVIDED, "Not provided by Telegram API"),
            ReportField("Duration", _get(media, "duration"), Availability.NOT_PROVIDED, "Not audio/video/voice or not provided"),
            ReportField("Width", _get(media, "width"), Availability.NOT_PROVIDED, "Not visual media or not provided"),
            ReportField("Height", _get(media, "height"), Availability.NOT_PROVIDED, "Not visual media or not provided"),
            ReportField("Album/media group ID", _get(message, "media_group_id"), Availability.NOT_PROVIDED, "Not part of an album"),
            ReportField("Caption", _get(message, "caption"), Availability.NOT_PROVIDED, "No caption"),
        ]

    def _message_type(self, message: Any) -> str:
        for name in ["text", "photo", "video", "document", "sticker", "voice", "audio", "contact", "location", "poll", "animation", "video_note"]:
            if _get(message, name):
                return name
        return "unsupported"

    def _username(self, username: Any) -> str | None:
        if not username:
            return None
        username = str(username)
        return username if username.startswith("@") else f"@{username}"

    def _detect_kind(self, message: Any, forward_origin: Any, media: list[ReportField]) -> ReportKind:
        chat_type = _get(_get(message, "chat"), "type")
        if forward_origin:
            return ReportKind.FORWARD
        if media:
            labels = {field.label for field in media}
            if "Contact user ID" in labels:
                return ReportKind.CONTACT
            if "Latitude" in labels:
                return ReportKind.LOCATION
            if "Poll ID" in labels:
                return ReportKind.POLL
            return ReportKind.MEDIA
        if chat_type == "channel":
            return ReportKind.CHANNEL
        if chat_type in {"group", "supergroup"}:
            return ReportKind.GROUP
        return ReportKind.MESSAGE

    def _chat_label(self, chat: Any) -> str:
        title = _get(chat, "title") or _get(chat, "full_name") or _get(chat, "username") or _get(chat, "id")
        ctype = _get(chat, "type") or "unknown"
        return f"{title} ({ctype})"

    def to_document(self, report: ReportContext) -> dict[str, Any]:
        return self._serializable(asdict(report))

    def _serializable(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value
        if is_dataclass(value):
            return self._serializable(asdict(value))
        if isinstance(value, dict):
            return {key: self._serializable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._serializable(item) for item in value]
        return value
