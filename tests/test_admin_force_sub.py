from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace as NS
from aiogram.fsm.context import FSMContext

from app.routers.admin import (
    fsub_toggle,
    fsub_add_save,
    fsub_delete_save,
    fsub_toggle_bypass,
    fsub_btn_text_save,
    fsub_msg_template_save,
)
from app.repositories.memory import MemoryRepository

@pytest.mark.asyncio
async def test_fsub_toggle_toggles_enabled_state() -> None:
    repo = MemoryRepository()
    gs = await repo.get_force_sub_settings()
    assert gs["enabled"] is False

    callback = AsyncMock()
    callback.from_user.id = 6938449843
    settings = NS(owner_id=6938449843)
    renderer = MagicMock()

    await fsub_toggle(callback, settings, repo, renderer)

    updated_gs = await repo.get_force_sub_settings()
    assert updated_gs["enabled"] is True

@pytest.mark.asyncio
async def test_fsub_add_save_correctly_parses_input() -> None:
    repo = MemoryRepository()
    message = AsyncMock()
    message.from_user.id = 6938449843
    message.text = "-1001234567890, https://t.me/+xyz, My Channel, join_request, Join Channel"
    message.forward_from_chat = None
    message.forward_origin = None
    settings = NS(owner_id=6938449843)
    state = AsyncMock(spec=FSMContext)

    await fsub_add_save(message, settings, repo, state)

    channels = await repo.get_force_sub_channels()
    assert len(channels) == 1
    assert channels[0]["chat_id"] == -1001234567890
    assert channels[0]["invite_link"] == "https://t.me/+xyz"
    assert channels[0]["title"] == "My Channel"
    assert channels[0]["mode"] == "join_request"
    assert channels[0]["button_text"] == "Join Channel"
    state.clear.assert_called_once()

@pytest.mark.asyncio
async def test_fsub_delete_save_removes_channel() -> None:
    repo = MemoryRepository()
    await repo.add_force_sub_channel({
        "chat_id": -1001234567890,
        "invite_link": "https://t.me/+xyz",
        "title": "My Channel",
        "mode": "join_request",
        "button_text": "Join Channel",
        "active": True
    })

    message = AsyncMock()
    message.from_user.id = 6938449843
    message.text = "-1001234567890"
    settings = NS(owner_id=6938449843)
    state = AsyncMock(spec=FSMContext)

    await fsub_delete_save(message, settings, repo, state)

    channels = await repo.get_force_sub_channels()
    assert len(channels) == 0
    state.clear.assert_called_once()

@pytest.mark.asyncio
async def test_fsub_toggle_bypass_toggles_bypass_state() -> None:
    repo = MemoryRepository()
    gs = await repo.get_force_sub_settings()
    assert gs["admin_bypass"] is True

    callback = AsyncMock()
    callback.from_user.id = 6938449843
    settings = NS(owner_id=6938449843)

    await fsub_toggle_bypass(callback, settings, repo)

    updated_gs = await repo.get_force_sub_settings()
    assert updated_gs["admin_bypass"] is False

@pytest.mark.asyncio
async def test_fsub_btn_text_save_updates_settings() -> None:
    repo = MemoryRepository()
    message = AsyncMock()
    message.from_user.id = 6938449843
    message.text = "New Verification Button"
    settings = NS(owner_id=6938449843)
    state = AsyncMock(spec=FSMContext)

    await fsub_btn_text_save(message, settings, repo, state)

    gs = await repo.get_force_sub_settings()
    assert gs["button_text"] == "New Verification Button"
    state.clear.assert_called_once()

@pytest.mark.asyncio
async def test_fsub_msg_template_save_updates_settings() -> None:
    repo = MemoryRepository()
    message = AsyncMock()
    message.from_user.id = 6938449843
    message.text = "New Message Template: {first_name}"
    settings = NS(owner_id=6938449843)
    state = AsyncMock(spec=FSMContext)

    await fsub_msg_template_save(message, settings, repo, state)

    gs = await repo.get_force_sub_settings()
    assert gs["message_template"] == "New Message Template: {first_name}"
    state.clear.assert_called_once()
