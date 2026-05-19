from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.models import PremiumPlan


class PremiumService:
    def __init__(self, plans: list[dict[str, Any]], reward_days: int = 3) -> None:
        self.plans = [PremiumPlan(**plan) for plan in plans]
        self.reward_days = reward_days

    def get_plan(self, code: str) -> PremiumPlan:
        for plan in self.plans:
            if plan.code == code:
                return plan
        raise ValueError("unknown premium plan")

    @staticmethod
    def is_premium(user_doc: dict[str, Any] | None) -> bool:
        until = (user_doc or {}).get("premium_until")
        if not until:
            return False
        if isinstance(until, str):
            until = datetime.fromisoformat(until)
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return until > datetime.now(timezone.utc)

    def new_expiry(self, user_doc: dict[str, Any] | None, days: int) -> datetime:
        now = datetime.now(timezone.utc)
        current = (user_doc or {}).get("premium_until")
        if isinstance(current, str):
            current = datetime.fromisoformat(current)
        if isinstance(current, datetime) and current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        base = current if isinstance(current, datetime) and current > now else now
        return base + timedelta(days=days)

    async def activate(self, repo: Any, telegram_id: int, days: int, source: str, payment: dict[str, Any] | None = None) -> datetime:
        user = await repo.upsert_user({"telegram_id": telegram_id})
        expiry = self.new_expiry(user, days)
        users = getattr(repo, "collections", {}).get("users")
        if users is not None:
            user["premium_until"] = expiry
        else:
            await repo.db.users.update_one({"telegram_id": telegram_id}, {"$set": {"premium_until": expiry}})
        if payment is not None:
            payments = getattr(repo, "collections", {}).get("payments")
            payload = {"telegram_id": telegram_id, "days": days, "source": source, "premium_until": expiry, **payment}
            if payments is not None:
                payments.append(payload)
            else:
                await repo.db.payments.insert_one(payload)
        await repo.log("premium_changed", {"telegram_id": telegram_id, "days": days, "source": source})
        return expiry

