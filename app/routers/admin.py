from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.constants import ADMIN_SECTIONS
from app.ui.keyboards import cb_button
from app.ui.keyboards import admin_keyboard
from app.ui.renderer import Renderer
from aiogram.types import InlineKeyboardMarkup

router = Router(name="admin")


class AdminSettingsState(StatesGroup):
    support_url = State()
    log_channel_id = State()


def _is_owner(user_id: int, owner_id: int) -> bool:
    return user_id == owner_id


@router.message(Command("admin"))
async def admin_panel(message: Message, settings, repo, renderer: Renderer) -> None:
    if not message.from_user or not _is_owner(message.from_user.id, settings.owner_id):
        await message.answer("<b>🚫 Owner only</b>")
        return
    await message.answer(renderer.admin_dashboard(await repo.stats()), reply_markup=admin_keyboard())


@router.callback_query(F.data.startswith("a:"))
async def admin_section(callback: CallbackQuery, settings, repo, renderer: Renderer, runtime_settings) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    section = next((title for title, data in ADMIN_SECTIONS if data == callback.data), "Admin Section")
    if callback.data == "a:dash":
        await callback.message.edit_text(renderer.admin_dashboard(await repo.stats()), reply_markup=admin_keyboard())
        return
    if callback.data == "a:settings":
        support_url = await runtime_settings.support_url(repo, settings.support_url)
        log_channel_id = await runtime_settings.log_channel_id(repo, settings.log_channel_id)
        await callback.message.edit_text(
            (
                "<b>⚙️ Settings</b>\n\n"
                "These settings are stored in MongoDB, so you do not need to edit Heroku config vars for normal operations.\n\n"
                f"<b>Support URL:</b> {support_url}\n"
                f"<b>Log Channel ID:</b> {log_channel_id or 'Not set'}"
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [cb_button("📞 Set Support URL", "set:support"), cb_button("📜 Set Log Channel", "set:log")],
                    [cb_button("⬅️ Admin", "a:dash")],
                ]
            ),
        )
        return
    await callback.message.edit_text(renderer.admin_section(section), reply_markup=admin_keyboard())


@router.callback_query(F.data == "set:support")
async def set_support_prompt(callback: CallbackQuery, settings, state: FSMContext) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    await state.set_state(AdminSettingsState.support_url)
    await callback.message.edit_text(
        "<b>📞 Set Support URL</b>\n\nSend the Telegram support link now, for example:\nhttps://t.me/your_support"
    )


@router.callback_query(F.data == "set:log")
async def set_log_prompt(callback: CallbackQuery, settings, state: FSMContext) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    await state.set_state(AdminSettingsState.log_channel_id)
    await callback.message.edit_text(
        "<b>📜 Set Log Channel</b>\n\nForward a message from the log channel or send its numeric ID, for example:\n-1001234567890"
    )


@router.message(AdminSettingsState.support_url)
async def save_support_url(message: Message, settings, repo, runtime_settings, state: FSMContext) -> None:
    if not message.from_user or not _is_owner(message.from_user.id, settings.owner_id):
        await state.clear()
        return
    try:
        await runtime_settings.set_support_url(repo, message.text or "", message.from_user.id)
    except ValueError as exc:
        await message.answer(f"<b>Invalid support URL</b>\n\n{exc}")
        return
    await state.clear()
    await message.answer("<b>✅ Support URL saved</b>", reply_markup=admin_keyboard())


@router.message(AdminSettingsState.log_channel_id)
async def save_log_channel(message: Message, settings, repo, runtime_settings, state: FSMContext) -> None:
    if not message.from_user or not _is_owner(message.from_user.id, settings.owner_id):
        await state.clear()
        return
    value = str(message.forward_from_chat.id) if message.forward_from_chat else (message.text or "")
    try:
        chat_id = await runtime_settings.set_log_channel_id(repo, value, message.from_user.id)
    except ValueError:
        await message.answer("<b>Invalid log channel ID</b>\n\nSend a numeric ID like -1001234567890 or forward a channel message.")
        return
    await state.clear()
    await message.answer(f"<b>✅ Log channel saved</b>\n\n<code>{chat_id}</code>", reply_markup=admin_keyboard())
