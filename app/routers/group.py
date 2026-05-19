from __future__ import annotations

from time import monotonic

from aiogram import F, Router
from aiogram.types import Message

from app.services.errors import ErrorService
from app.services.report_engine import ReportEngine
from app.ui.keyboards import report_actions_keyboard
from app.ui.renderer import Renderer

router = Router(name="group")
_cooldowns: dict[tuple[int, int], float] = {}


async def _is_triggered(message: Message) -> bool:
    if message.reply_to_message and message.text:
        me = await message.bot.get_me()
        return f"@{me.username}".lower() in message.text.lower()
    if message.text:
        me = await message.bot.get_me()
        return f"@{me.username}".lower() in message.text.lower()
    return False


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_report(message: Message, settings, repo, report_engine: ReportEngine, renderer: Renderer, errors: ErrorService) -> None:
    if not await _is_triggered(message):
        return
    key = (message.chat.id, message.from_user.id if message.from_user else 0)
    now = monotonic()
    last = _cooldowns.get(key, 0)
    if now - last < settings.group_cooldown_seconds:
        await message.reply("<b>⏳ Cooldown active</b>\n\nPlease wait before requesting another group report.")
        return
    _cooldowns[key] = now
    try:
        target = message.reply_to_message or message
        report = report_engine.message_report(target)
        report.report_id = await repo.insert_report(report_engine.to_document(report), report.raw)
        await message.reply(
            renderer.report(report),
            reply_markup=report_actions_keyboard(report, premium=False),
        )
    except Exception as exc:
        code = await errors.capture(repo, exc, {"handler": "group_report", "chat_id": message.chat.id})
        await message.reply(renderer.friendly_error(code))

