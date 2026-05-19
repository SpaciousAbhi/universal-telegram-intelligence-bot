from __future__ import annotations

from typing import Iterable

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
    if CopyTextButton is not None:
        return InlineKeyboardButton(text=text, copy_text=CopyTextButton(text=value))
    return cb_button(text, fallback)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=_rows([cb_button(text, data) for text, data in MAIN_MENU]))


def report_actions_keyboard(report: ReportContext, premium: bool = False) -> InlineKeyboardMarkup:
    report_id = report.report_id or "last"
    rows = [
        [cb_button("📋 Copy Menu", f"r:copy:{report_id}"), cb_button("💾 Save Report", f"r:save:{report_id}")],
        [cb_button("📤 Export", f"r:export:{report_id}"), cb_button("🧾 Raw Data", f"r:raw:{report_id}")],
        [cb_button("🔄 Analyze Another", "u:analyze"), cb_button("❓ Help", "u:help")],
    ]
    if not premium:
        rows.append([cb_button("⭐ Upgrade Premium", "u:premium")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def copy_menu_keyboard(report: ReportContext) -> InlineKeyboardMarkup:
    values: list[tuple[str, str, str]] = []
    for section in report.sections:
        for field in section.fields:
            if field.copy_key and field.value not in (None, ""):
                values.append((field.copy_key, field.label, str(field.value)))
    rows = []
    for copy_key, label, value in values[:7]:
        rows.append([copy_button(f"Copy {label}", value, f"copy:{copy_key}")])
    rows.append([cb_button("Copy Full Report", "copy:full"), cb_button("Copy Raw JSON", "copy:raw")])
    rows.append([cb_button("⬅️ Back", "u:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def copy_menu_keyboard_from_document(report_doc: dict | None) -> InlineKeyboardMarkup:
    values: list[tuple[str, str, str]] = []
    for section in (report_doc or {}).get("sections", []):
        for field in section.get("fields", []):
            if field.get("copy_key") and field.get("value") not in (None, ""):
                values.append((field["copy_key"], field.get("label", field["copy_key"]), str(field["value"])))
    rows = [[copy_button(f"Copy {label}", value, f"copy:{copy_key}")] for copy_key, label, value in values[:7]]
    rows.append([cb_button("Copy Full Report", "copy:full"), cb_button("Copy Raw JSON", "copy:raw")])
    rows.append([cb_button("⬅️ Back", "u:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
