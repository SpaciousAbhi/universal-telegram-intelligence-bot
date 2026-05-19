from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PremiumPlanConfig(dict):
    code: str
    title: str
    days: int
    stars: int


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    owner_id: int = Field(alias="OWNER_ID")
    mongo_uri: str = Field(validation_alias=AliasChoices("MONGO_URI", "MONGO_URL", "MONGODB_URI", "MONGODB_URL"))
    db_name: str = Field(default="telegram_intelligence_bot", alias="DB_NAME")
    log_channel_id: int | None = Field(default=None, alias="LOG_CHANNEL_ID")
    support_url: str = Field(default="https://t.me/support", alias="SUPPORT_URL")
    heroku_app_name: str | None = Field(default=None, alias="HEROKU_APP_NAME")
    group_cooldown_seconds: int = Field(default=20, alias="GROUP_COOLDOWN_SECONDS")
    default_timezone: str = Field(default="UTC", alias="DEFAULT_TIMEZONE")
    premium_plans_json: str = Field(
        default='[{"code":"p30","title":"30 days","days":30,"stars":199},{"code":"p90","title":"90 days","days":90,"stars":499},{"code":"p365","title":"1 year","days":365,"stars":1499}]',
        alias="PREMIUM_PLANS_JSON",
    )
    referral_reward_days: int = Field(default=3, alias="REFERRAL_REWARD_DAYS")

    @field_validator("bot_token", "mongo_uri")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("value cannot be blank")
        return value.strip()

    @property
    def premium_plans(self) -> list[dict[str, Any]]:
        parsed = json.loads(self.premium_plans_json)
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("PREMIUM_PLANS_JSON must be a non-empty JSON list")
        for plan in parsed:
            if not {"code", "title", "days", "stars"}.issubset(plan):
                raise ValueError("each premium plan needs code, title, days, and stars")
        return parsed


@lru_cache
def get_settings() -> Settings:
    return Settings()
