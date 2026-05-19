from __future__ import annotations

import logging
from aiogram import F, Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, Message, ChatJoinRequest, ChatMemberUpdated

from app.services.errors import ErrorService
from app.services.force_sub import ForceSubscriptionService
from app.services.premium import PremiumService
from app.services.referrals import ReferralService
from app.services.report_engine import ReportEngine
from app.ui.keyboards import (
    copy_menu_keyboard_from_document,
    force_sub_keyboard,
    help_keyboard,
    main_menu_keyboard,
    premium_keyboard,
    referral_keyboard,
    report_actions_keyboard,
    support_keyboard,
)
from app.ui.renderer import Renderer
from app.utils import pretty_json

logger = logging.getLogger(__name__)
router = Router(name="user")


@router.callback_query(F.data == "fs:recheck")
async def cb_recheck_force_sub(
    callback: CallbackQuery,
    repo,
    bot: Bot,
    force_sub: ForceSubscriptionService,
    renderer: Renderer,
    settings,
) -> None:
    user_id = callback.from_user.id
    user_doc = await repo.get_user(user_id)
    owner_id = getattr(settings, "owner_id", 0)
    
    result = await force_sub.check_user_access(bot, repo, user_id, user_doc, owner_id)
    if result is None:
        await callback.answer("✅ Verification successful! Access unlocked.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
            
        # Re-fetch user doc in case it was updated during check
        user_doc = await repo.get_user(user_id)
        if user_doc:
            referrer_id = user_doc.get("referred_by_pending")
            if referrer_id:
                # Reward referrer now that access is verified
                ref_service = ReferralService(settings.referral_reward_days)
                premium_service = PremiumService(settings.premium_plans, settings.referral_reward_days)
                await ref_service.register(repo, referrer_id, user_id, premium_service)
                await repo.db.users.update_one(
                    {"telegram_id": user_id},
                    {"$unset": {"referred_by_pending": ""}}
                )

        await callback.message.answer(
            "<b>🎉 Welcome!</b>\n\nYour access has been verified. You can now use the bot.",
            reply_markup=main_menu_keyboard()
        )
    else:
        missing = result["missing"]
        gs = result["settings"]
        missing_titles = ", ".join(m["title"] for m in missing)
        await callback.answer(f"❌ You still need to join: {missing_titles}", show_alert=True)
        
        required_count = len(await repo.active_force_sub_channels())
        missing_count = len(missing)
        joined_count = required_count - missing_count
        bot_info = await bot.get_me()
        
        text = renderer.force_sub_prompt(
            missing=missing,
            user=callback.from_user,
            bot_name=bot_info.full_name,
            bot_username=bot_info.username,
            required_count=required_count,
            joined_count=joined_count,
            missing_count=missing_count,
            settings=gs,
        )
        
        reply_markup = force_sub_keyboard(missing, gs)
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        except Exception:
            pass


@router.chat_join_request()
async def handle_chat_join_request(
    event: ChatJoinRequest,
    repo,
    bot: Bot,
) -> None:
    user_id = event.from_user.id
    chat_id = event.chat.id
    title = event.chat.title
    
    logger.info("User %s requested to join %s (%s)", user_id, title, chat_id)
    await repo.record_join_request(user_id, chat_id, "pending")
    await repo.log_force_sub_attempt(user_id, chat_id, "pending_request", f"Join request pending for: {title}")
    
    ch = await repo.get_force_sub_channel(chat_id)
    if ch and ch.get("auto_approve"):
        try:
            await bot.approve_chat_join_request(chat_id, user_id)
            await repo.record_join_request(user_id, chat_id, "approved")
            await repo.log("join_request_auto_approved", {"user_id": user_id, "chat_id": chat_id})
        except Exception as exc:
            logger.error("Failed to auto-approve join request for chat %s, user %s: %s", chat_id, user_id, exc)


@router.chat_member()
async def handle_chat_member_update(
    event: ChatMemberUpdated,
    repo,
) -> None:
    chat_id = event.chat.id
    ch = await repo.get_force_sub_channel(chat_id)
    if not ch:
        return
        
    user_id = event.from_user.id
    new_state = event.new_chat_member.status
    
    if new_state in {"left", "kicked"}:
        gs = await repo.get_force_sub_settings()
        if gs.get("leave_behavior") == "block_again":
            await repo.update_user_force_sub_status(user_id, verified=False)
            await repo.log_force_sub_attempt(user_id, chat_id, "left", f"User left required chat: {event.chat.title}")
            logger.info("User %s left required chat %s, access revoked.", user_id, event.chat.title)


@router.message(CommandStart())
async def start(
    message: Message,
    repo,
    report_engine: ReportEngine,
    renderer: Renderer,
    referral_service: ReferralService,
    premium_service: PremiumService,
    force_sub: ForceSubscriptionService,
) -> None:
    if not message.from_user:
        return
    user_doc = await repo.upsert_user(
        {
            "telegram_id": message.from_user.id,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "username": message.from_user.username,
            "language_code": message.from_user.language_code,
        }
    )
    referrer_id = referral_service.parse_start_payload(message.text)
    await referral_service.register(repo, referrer_id, message.from_user.id, premium_service)

    report = report_engine.user_profile(message.from_user, user_doc)
    report_id = await repo.insert_report(report_engine.to_document(report), report.raw)
    report.report_id = report_id
    await message.answer(
        renderer.report(report),
        reply_markup=report_actions_keyboard(report, premium_service.is_premium(user_doc)),
    )
    await message.answer("<b>Main Menu</b>", reply_markup=main_menu_keyboard())


@router.message(F.chat.type == "private")
async def analyze_private_message(
    message: Message,
    repo,
    report_engine: ReportEngine,
    renderer: Renderer,
    premium_service: PremiumService,
    force_sub: ForceSubscriptionService,
    errors: ErrorService,
) -> None:
    if not message.from_user:
        return

    try:
        user_doc = await repo.upsert_user({"telegram_id": message.from_user.id})
        report = report_engine.message_report(message)
        report_id = await repo.insert_report(report_engine.to_document(report), report.raw)
        report.report_id = report_id
        await repo.increment_user_reports(message.from_user.id, report.kind.value)
        await message.answer(
            renderer.report(report),
            reply_markup=report_actions_keyboard(report, premium_service.is_premium(user_doc)),
        )
    except Exception as exc:
        code = await errors.capture(repo, exc, {"handler": "analyze_private_message", "user_id": message.from_user.id})
        await message.answer(renderer.friendly_error(code))


@router.callback_query(F.data == "u:menu")
async def cb_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text("<b>Main Menu</b>", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "u:me")
async def cb_my_info(callback: CallbackQuery, repo, report_engine: ReportEngine, renderer: Renderer, premium_service: PremiumService) -> None:
    await callback.answer()
    user_doc = await repo.upsert_user({"telegram_id": callback.from_user.id})
    report = report_engine.user_profile(callback.from_user, user_doc)
    report.report_id = await repo.insert_report(report_engine.to_document(report), report.raw)
    await callback.message.edit_text(
        renderer.report(report),
        reply_markup=report_actions_keyboard(report, premium_service.is_premium(user_doc)),
    )


@router.callback_query(F.data == "u:analyze")
async def cb_analyze(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "<b>🔍 Analyze Message</b>\n\nSend, forward, reply, or upload any supported Telegram message/media here. "
        "The bot will auto-detect the input and generate the correct report.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "u:help")
async def cb_help(callback: CallbackQuery, renderer: Renderer) -> None:
    await callback.answer()
    await callback.message.edit_text(renderer.help_center(), reply_markup=help_keyboard())


@router.callback_query(F.data == "u:support")
async def cb_support(callback: CallbackQuery, settings, repo, runtime_settings, renderer: Renderer) -> None:
    await callback.answer()
    support_url = await runtime_settings.support_url(repo, settings.support_url)
    await callback.message.edit_text(renderer.support(), reply_markup=support_keyboard(support_url))


@router.callback_query(F.data == "u:premium")
async def cb_premium(callback: CallbackQuery, renderer: Renderer, premium_service: PremiumService) -> None:
    await callback.answer()
    await callback.message.edit_text(renderer.premium_menu(), reply_markup=premium_keyboard(premium_service.plans))


@router.callback_query(F.data == "u:saved")
async def cb_saved_reports(callback: CallbackQuery, repo, renderer: Renderer, premium_service: PremiumService) -> None:
    await callback.answer()
    user_doc = await repo.upsert_user({"telegram_id": callback.from_user.id})
    premium = premium_service.is_premium(user_doc)
    rows = await repo.saved_reports(callback.from_user.id) if premium else []
    await callback.message.edit_text(renderer.saved_reports(rows, premium), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "u:referral")
async def cb_referral(callback: CallbackQuery, referral_service: ReferralService, renderer: Renderer) -> None:
    await callback.answer()
    bot_info = await callback.bot.get_me()
    link = referral_service.referral_link(bot_info.username, callback.from_user.id)
    await callback.message.edit_text(renderer.referral_menu(link), reply_markup=referral_keyboard(link))


@router.callback_query(F.data.startswith("r:copy:"))
async def cb_copy_menu(callback: CallbackQuery, repo, renderer: Renderer) -> None:
    await callback.answer()
    report_id = callback.data.split(":", 2)[2]
    report_doc = await repo.get_report(report_id)
    await callback.message.edit_text(renderer.copy_menu(report_doc), reply_markup=copy_menu_keyboard_from_document(report_doc))


@router.callback_query(F.data.startswith("r:raw:"))
async def cb_raw(callback: CallbackQuery, repo, renderer: Renderer, report_engine: ReportEngine, premium_service: PremiumService) -> None:
    await callback.answer()
    user_doc = await repo.upsert_user({"telegram_id": callback.from_user.id})
    report_id = callback.data.split(":", 2)[2]
    raw = await repo.get_raw_report(report_id)
    await callback.message.edit_text(renderer.raw_document(raw, premium_service.is_premium(user_doc)), reply_markup=main_menu_keyboard())


@router.callback_query(F.data.startswith("r:save:"))
async def cb_save_report(callback: CallbackQuery, repo, renderer: Renderer, premium_service: PremiumService) -> None:
    await callback.answer()
    user_doc = await repo.upsert_user({"telegram_id": callback.from_user.id})
    if not premium_service.is_premium(user_doc):
        await callback.message.edit_text(renderer.premium_required("Saved reports"), reply_markup=premium_keyboard(premium_service.plans))
        return
    report_id = callback.data.split(":", 2)[2]
    if not await repo.get_report(report_id):
        await callback.message.edit_text("<b>💾 Save Report</b>\n\nStored report was not found.", reply_markup=main_menu_keyboard())
        return
    await repo.save_report(callback.from_user.id, report_id)
    await callback.message.edit_text(renderer.report_saved(report_id), reply_markup=main_menu_keyboard())


@router.callback_query(F.data.startswith("r:export:"))
async def cb_export_report(callback: CallbackQuery, repo, renderer: Renderer, premium_service: PremiumService) -> None:
    await callback.answer()
    user_doc = await repo.upsert_user({"telegram_id": callback.from_user.id})
    if not premium_service.is_premium(user_doc):
        await callback.message.edit_text(renderer.premium_required("Report export"), reply_markup=premium_keyboard(premium_service.plans))
        return
    report_id = callback.data.split(":", 2)[2]
    raw = await repo.get_raw_report(report_id)
    if not raw:
        await callback.message.edit_text("<b>📤 Export</b>\n\nStored raw data was not found for this report.", reply_markup=main_menu_keyboard())
        return
    payload = pretty_json(raw).encode("utf-8")
    await callback.message.answer_document(
        BufferedInputFile(payload, filename=f"telegram-report-{report_id}.json"),
        caption="📤 Premium JSON export",
    )
