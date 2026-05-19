from __future__ import annotations

from typing import Any, Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    from aiogram.types import CopyTextButton
except ImportError:  # pragma: no cover - aiogram compatibility fallback
    CopyTextButton = None  # type: ignore[assignment]

from app.constants import ADMIN_SECTIONS, HELP_TOPICS, MAIN_MENU
from app.models import PremiumPlan, ReportContext


def _rows(buttons: Iterable[InlineKeyboardButton], width: int = 2) -> list[list[InlineKeyboardButton]]:
    row: list[InlineKeyboardButton] = []
    rows: list[list[InlineKeyboardButton]] = []
    for button in buttons:
        row.append(button)
        if len(row) == width:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def cb_button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data[:64])


def url_button(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url)


def copy_button(text: str, value: str, fallback: str) -> InlineKeyboardButton:
    if CopyTextButton is not None and 1 <= len(value) <= 256:
        return InlineKeyboardButton(text=text, copy_text=CopyTextButton(text=value))
    return cb_button(text, fallback)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=_rows([cb_button(text, data) for text, data in MAIN_MENU]))


def report_actions_keyboard(report: ReportContext, premium: bool = False) -> InlineKeyboardMarkup:
    report_id = report.report_id or "last"
    rows = _report_copy_rows(report, report_id)
    rows.extend(
        [
            [cb_button("💾 Save Report", f"r:save:{report_id}"), cb_button("📤 Export", f"r:export:{report_id}")],
            [cb_button("🧾 Raw Data", f"r:raw:{report_id}"), cb_button("🔄 Analyze Another", "u:analyze")],
            [cb_button("❓ Help", "u:help"), cb_button("📋 More Copy", f"r:copy:{report_id}")],
        ]
    )
    if not premium:
        rows.append([cb_button("⭐ Premium", "u:premium")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _report_copy_rows(report: ReportContext, report_id: str) -> list[list[InlineKeyboardButton]]:
    sections = [{"fields": [_field_to_dict(field) for field in section.fields]} for section in report.sections]
    values = _copy_values_from_sections(sections)
    priority = ["user_id", "chat_id", "message_id", "username", "file_id", "link"]
    buttons: list[InlineKeyboardButton] = []
    used: set[str] = set()
    for key in priority:
        item = next((value for value in values if value[0] == key and value[2] not in used), None)
        if not item:
            continue
        copy_key, label, value = item
        used.add(value)
        if len(value) <= 256:
            buttons.append(copy_button(f"📋 {label}", value, f"copy:{copy_key}:{report_id}"))
        else:
            buttons.append(cb_button(f"📋 {label}", f"r:copy:{report_id}"))
    return _rows(buttons[:6], width=2)


def _field_to_dict(field: Any) -> dict[str, Any]:
    return {
        "label": getattr(field, "label", ""),
        "value": getattr(field, "value", None),
        "copy_key": getattr(field, "copy_key", None),
    }


def copy_menu_keyboard(report: ReportContext) -> InlineKeyboardMarkup:
    sections = [{"fields": [_field_to_dict(field) for field in section.fields]} for section in report.sections]
    return _copy_menu_from_values(_copy_values_from_sections(sections))


def copy_menu_keyboard_from_document(report_doc: dict | None) -> InlineKeyboardMarkup:
    return _copy_menu_from_values(_copy_values_from_sections((report_doc or {}).get("sections", [])))


def _copy_menu_from_values(values: list[tuple[str, str, str]]) -> InlineKeyboardMarkup:
    rows = [[copy_button(f"Copy {label}", value, f"copy:{copy_key}")] for copy_key, label, value in values[:7]]
    rows.append([cb_button("Copy Full Report", "copy:full"), cb_button("Copy Raw JSON", "copy:raw")])
    rows.append([cb_button("⬅️ Back", "u:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _copy_values_from_sections(sections: list[dict]) -> list[tuple[str, str, str]]:
    label_by_key = {
        "user_id": "User ID",
        "chat_id": "Chat ID",
        "message_id": "Msg ID",
        "username": "Username",
        "file_id": "File ID",
        "link": "Link",
        "mention": "Mention",
        "reply_message_id": "Reply ID",
    }
    values: list[tuple[str, str, str]] = []
    for section in sections:
        for field in section.get("fields", []):
            if not isinstance(field, dict):
                continue
            copy_key = field.get("copy_key")
            value = field.get("value")
            if copy_key and value not in (None, ""):
                values.append((copy_key, label_by_key.get(copy_key, field.get("label", copy_key)), str(value)))
    return values


def premium_keyboard(plans: list[PremiumPlan]) -> InlineKeyboardMarkup:
    rows = [[cb_button(f"⭐ Buy {plan.title} - {plan.stars} Stars", f"pay:{plan.code}")] for plan in plans]
    rows.extend(
        [
            [cb_button("📅 My Premium Status", "p:status"), cb_button("🎁 My Referral Link", "u:referral")],
            [cb_button("⬅️ Main Menu", "u:menu")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def referral_keyboard(referral_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [url_button("📤 Share Referral Link", f"https://t.me/share/url?url={referral_link}")],
            [cb_button("👥 Invited Users", "ref:invited"), cb_button("🏆 Premium Days Earned", "ref:earned")],
            [cb_button("⬅️ Main Menu", "u:menu")],
        ]
    )


def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=_rows([cb_button(title, data) for title, data in HELP_TOPICS]) + [[cb_button("⬅️ Main Menu", "u:menu")]]
    )


def support_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[url_button("📞 Contact Support", url)], [cb_button("⬅️ Main Menu", "u:menu")]])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=_rows([cb_button(text, data) for text, data in ADMIN_SECTIONS]))


def force_sub_keyboard(channels: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for channel in channels:
        invite = channel.get("invite_link") or channel.get("public_link") or channel.get("url")
        if invite:
            rows.append([url_button(f"Join {channel.get('title', channel.get('chat_id'))}", invite)])
    rows.append([cb_button("🔄 Recheck", "fs:recheck")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
