from __future__ import annotations

from typing import Any

from app.models import Availability, ReportContext, ReportKind
from app.utils import escape, pretty_json, trim_text


FIELD_MEANINGS = {
    "Telegram User ID": "Permanent numeric Telegram identifier.",
    "Username": "Public username. It can be changed by the user.",
    "Chat ID": "Unique identifier of this private chat, group, supergroup, or channel.",
    "Message ID": "Unique only inside this chat.",
    "Forwarded source type": "Source category Telegram chose to expose for this forward.",
    "File ID": "Reusable by this bot to access or send the same file.",
    "Unique file ID": "Stable across bots, but cannot be used to download the file.",
    "Topic/thread ID": "Forum topic identifier inside a supergroup.",
}


class Renderer:
    def report(self, report: ReportContext, advanced: bool = False) -> str:
        title = self._title(report.kind)
        lines = [f"<b>{title}</b>", ""]
        for section in report.sections:
            lines.append(f"<b>{escape(section.title)}</b>")
            for field in section.fields:
                if not advanced and field.premium_only:
                    continue
                status = "" if field.status == Availability.AVAILABLE else f" {field.status.value}"
                lines.append(f"<b>{escape(field.label)}:</b> {escape(field.display_value())}{status}")
            lines.append("")
        lines.extend(self.truth_section(report))
        lines.extend(self.limitation_section(report))
        lines.append("<i>Raw developer data is hidden by default. Use Raw Data from the action menu if premium is active.</i>")
        return trim_text("\n".join(lines).strip(), 4096)

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
            "<b>📋 Copy Menu</b>\n\n"
            "Use the buttons below to copy IDs, links, file IDs, the full report, or raw JSON where available."
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
            "Hidden/private fields are marked honestly with Telegram limitation labels."
        )

    def support(self) -> str:
        return "<b>📞 Support</b>\n\nUse the contact button below for support. No ticket system is created inside the bot."

    def admin_dashboard(self, stats: dict[str, Any]) -> str:
        rows = "\n".join(f"<b>{escape(key.replace('_', ' ').title())}:</b> {escape(value)}" for key, value in stats.items())
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
            f"<b>Error code:</b> {escape(code)}"
        )

    def truth_section(self, report: ReportContext) -> list[str]:
        meanings = []
        seen = set()
        for section in report.sections:
            for field in section.fields:
                if field.label in FIELD_MEANINGS and field.label not in seen:
                    seen.add(field.label)
                    meanings.append(f"• <b>{escape(field.label)}:</b> {escape(FIELD_MEANINGS[field.label])}")
        if not meanings:
            meanings.append("• This report shows only metadata Telegram made available to the bot.")
        return ["<b>🧠 What This Means</b>", *meanings, ""]

    def limitation_section(self, report: ReportContext) -> list[str]:
        if not report.unavailable:
            return ["<b>🛡 Privacy & Limitations</b>", "✅ All core fields in this report were available.", ""]
        lines = ["<b>🛡 Privacy & Limitations</b>"]
        for field in report.unavailable[:8]:
            lines.append(f"• <b>{escape(field.label)}:</b> {field.status.value} - {escape(field.reason or field.status.value)}")
        return [*lines, ""]

    def _title(self, kind: ReportKind) -> str:
        return {
            ReportKind.USER: "👤 User Identity Card",
            ReportKind.FORWARD: "🔎 Forward Source Report",
            ReportKind.MEDIA: "📦 File Intelligence Report",
            ReportKind.GROUP: "👥 Group / Forum Report",
            ReportKind.CHANNEL: "📣 Channel Report",
            ReportKind.CONTACT: "☎️ Contact Report",
            ReportKind.LOCATION: "📍 Location Report",
            ReportKind.POLL: "📊 Poll Report",
        }.get(kind, "🧾 Telegram Message Report")
