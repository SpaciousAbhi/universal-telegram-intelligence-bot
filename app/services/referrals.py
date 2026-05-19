from __future__ import annotations

from typing import Any

from app.services.premium import PremiumService


class ReferralService:
    def __init__(self, reward_days: int) -> None:
        self.reward_days = reward_days

    def referral_link(self, bot_username: str, user_id: int) -> str:
        return f"https://t.me/{bot_username}?start=ref_{user_id}"

    def parse_start_payload(self, text: str | None) -> int | None:
        if not text or " " not in text:
            return None
        payload = text.split(maxsplit=1)[1]
        if not payload.startswith("ref_"):
            return None
        try:
            return int(payload.removeprefix("ref_"))
        except ValueError:
            return None

    async def register(self, repo: Any, referrer_id: int | None, invited_id: int, premium: PremiumService) -> bool:
        if not referrer_id or referrer_id == invited_id:
            return False
        referrals = getattr(repo, "collections", {}).get("referrals")
        existing = False
        if referrals is not None:
            existing = any(r.get("invited_id") == invited_id for r in referrals)
        else:
            existing = await repo.db.referrals.find_one({"invited_id": invited_id}) is not None
        if existing:
            return False
        payload = {"referrer_id": referrer_id, "invited_id": invited_id, "reward_days": self.reward_days}
        if referrals is not None:
            referrals.append(payload)
        else:
            await repo.db.referrals.insert_one(payload)
        await premium.activate(repo, referrer_id, self.reward_days, "referral_reward")
        await repo.log("referral_reward", payload)
        return True

