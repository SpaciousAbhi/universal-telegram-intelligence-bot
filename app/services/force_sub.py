from __future__ import annotations

from typing import Any


class ForceSubscriptionService:
    async def missing_channels(self, bot: Any, repo: Any, user_id: int) -> list[dict[str, Any]]:
        missing: list[dict[str, Any]] = []
        for channel in await repo.active_force_sub_channels():
            chat_id = channel["chat_id"]
            try:
                member = await bot.get_chat_member(chat_id, user_id)
                status = getattr(member, "status", None)
                if status in {"left", "kicked"}:
                    missing.append(channel)
            except Exception:
                missing.append({**channel, "reason": "Bot has no access or channel is private"})
        return missing

    async def gate_or_none(self, bot: Any, repo: Any, user_id: int) -> list[dict[str, Any]] | None:
        missing = await self.missing_channels(bot, repo, user_id)
        return missing or None

