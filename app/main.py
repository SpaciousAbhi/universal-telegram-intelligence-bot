from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.config import get_settings
from app.constants import VISIBLE_COMMANDS
from app.repositories import MongoRepository
from app.routers import admin, group, payments, user
from app.services.errors import ErrorService
from app.services.force_sub import ForceSubscriptionService
from app.services.premium import PremiumService
from app.services.referrals import ReferralService
from app.services.report_engine import ReportEngine
from app.services.settings import RuntimeSettingsService
from app.ui.renderer import Renderer


async def build_dispatcher() -> tuple[Bot, Dispatcher, MongoRepository]:
    settings = get_settings()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    repo = MongoRepository(settings.mongo_uri, settings.db_name)
    await repo.ping()
    await repo.ensure_indexes()
    dp = Dispatcher(
        settings=settings,
        repo=repo,
        report_engine=ReportEngine(),
        renderer=Renderer(),
        premium_service=PremiumService(settings.premium_plans, settings.referral_reward_days),
        referral_service=ReferralService(settings.referral_reward_days),
        force_sub=ForceSubscriptionService(),
        errors=ErrorService(),
        runtime_settings=RuntimeSettingsService(),
    )
    dp.include_router(payments.router)
    dp.include_router(admin.router)
    dp.include_router(group.router)
    dp.include_router(user.router)
    return bot, dp, repo


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    bot, dp, repo = await build_dispatcher()
    commands = [BotCommand(command=cmd, description=desc) for cmd, desc in VISIBLE_COMMANDS.items()]
    await bot.set_my_commands(commands)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await repo.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
