from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.models import BroadcastStats


class BroadcastService:
    async def run_text_broadcast(self, bot: Any, repo: Any, text: str, users: list[dict[str, Any]]) -> BroadcastStats:
        stats = BroadcastStats(total=len(users))
        for user in users:
            user_id = user.get("telegram_id")
            if not user_id:
                stats.invalid += 1
                continue
            try:
                await bot.send_message(user_id, text)
                stats.sent += 1
            except Exception as exc:
                message = str(exc).lower()
                if "blocked" in message or "forbidden" in message:
                    stats.blocked += 1
                else:
                    stats.failed += 1
        await repo.log("broadcast_finished", asdict(stats))
        return stats

    def summary(self, stats: BroadcastStats) -> str:
        return (
            "📢 Broadcast Summary\n\n"
            f"Total: {stats.total}\n"
            f"Sent: {stats.sent}\n"
            f"Failed: {stats.failed}\n"
            f"Blocked: {stats.blocked}\n"
            f"Invalid: {stats.invalid}\n"
            f"Remaining: {stats.remaining}"
        )
