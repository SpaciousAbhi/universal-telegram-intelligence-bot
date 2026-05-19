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
    fsub_add = State()
    fsub_delete = State()
    fsub_btn_text = State()
    fsub_msg_template = State()



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
    if callback.data == "a:fsub":
        gs = await repo.get_force_sub_settings()
        channels = await repo.get_force_sub_channels()
        
        status_text = "🟢 Enabled" if gs.get("enabled") else "🔴 Disabled"
        text = (
            "<b>🔐 Force Subscribe Manager</b>\n\n"
            f"<b>Status:</b> {status_text}\n"
            f"<b>Total Channels:</b> {len(channels)}\n\n"
        )
        if channels:
            text += "<b>Configured Channels:</b>\n"
            for i, ch in enumerate(channels, 1):
                chat_id = ch["chat_id"]
                title = ch.get("title", f"Chat {chat_id}")
                mode = ch.get("mode", "normal")
                active = "🟢" if ch.get("active", True) else "🔴"
                text += f"{i}. {active} <b>{title}</b> (<code>{chat_id}</code>) | {mode}\n"
        else:
            text += "<i>No force-sub channels configured yet.</i>"
            
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    cb_button("🔴 Disable" if gs.get("enabled") else "🟢 Enable", "fsub:toggle"),
                    cb_button("➕ Add Channel", "fsub:add")
                ],
                [
                    cb_button("⚙️ Global Settings", "fsub:settings"),
                    cb_button("🗑️ Delete Channel", "fsub:delete")
                ],
                [cb_button("⬅️ Admin Dashboard", "a:dash")]
            ]
        )
        await callback.message.edit_text(text, reply_markup=keyboard)
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


@router.callback_query(F.data == "fsub:toggle")
async def fsub_toggle(callback: CallbackQuery, settings, repo, renderer: Renderer) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    gs = await repo.get_force_sub_settings()
    gs["enabled"] = not gs.get("enabled", False)
    await repo.set_force_sub_settings(gs, callback.from_user.id)
    
    channels = await repo.get_force_sub_channels()
    status_text = "🟢 Enabled" if gs.get("enabled") else "🔴 Disabled"
    text = (
        "<b>🔐 Force Subscribe Manager</b>\n\n"
        f"<b>Status:</b> {status_text}\n"
        f"<b>Total Channels:</b> {len(channels)}\n\n"
    )
    if channels:
        text += "<b>Configured Channels:</b>\n"
        for i, ch in enumerate(channels, 1):
            chat_id = ch["chat_id"]
            title = ch.get("title", f"Chat {chat_id}")
            mode = ch.get("mode", "normal")
            active = "🟢" if ch.get("active", True) else "🔴"
            text += f"{i}. {active} <b>{title}</b> (<code>{chat_id}</code>) | {mode}\n"
    else:
        text += "<i>No force-sub channels configured yet.</i>"
        
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                cb_button("🔴 Disable" if gs.get("enabled") else "🟢 Enable", "fsub:toggle"),
                cb_button("➕ Add Channel", "fsub:add")
            ],
            [
                cb_button("⚙️ Global Settings", "fsub:settings"),
                cb_button("🗑️ Delete Channel", "fsub:delete")
            ],
            [cb_button("⬅️ Admin Dashboard", "a:dash")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "fsub:add")
async def fsub_add_prompt(callback: CallbackQuery, settings, state: FSMContext) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    await state.set_state(AdminSettingsState.fsub_add)
    await callback.message.edit_text(
        "<b>➕ Add Force Subscribe Channel</b>\n\n"
        "<b>Option 1 — Forward a message:</b>\n"
        "Forward any message from the channel/group you want to add. The bot will auto-detect the chat ID and title.\n\n"
        "<b>Option 2 — Send ID or Username:</b>\n"
        "<code>-1001234567890</code> or <code>@mychannel</code>\n\n"
        "<b>Option 3 — Detailed format (comma-separated):</b>\n"
        "<code>chat_id, invite_link, title, mode, button_text</code>\n\n"
        "Examples:\n"
        "<code>-1001234567890, https://t.me/+xyz, My Channel, join_request, Join Channel</code>\n\n"
        "Send now, or send /cancel to cancel.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("❌ Cancel", "a:fsub")]])
    )



@router.message(AdminSettingsState.fsub_add)
async def fsub_add_save(message: Message, settings, repo, state: FSMContext) -> None:
    if not message.from_user or not _is_owner(message.from_user.id, settings.owner_id):
        await state.clear()
        return
    
    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("<b>❌ Action cancelled.</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("⬅️ Back", "a:fsub")]]))
        return

    # Option 1: Forwarded message — auto-detect chat info
    fwd_chat = None
    if message.forward_from_chat:
        fwd_chat = message.forward_from_chat
    elif getattr(message, "forward_origin", None):
        origin = message.forward_origin
        if hasattr(origin, "chat"):
            fwd_chat = origin.chat

    if fwd_chat:
        chat_id = fwd_chat.id
        title = getattr(fwd_chat, "title", None) or getattr(fwd_chat, "full_name", None) or f"Chat {chat_id}"
        username = getattr(fwd_chat, "username", None)
        invite_link = f"https://t.me/{username}" if username else ""
        
        await repo.add_force_sub_channel({
            "chat_id": chat_id,
            "invite_link": invite_link,
            "title": title,
            "mode": "normal",
            "button_text": f"Join {title}",
            "active": True
        })
        
        await state.clear()
        await message.answer(
            "<b>✅ Channel Added from Forward!</b>\n\n"
            f"<b>ID:</b> <code>{chat_id}</code>\n"
            f"<b>Title:</b> {title}\n"
            f"<b>Username:</b> {'@' + username if username else 'N/A'}\n"
            f"<b>Link:</b> {invite_link or 'None'}\n"
            f"<b>Mode:</b> normal",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("⬅️ Back to Manager", "a:fsub")]])
        )
        return

    # Option 2/3: Text input
    if not text:
        await message.answer("<b>Invalid input.</b> Forward a channel message, or send the chat ID/username. Send /cancel to cancel.")
        return

    parts = [p.strip() for p in text.split(",")]
    if not parts or not parts[0]:
        await message.answer("<b>Invalid input.</b> Please try again or send /cancel.")
        return
        
    raw_chat_id = parts[0]
    try:
        chat_id_val: int | str = int(raw_chat_id)
    except ValueError:
        chat_id_val = raw_chat_id
        
    invite_link = parts[1] if len(parts) > 1 else ""
    title = parts[2] if len(parts) > 2 else f"Channel {raw_chat_id}"
    mode = parts[3] if len(parts) > 3 and parts[3] in ("normal", "join_request") else "normal"
    btn_text = parts[4] if len(parts) > 4 else f"Join {title}"
    
    await repo.add_force_sub_channel({
        "chat_id": chat_id_val,
        "invite_link": invite_link,
        "title": title,
        "mode": mode,
        "button_text": btn_text,
        "active": True
    })
    
    await state.clear()
    await message.answer(
        "<b>✅ Channel Configured Successfully!</b>\n\n"
        f"<b>ID:</b> <code>{chat_id_val}</code>\n"
        f"<b>Title:</b> {title}\n"
        f"<b>Mode:</b> {mode}\n"
        f"<b>Btn Text:</b> {btn_text}\n"
        f"<b>Link:</b> {invite_link or 'None'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("⬅️ Back to Manager", "a:fsub")]])
    )



@router.callback_query(F.data == "fsub:delete")
async def fsub_delete_prompt(callback: CallbackQuery, settings, state: FSMContext) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    await state.set_state(AdminSettingsState.fsub_delete)
    await callback.message.edit_text(
        "<b>🗑️ Delete Force Subscribe Channel</b>\n\n"
        "Send the Chat ID or Username of the channel/group you wish to delete from force subscription, or send /cancel to cancel.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("❌ Cancel", "a:fsub")]])
    )


@router.message(AdminSettingsState.fsub_delete)
async def fsub_delete_save(message: Message, settings, repo, state: FSMContext) -> None:
    if not message.from_user or not _is_owner(message.from_user.id, settings.owner_id):
        await state.clear()
        return
        
    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("<b>❌ Action cancelled.</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("⬅️ Back", "a:fsub")]]))
        return
        
    await repo.remove_force_sub_channel(text)
    await state.clear()
    await message.answer(
        f"<b>🗑️ Removed channel/group:</b> <code>{text}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("⬅️ Back to Manager", "a:fsub")]])
    )


@router.callback_query(F.data == "fsub:settings")
async def fsub_settings_menu(callback: CallbackQuery, settings, repo) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    gs = await repo.get_force_sub_settings()
    
    bypass_text = "🟢 Enabled (Admin Bypassed)" if gs.get("admin_bypass") else "🔴 Disabled (Admin Checked)"
    text = (
        "<b>⚙️ Force Subscribe Global Settings</b>\n\n"
        f"<b>Verification Button Text:</b> <code>{gs.get('button_text')}</code>\n"
        f"<b>Admin/Owner Bypass:</b> {bypass_text}\n\n"
        f"<b>Message Template:</b>\n"
        f"----------\n"
        f"{gs.get('message_template')}\n"
        f"----------"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                cb_button("✏️ Set Button Text", "fsub:set_btn"),
                cb_button("✏️ Set Msg Template", "fsub:set_msg")
            ],
            [
                cb_button("Toggle Admin Bypass", "fsub:toggle_bypass")
            ],
            [cb_button("⬅️ Back to Manager", "a:fsub")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "fsub:toggle_bypass")
async def fsub_toggle_bypass(callback: CallbackQuery, settings, repo) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    gs = await repo.get_force_sub_settings()
    gs["admin_bypass"] = not gs.get("admin_bypass", True)
    await repo.set_force_sub_settings(gs, callback.from_user.id)
    
    bypass_text = "🟢 Enabled (Admin Bypassed)" if gs.get("admin_bypass") else "🔴 Disabled (Admin Checked)"
    text = (
        "<b>⚙️ Force Subscribe Global Settings</b>\n\n"
        f"<b>Verification Button Text:</b> <code>{gs.get('button_text')}</code>\n"
        f"<b>Admin/Owner Bypass:</b> {bypass_text}\n\n"
        f"<b>Message Template:</b>\n"
        f"----------\n"
        f"{gs.get('message_template')}\n"
        f"----------"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                cb_button("✏️ Set Button Text", "fsub:set_btn"),
                cb_button("✏️ Set Msg Template", "fsub:set_msg")
            ],
            [
                cb_button("Toggle Admin Bypass", "fsub:toggle_bypass")
            ],
            [cb_button("⬅️ Back to Manager", "a:fsub")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "fsub:set_btn")
async def fsub_set_btn_prompt(callback: CallbackQuery, settings, state: FSMContext) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    await state.set_state(AdminSettingsState.fsub_btn_text)
    await callback.message.edit_text(
        "<b>✏️ Set Verification Button Text</b>\n\n"
        "Send the new text for the verification button now, or send /cancel to cancel.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("❌ Cancel", "fsub:settings")]])
    )


@router.message(AdminSettingsState.fsub_btn_text)
async def fsub_btn_text_save(message: Message, settings, repo, state: FSMContext) -> None:
    if not message.from_user or not _is_owner(message.from_user.id, settings.owner_id):
        await state.clear()
        return
    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("<b>❌ Action cancelled.</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("⬅️ Back", "fsub:settings")]]))
        return
    if not text:
        await message.answer("<b>Button text cannot be empty.</b> Please try again or send /cancel.")
        return
    gs = await repo.get_force_sub_settings()
    gs["button_text"] = text
    await repo.set_force_sub_settings(gs, message.from_user.id)
    await state.clear()
    await message.answer(
        f"<b>✅ Verification button text updated to:</b>\n<code>{text}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("⬅️ Back to Settings", "fsub:settings")]])
    )


@router.callback_query(F.data == "fsub:set_msg")
async def fsub_set_msg_prompt(callback: CallbackQuery, settings, state: FSMContext) -> None:
    await callback.answer()
    if not _is_owner(callback.from_user.id, settings.owner_id):
        await callback.message.edit_text("<b>🚫 Owner only</b>")
        return
    await state.set_state(AdminSettingsState.fsub_msg_template)
    await callback.message.edit_text(
        "<b>✏️ Set Message Template</b>\n\n"
        "Send the new text template now. You can use placeholders like <code>{first_name}</code>, <code>{last_name}</code>, <code>{username}</code>, <code>{user_id}</code>.\n\n"
        "Or send /cancel to cancel.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("❌ Cancel", "fsub:settings")]])
    )


@router.message(AdminSettingsState.fsub_msg_template)
async def fsub_msg_template_save(message: Message, settings, repo, state: FSMContext) -> None:
    if not message.from_user or not _is_owner(message.from_user.id, settings.owner_id):
        await state.clear()
        return
    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("<b>❌ Action cancelled.</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("⬅️ Back", "fsub:settings")]]))
        return
    if not text:
        await message.answer("<b>Message template cannot be empty.</b> Please try again or send /cancel.")
        return
    gs = await repo.get_force_sub_settings()
    gs["message_template"] = text
    await repo.set_force_sub_settings(gs, message.from_user.id)
    await state.clear()
    await message.answer(
        f"<b>✅ Message template updated to:</b>\n\n{text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cb_button("⬅️ Back to Settings", "fsub:settings")]])
    )

