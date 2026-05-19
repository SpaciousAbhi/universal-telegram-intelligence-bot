from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from aiogram import Bot, BaseMiddleware
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)


class ForceSubscriptionService:
    async def check_user_access(
        self, bot: Bot, repo: Any, user_id: int, user_doc: dict[str, Any] | None, owner_id: int
    ) -> dict[str, Any] | None:
        """
        Verifies if the user passes force subscription checks.
        Returns a dict with {"missing": list_of_missing_channels, "settings": global_settings}
        if access is blocked, or None if the user is verified/bypassed.
        """
        # Load global settings
        gs = await repo.get_force_sub_settings()
        if not gs.get("enabled"):
            return None

        # 1. Bypass check
        # Owner/Admin bypass
        if gs.get("admin_bypass") and user_id == owner_id:
            return None
        # User-specific bypass
        if user_id in gs.get("bypass_users", []):
            return None
        # Check user doc for bypass flag
        if user_doc and user_doc.get("fs_bypass"):
            return None

        # 2. Recheck policy check
        if user_doc and user_doc.get("fs_verified"):
            recheck_mode = gs.get("recheck_mode", "every_time")
            if recheck_mode == "once":
                return None
            elif recheck_mode == "time_limit":
                last_verified = user_doc.get("fs_last_verified_at")
                if last_verified:
                    if last_verified.tzinfo is None:
                        last_verified = last_verified.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    diff = (now - last_verified).total_seconds()
                    if diff < gs.get("recheck_ttl_seconds", 86400):
                        return None

        # 3. Check active channels
        channels = await repo.active_force_sub_channels()
        if not channels:
            # If no channels are active, access is granted
            await repo.update_user_force_sub_status(user_id, verified=True)
            return None

        missing: list[dict[str, Any]] = []

        for ch in channels:
            chat_id = ch["chat_id"]
            title = ch.get("title", f"Chat {chat_id}")
            mode = ch.get("mode", "normal")  # "normal" or "join_request"
            allow_pending = ch.get("allow_pending_request", False)

            # Check membership
            joined = False
            status = "not_joined"
            bot_status = "ok"

            try:
                member = await bot.get_chat_member(chat_id, user_id)
                m_status = getattr(member, "status", None)
                if m_status in {"creator", "administrator", "member"}:
                    joined = True
                elif m_status == "restricted" and getattr(member, "is_member", False):
                    joined = True
                else:
                    status = "not_joined"
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                err_msg = str(exc)
                logger.warning("Bot failed to check chat %s member %s: %s", chat_id, user_id, err_msg)
                # Update bot permission status in DB
                bot_status = f"error: {err_msg[:100]}"
                status = "not_joined"
            except Exception as exc:
                err_msg = str(exc)
                logger.error("Unexpected error checking chat %s member %s: %s", chat_id, user_id, err_msg)
                bot_status = f"error: {err_msg[:100]}"
                status = "not_joined"

            # Update bot status for this channel in DB
            if bot_status != ch.get("bot_status"):
                await repo.add_force_sub_channel({**ch, "bot_status": bot_status})

            # If not direct member, inspect Join Request Mode if configured
            if not joined and mode == "join_request":
                req = await repo.get_join_request(user_id, chat_id)
                if req:
                    req_status = req.get("status")
                    if req_status == "approved":
                        joined = True
                    elif req_status == "pending":
                        if allow_pending:
                            joined = True
                        else:
                            status = "pending_request"
                    else:
                        status = "not_joined"

            if not joined:
                missing.append({
                    "chat_id": chat_id,
                    "title": title,
                    "invite_link": ch.get("invite_link"),
                    "button_text": ch.get("button_text") or f"Join {title}",
                    "status": status,
                })
                await repo.log_force_sub_attempt(user_id, chat_id, status, f"Missing channel: {title}")

        if not missing:
            await repo.update_user_force_sub_status(user_id, verified=True)
            return None

        if user_doc and user_doc.get("fs_verified") and gs.get("leave_behavior") == "block_again":
            await repo.update_user_force_sub_status(user_id, verified=False)

        return {"missing": missing, "settings": gs}


class ForceSubMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        is_private = False
        user_id = 0
        message = None
        callback = None
        is_command = False
        is_start = False
        
        if isinstance(event, Message):
            is_private = event.chat.type == "private"
            user_id = event.from_user.id if event.from_user else 0
            message = event
            if event.text:
                is_command = event.text.startswith("/")
                is_start = event.text.startswith("/start")
        elif isinstance(event, CallbackQuery):
            is_private = event.message and event.message.chat.type == "private" if event.message else True
            user_id = event.from_user.id
            callback = event
            if event.data == "fs:recheck":
                return await handler(event, data)
                
        if not is_private or not user_id:
            return await handler(event, data)
            
        repo = data.get("repo")
        bot = data.get("bot")
        force_sub = data.get("force_sub")
        renderer = data.get("renderer")
        settings = data.get("settings")
        
        if not (repo and bot and force_sub and renderer and settings):
            return await handler(event, data)

        if await repo.is_banned(user_id):
            if message:
                await message.answer("<b>🚫 Access denied</b>\n\nYour account is banned from using this bot.")
            elif callback:
                await callback.answer("🚫 Your account is banned from using this bot.", show_alert=True)
            return

        if is_start and message and message.text:
            from app.services.referrals import ReferralService
            ref_service = ReferralService(settings.referral_reward_days)
            referrer_id = ref_service.parse_start_payload(message.text)
            if referrer_id:
                await repo.db.users.update_one(
                    {"telegram_id": user_id},
                    {"$setOnInsert": {"referred_by_pending": referrer_id}},
                    upsert=True
                )

        gs = await repo.get_force_sub_settings()
        if not gs.get("enabled"):
            return await handler(event, data)
            
        check_mode = gs.get("check_mode", "all")
        event_type = "message"
        if callback:
            event_type = "callback"
        elif is_start:
            event_type = "start"
        elif is_command:
            event_type = "command"
            
        should_check = False
        if check_mode == "start":
            should_check = (event_type == "start")
        elif check_mode == "command":
            should_check = (event_type in {"start", "command"})
        else:
            should_check = True
            
        if not should_check:
            return await handler(event, data)
            
        owner_id = getattr(settings, "owner_id", 0)
        user_doc = await repo.get_user(user_id)
        
        result = await force_sub.check_user_access(bot, repo, user_id, user_doc, owner_id)
        if result is not None:
            missing = result["missing"]
            global_settings = result["settings"]
            
            required_count = len(await repo.active_force_sub_channels())
            missing_count = len(missing)
            joined_count = required_count - missing_count
            
            user_obj = event.from_user
            bot_info = await bot.get_me()
            
            text = renderer.force_sub_prompt(
                user=user_obj,
                bot_name=bot_info.full_name,
                bot_username=bot_info.username,
                required_count=required_count,
                joined_count=joined_count,
                missing_count=missing_count,
                settings=global_settings,
                missing=missing
            )
            
            from app.ui.keyboards import force_sub_keyboard
            reply_markup = force_sub_keyboard(missing, global_settings)
            
            media_file_id = global_settings.get("media_file_id")
            media_type = global_settings.get("media_type")
            
            if message:
                if media_file_id and media_type:
                    try:
                        if media_type == "photo":
                            await message.answer_photo(media_file_id, caption=text, reply_markup=reply_markup)
                        elif media_type == "video":
                            await message.answer_video(media_file_id, caption=text, reply_markup=reply_markup)
                        elif media_type == "animation":
                            await message.answer_animation(media_file_id, caption=text, reply_markup=reply_markup)
                        else:
                            await message.answer(text, reply_markup=reply_markup)
                    except Exception as e:
                        logger.error("Failed to send force-sub media: %s. Falling back to text.", e)
                        await message.answer(text, reply_markup=reply_markup)
                else:
                    await message.answer(text, reply_markup=reply_markup)
            elif callback:
                try:
                    await callback.message.edit_text(text, reply_markup=reply_markup)
                except Exception:
                    await callback.answer("🔒 Please join all required channels first!", show_alert=True)
            return
            
        return await handler(event, data)
