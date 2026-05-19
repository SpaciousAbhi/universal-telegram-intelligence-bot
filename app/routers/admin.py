from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.constants import ADMIN_SECTIONS
from app.ui.keyboards import admin_keyboard
from app.ui.renderer import Renderer

router = Router(name="admin")


def _is_owner(user_id: int, owner_id: int) -> bool:
    return user_id == owner_id


@router.message(Command("admin"))
async def admin_panel(message: Message, settings, repo, renderer: Renderer) -> None:
    if not message.from_user or not _is_owner(message.from_user.id, settings.owner_id):
        await message.answer("<b>🚫 Owner only</b>")
        return
    await message.answer(renderer.admin_dashboard(await repo.stats()), reply_markup=admin_keyboard())


@router.callback_query(F.data.startswith("a:"))
async def admin_section(callback: CallbackQuery, settings, repo, renderer: Renderer) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    section = next((title for title, data in ADMIN_SECTIONS if data == callback.data), "Admin Section")
    if callback.data == "a:dash":
        await callback.message.edit_text(renderer.admin_dashboard(await repo.stats()), reply_markup=admin_keyboard())
        return
    await callback.message.edit_text(renderer.admin_section(section), reply_markup=admin_keyboard())

