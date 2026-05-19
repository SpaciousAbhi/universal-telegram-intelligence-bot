from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, Message

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

router = Router(name="user")


async def _blocked_or_gated(message: Message, repo, renderer: Renderer, force_sub: ForceSubscriptionService) -> bool:
    user_id = message.from_user.id if message.from_user else 0
    if await repo.is_banned(user_id):
        await message.answer("<b>🚫 Access denied</b>\n\nYour account is banned from using this bot.")
        return True
    missing = await force_sub.gate_or_none(message.bot, repo, user_id)
    if missing:
        await message.answer(renderer.force_sub_prompt(missing), reply_markup=force_sub_keyboard(missing))
        return True
    return False


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
    if await _blocked_or_gated(message, repo, renderer, force_sub):
        return
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
    if await _blocked_or_gated(message, repo, renderer, force_sub):
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
async def cb_support(callback: CallbackQuery, settings, renderer: Renderer) -> None:
    await callback.answer()
    await callback.message.edit_text(renderer.support(), reply_markup=support_keyboard(settings.support_url))


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
