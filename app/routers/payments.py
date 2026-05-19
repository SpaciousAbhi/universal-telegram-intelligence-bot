from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from app.services.premium import PremiumService
from app.ui.keyboards import main_menu_keyboard

router = Router(name="payments")


@router.callback_query(F.data.startswith("pay:"))
async def cb_buy_premium(callback: CallbackQuery, premium_service: PremiumService) -> None:
    await callback.answer()
    code = callback.data.split(":", 1)[1]
    plan = premium_service.get_plan(code)
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Premium - {plan.title}",
        description="Unlock raw data, exports, saved reports, comparison, and developer tools.",
        payload=f"premium:{plan.code}:{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=plan.title, amount=plan.stars)],
        provider_token="",
    )


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery, premium_service: PremiumService) -> None:
    try:
        parts = pre_checkout_query.invoice_payload.split(":")
        ok = len(parts) == 3 and parts[0] == "premium"
        if ok:
            premium_service.get_plan(parts[1])
        await pre_checkout_query.answer(ok=ok, error_message=None if ok else "Unknown premium plan.")
    except Exception:
        await pre_checkout_query.answer(ok=False, error_message="Payment could not be validated.")


@router.message(F.successful_payment)
async def successful_payment(message: Message, repo, premium_service: PremiumService) -> None:
    payment = message.successful_payment
    parts = payment.invoice_payload.split(":")
    plan = premium_service.get_plan(parts[1])
    expiry = await premium_service.activate(
        repo,
        message.from_user.id,
        plan.days,
        "telegram_stars",
        {
            "currency": payment.currency,
            "total_amount": payment.total_amount,
            "telegram_payment_charge_id": payment.telegram_payment_charge_id,
            "provider_payment_charge_id": payment.provider_payment_charge_id,
        },
    )
    await message.answer(
        f"<b>⭐ Premium Activated</b>\n\nPlan: {plan.title}\nValid until: {expiry.isoformat()}",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("paysupport"))
async def pay_support(message: Message, settings, repo, runtime_settings) -> None:
    support_url = await runtime_settings.support_url(repo, settings.support_url)
    await message.answer(
        "<b>Payment Support</b>\n\n"
        "For Telegram Stars payment issues, contact support with your payment date and Telegram payment charge ID if available.\n"
        f"Support: {support_url}"
    )
