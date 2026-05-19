from __future__ import annotations

from typing import Any


class RuntimeSettingsService:
    """DB-backed settings that avoid Heroku config edits for normal operations."""

    SUPPORT_URL = "support_url"
    LOG_CHANNEL_ID = "log_channel_id"

    async def support_url(self, repo: Any, fallback: str) -> str:
        return await repo.get_setting(self.SUPPORT_URL, fallback)

    async def log_channel_id(self, repo: Any, fallback: int | None = None) -> int | None:
        value = await repo.get_setting(self.LOG_CHANNEL_ID, fallback)
        if value in (None, ""):
            return None
        return int(value)

    async def set_support_url(self, repo: Any, value: str, owner_id: int) -> None:
        value = value.strip()
        if not (value.startswith("https://t.me/") or value.startswith("http://t.me/") or value.startswith("tg://")):
            raise ValueError("Support URL must be a Telegram link, for example https://t.me/your_support")
        await repo.set_setting(self.SUPPORT_URL, value, owner_id)

    async def set_log_channel_id(self, repo: Any, value: str, owner_id: int) -> int:
        chat_id = int(value.strip())
        await repo.set_setting(self.LOG_CHANNEL_ID, chat_id, owner_id)
        return chat_id
