from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import Availability, ReportContext, ReportField, ReportKind
from app.utils import escape, pretty_json, trim_text


SEP = "━━━━━━━━━━━━━━━━━━"

FIELD_MEANINGS = {
    "Telegram User ID": "User ID is your permanent Telegram numeric ID.",
    "User ID": "User ID is your permanent Telegram numeric ID.",
    "Username": "Username can be changed anytime.",
    "Mention link": "Mention link can identify a user even without username.",
    "Message ID": "Message ID is unique only inside this chat.",
    "Chat ID": "Chat ID identifies the current chat.",
    "Channel ID": "Channel ID identifies the original channel source.",
    "Source ID": "Source ID identifies the original Telegram source when Telegram exposes it.",
    "File ID": "File ID can be reused by this bot.",
    "Unique file ID": "Unique File ID helps detect the same file across bots.",
}

LABELS = {
    "Telegram User ID": "User ID",
    "First name": "First Name",
    "Last name": "Last Name",
    "Full name": "Name",
    "Account type": "Account Type",
    "Language code": "Language",
    "Premium status": "Premium",
    "Profile link": "Public Link",
    "Mention link": "Mention Link",
    "First seen by bot": "First Seen",
    "Last active in bot": "Last Active",
    "Report generated time": "Report Time",
    "Sender name": "Sender Name",
    "Message type": "Message Type",
    "Date/time": "Date",
    "Forwarded source type": "Source Type",
    "Original user/channel/group": "Source Name",
    "Source username": "Username",
    "Forwarded channel post ID": "Original Post ID",
    "Source trace result": "Trace Result",
    "File type": "File Type",
    "File size": "File Size",
    "MIME type": "MIME Type",
    "Album/media group ID": "Album",
    "Topic/thread ID": "Topic ID",
}


class Renderer:
    def report(self, report: ReportContext, advanced: bool = False) -> str:
        if report.kind == ReportKind.USER:
            return self._user_report(report)
        return self._message_report(report, advanced=advanced)

    def raw(self, report: ReportContext, premium: bool) -> str:
        if not premium:
            return self.premium_required("Raw Developer Data")
        return trim_text(f"<b>🧾 Raw Developer Data</b>\n\n<pre>{escape(pretty_json(report.raw))}</pre>", 4096)

    def raw_document(self, raw: dict[str, Any] | None, premium: bool) -> str:
        if not premium:
            return self.premium_required("Raw Developer Data")
        if not raw:
            return "<b>🧾 Raw Developer Data</b>\n\nStored raw data was not found for this report."
        return trim_text(f"<b>🧾 Raw Developer Data</b>\n\n<pre>{escape(pretty_json(raw))}</pre>", 4096)

    def copy_menu(self, report: Any) -> str:
        return (
            "<b>📋 More Copy Options</b>\n\n"
            "Use these extra buttons for values that did not fit under the main report."
        )

    def premium_required(self, feature: str) -> str:
        return (
            f"<b>⭐ Premium Required</b>\n\n"
            f"{escape(feature)} is a premium power-user tool.\n\n"
            "<b>Premium unlocks:</b>\n"
            "Raw JSON, TXT/JSON/CSV exports, bulk export, saved reports, report search, comparison, developer copy formats, and file vault."
        )

    def premium_menu(self) -> str:
        return (
            "<b>⭐ Premium</b>\n\n"
            "Unlock developer tools, exports, saved reports, comparison, and file vault.\n"
            "Payments use Telegram Stars and activate instantly after successful payment."
        )

    def saved_reports(self, rows: list[dict[str, Any]], premium: bool) -> str:
        if not premium:
            return self.premium_required("Saved Reports")
        if not rows:
            return "<b>💾 Saved Reports</b>\n\nNo saved reports yet. Save any report from the report action menu."
        lines = ["<b>💾 Saved Reports</b>", ""]
        for index, row in enumerate(rows, start=1):
            lines.append(f"{index}. <b>{escape(row.get('name'))}</b> - <code>{escape(row.get('report_id'))}</code>")
        return "\n".join(lines)

    def report_saved(self, report_id: str) -> str:
        return f"<b>💾 Report Saved</b>\n\nReport <code>{escape(report_id)}</code> is now available in Saved Reports."

    def referral_menu(self, referral_link: str, invited: int = 0, earned_days: int = 0) -> str:
        return (
            "<b>🎁 Referral</b>\n\n"
            f"<b>Your link:</b> {escape(referral_link)}\n"
            f"<b>Invited users:</b> {invited}\n"
            f"<b>Premium days earned:</b> {earned_days}\n\n"
            "Share your link. Rewards are added after a new user starts the bot and passes access checks."
        )

    def help_center(self) -> str:
        return (
            "<b>❓ Help Center</b>\n\n"
            "Send or forward any supported Telegram message in private chat for a full report.\n"
            "In groups, reply to a message and mention the bot, or mention the bot directly for a short group report.\n"
            "Hidden/private fields are marked honestly in the unavailable section."
        )

    def support(self) -> str:
        return "<b>📞 Support</b>\n\nUse the contact button below for support. No ticket system is created inside the bot."

    def admin_dashboard(self, stats: dict[str, Any]) -> str:
        rows = "\n".join(f"<b>{escape(key.replace('_', ' ').title())}:</b> <code>{escape(value)}</code>" for key, value in stats.items())
        return f"<b>📊 Owner Command Center</b>\n\n{rows}\n\nChoose a section below."

    def admin_section(self, section: str) -> str:
        return (
            f"<b>{escape(section)}</b>\n\n"
            "This control center is wired for owner-only access. Use the panel actions to inspect status, export data, "
            "manage premium, force-sub, bans, broadcasts, payments, logs, errors, and settings."
        )

    def force_sub_prompt(self, missing: list[dict[str, Any]]) -> str:
        titles = "\n".join(f"• {escape(ch.get('title') or ch.get('chat_id'))}" for ch in missing)
        return (
            "<b>🔐 Join Required</b>\n\n"
            "Join the required channels below to use the bot. Channels you already joined are not shown.\n\n"
            f"{titles}"
        )

    def friendly_error(self, code: str) -> str:
        return (
            "<b>⚠️ Report failed safely</b>\n\n"
            "This input could not be processed right now. The error was logged for the owner.\n"
            f"<b>Error code:</b> <code>{escape(code)}</code>"
        )

    def _user_report(self, report: ReportContext) -> str:
        fields = self._field_map(report)
        lines = [
            "<b>👤 User Identity Report</b>",
            "",
            "Here is your Telegram profile information.",
            "",
        ]
        lines.extend(
            self._section(
                "🆔 Basic Details",
                [
                    self._line("User ID", fields.get("Telegram User ID")),
                    self._line("Name", fields.get("Full name")),
                    self._line("Username", fields.get("Username")),
                    self._line("Account Type", fields.get("Account type")),
                    self._line("Language", fields.get("Language code")),
                    self._line("Premium", fields.get("Premium status")),
                ],
            )
        )
        lines.extend(
            self._section(
                "🔗 Profile Links",
                [
                    self._line("Public Link", fields.get("Profile link")),
                    self._line("Mention Link", fields.get("Mention link")),
                ],
            )
        )
        lines.extend(
            self._section(
                "📌 Bot Activity",
                [
                    self._line("First Seen", fields.get("First seen by bot")),
                    self._line("Last Active", fields.get("Last active in bot")),
                    self._line("Report Time", fields.get("Report generated time")),
                ],
            )
        )
        lines.extend(self.truth_section(report))
        lines.extend(self.unavailable_section(report, preferred=["Last name", "Verified/scam/fake/restricted flags"]))
        return trim_text("\n".join(line for line in lines if line is not None).strip(), 4096)

    def _message_report(self, report: ReportContext, advanced: bool = False) -> str:
        fields = self._field_map(report)
        title, summary = self._message_title(report, fields)
        lines = [f"<b>{title}</b>", "", summary, ""]
        lines.extend(
            self._section(
                "📨 Message Details",
                [
                    self._line("Message ID", fields.get("Message ID")),
                    self._line("Chat Type", self._chat_type(fields.get("Chat title/type"))),
                    self._line("Chat ID", fields.get("Chat ID")),
                    self._line("Sender ID", fields.get("Sender ID")),
                    self._line("Sender Name", fields.get("Sender name")),
                    self._line("Username", fields.get("Sender username")),
                    self._line("Message Type", fields.get("Message type")),
                    self._line("Date", fields.get("Date/time")),
                    self._line("Topic ID", fields.get("Topic/thread ID")),
                ],
            )
        )
        if self._has_any(fields, ["Forwarded source type", "Original user/channel/group", "Source ID", "Source username"]):
            source_id_label = "Channel ID" if self._value(fields.get("Forwarded source type")).lower() == "channel" else "Source ID"
            lines.extend(
                self._section(
                    "🔁 Forward Source",
                    [
                        self._line("Source Type", fields.get("Forwarded source type")),
                        self._line("Source Name", fields.get("Original user/channel/group")),
                        self._line(source_id_label, fields.get("Source ID")),
                        self._line("Username", fields.get("Source username")),
                        self._line("Original Post ID", fields.get("Forwarded channel post ID")),
                        self._line("Forward Date", fields.get("Forward date")),
                        self._line("Trace Result", fields.get("Source trace result")),
                    ],
                )
            )
        if self._has_any(fields, ["File type", "File ID", "Unique file ID"]):
            lines.extend(
                self._section(
                    "📦 Media Details",
                    [
                        self._line("File Type", fields.get("File type")),
                        self._line("File ID", fields.get("File ID")),
                        self._line("Unique File ID", fields.get("Unique file ID")),
                        self._line("File Size", fields.get("File size")),
                        self._resolution_line(fields.get("Width"), fields.get("Height")),
                        self._line("Album", fields.get("Album/media group ID"), no_value="No"),
                    ],
                )
            )
        caption = self._value(fields.get("Caption"))
        if caption:
            preview = self._caption_preview(caption)
            lines.extend(self._section("📝 Caption Preview", [f"<code>{escape(preview)}</code>", "Full caption is available in Export / Raw Data."]))
        entity_lines = self._entity_lines(report)
        if entity_lines:
            lines.extend(self._section("🔗 Text Entities", entity_lines))
        lines.extend(self.truth_section(report))
        lines.extend(self.unavailable_section(report))
        return trim_text("\n".join(line for line in lines if line is not None).strip(), 4096)

    def truth_section(self, report: ReportContext) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()
        for section in report.sections:
            for field in section.fields:
                if self._value(field) and field.label in FIELD_MEANINGS and field.label not in seen:
                    seen.add(field.label)
                    lines.append(f"• {escape(FIELD_MEANINGS[field.label])}")
        if not lines:
            lines.append("• This report shows only metadata Telegram made available to the bot.")
        return self._section("🧠 What This Means", lines[:5])

    def unavailable_section(self, report: ReportContext, preferred: list[str] | None = None) -> list[str]:
        unavailable: list[str] = []
        seen: set[str] = set()
        preferred = preferred or []
        fields = [field for section in report.sections for field in section.fields]
        fields.sort(key=lambda field: (0 if field.label in preferred else 1, field.label))
        for field in fields:
            if field.label in seen or self._value(field):
                continue
            seen.add(field.label)
            reason = self._clean_reason(field)
            unavailable.append(f"• {escape(LABELS.get(field.label, field.label))}: {escape(reason)}")
        if not unavailable:
            return []
        return self._section("⚠️ Unavailable Fields", unavailable[:8])

    def _section(self, title: str, rows: list[str | None]) -> list[str]:
        clean = [row for row in rows if row]
        if not clean:
            return []
        return [SEP, f"<b>{escape(title)}</b>", SEP, "", *clean, ""]

    def _line(self, label: str, field: ReportField | str | None, no_value: str | None = None) -> str | None:
        value = self._value(field)
        if not value:
            if no_value is None:
                return None
            value = no_value
        return f"• {escape(label)}: <code>{escape(self._format_value(label, value))}</code>"

    def _resolution_line(self, width: ReportField | None, height: ReportField | None) -> str | None:
        w = self._value(width)
        h = self._value(height)
        if not w or not h:
            return None
        return f"• Resolution: <code>{escape(w)} × {escape(h)}</code>"

    def _field_map(self, report: ReportContext) -> dict[str, ReportField]:
        return {field.label: field for section in report.sections for field in section.fields}

    def _value(self, field: ReportField | str | None) -> str:
        if isinstance(field, str):
            return field
        if field is None or field.value in (None, ""):
            return ""
        return str(field.value)

    def _has_any(self, fields: dict[str, ReportField], labels: list[str]) -> bool:
        return any(self._value(fields.get(label)) for label in labels)

    def _format_value(self, label: str, value: str) -> str:
        if label in {"Date", "Forward Date", "First Seen", "Last Active", "Report Time"}:
            return self._format_datetime(value)
        if label == "File Size":
            return self._format_size(value)
        if label in {"Account Type", "Message Type", "File Type", "Source Type", "Chat Type"}:
            return value.replace("_", " ").title()
        if label == "Premium":
            return "Yes" if value.lower() in {"true", "yes", "1"} else "No"
        if label == "Language":
            return self._format_language(value)
        return value

    def _format_datetime(self, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
        return parsed.strftime("%d %b %Y, %H:%M UTC").lstrip("0")

    def _format_size(self, value: str) -> str:
        try:
            size = float(value)
        except ValueError:
            return value
        if size < 1024:
            return f"{int(size)} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def _format_language(self, value: str) -> str:
        return {"en": "English", "en-us": "English", "en-gb": "English"}.get(value.lower(), value)

    def _caption_preview(self, caption: str) -> str:
        caption = caption.strip()
        if len(caption) <= 230:
            return caption
        return caption[:230].rstrip() + "..."

    def _entity_lines(self, report: ReportContext) -> list[str]:
        ignored = {"Entities"}
        lines: list[str] = []
        for section in report.sections:
            if "Entities" not in section.title:
                continue
            for field in section.fields:
                if field.label in ignored:
                    continue
                value = self._value(field)
                if value:
                    lines.append(f"• {escape(field.label)}: <code>{escape(value)}</code>")
        return lines

    def _chat_type(self, field: ReportField | None) -> str:
        value = self._value(field)
        if "(" in value and value.endswith(")"):
            return value.rsplit("(", 1)[1].rstrip(")")
        return value

    def _message_title(self, report: ReportContext, fields: dict[str, ReportField]) -> tuple[str, str]:
        message_type = self._format_value("Message Type", self._value(fields.get("Message type")) or "Message")
        if report.kind == ReportKind.FORWARD and self._has_any(fields, ["File type", "File ID"]):
            return "🔎 Forwarded Media Report", f"A forwarded {message_type.lower()} message was detected."
        if report.kind == ReportKind.FORWARD:
            return "🔎 Forwarded Message Report", "A forwarded message was detected."
        if report.kind == ReportKind.MEDIA:
            return "📦 Media Report", f"A {message_type.lower()} message was detected."
        if report.kind == ReportKind.GROUP:
            return "👥 Group / Forum Report", "A group message was detected."
        if report.kind == ReportKind.CHANNEL:
            return "📣 Channel Report", "A channel post was detected."
        return "🧾 Message Report", "Telegram message information was detected."

    def _clean_reason(self, field: ReportField) -> str:
        reason = field.reason or field.status.value
        replacements = {
            "Not provided by Telegram API": "Not available for this report.",
            "Not audio/video/voice or not provided": "Not applicable for this media type.",
            "Not visual media or not provided": "Not applicable for this media type.",
            "Not part of an album": "Not part of an album.",
            "No caption": "No caption.",
            "Not a forum topic message": "Not applicable in this chat.",
            "User has no username": "User has no username.",
            "Not seen before this report": "Not seen before this report.",
            "Not available yet": "Not available yet.",
            "Sender not provided by Telegram API": "Sender is not available.",
            "Source has no public username or Telegram did not provide it": "Source has no public username.",
        }
        return replacements.get(reason, reason)
