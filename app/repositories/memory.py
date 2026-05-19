from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .mongo import COLLECTIONS


class MemoryRepository:
    """Small test double with the subset of MongoRepository used by services."""

    def __init__(self) -> None:
        self.collections: dict[str, list[dict[str, Any]]] = {name: [] for name in COLLECTIONS}

    async def upsert_user(self, user: dict[str, Any]) -> dict[str, Any]:
        existing = next((u for u in self.collections["users"] if u["telegram_id"] == user["telegram_id"]), None)
        if existing:
            existing.update(user)
            existing["last_active_at"] = user.get("last_active_at") or datetime.now(timezone.utc)
            return existing
        row = {**user, "first_seen_at": user.get("last_active_at") or datetime.now(timezone.utc), "total_reports": 0}
        self.collections["users"].append(row)
        return row

    async def increment_user_reports(self, telegram_id: int, report_type: str) -> None:
        user = next((u for u in self.collections["users"] if u["telegram_id"] == telegram_id), None)
        if not user:
            user = {"telegram_id": telegram_id, "total_reports": 0, "report_counts": defaultdict(int)}
            self.collections["users"].append(user)
        user["total_reports"] = user.get("total_reports", 0) + 1
        counts = user.setdefault("report_counts", {})
        counts[report_type] = counts.get(report_type, 0) + 1

    async def insert_report(self, report: dict[str, Any], raw: dict[str, Any]) -> str:
        report_id = uuid4().hex
        self.collections["reports"].append({"_id": report_id, **report})
        self.collections["raw_reports"].append({"report_id": report_id, **raw})
        return report_id

    async def get_report(self, report_id: str) -> dict[str, Any] | None:
        return next((r for r in self.collections["reports"] if r.get("_id") == report_id), None)

    async def get_raw_report(self, report_id: str) -> dict[str, Any] | None:
        return next((r for r in self.collections["raw_reports"] if r.get("report_id") == report_id), None)

    async def save_report(self, owner_user_id: int, report_id: str, name: str | None = None) -> None:
        self.collections["saved_reports"].append(
            {"owner_user_id": owner_user_id, "report_id": report_id, "name": name or f"Report {report_id[-6:]}"}
        )

    async def saved_reports(self, owner_user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        rows = [r for r in self.collections["saved_reports"] if r.get("owner_user_id") == owner_user_id]
        return rows[:limit]

    async def is_banned(self, telegram_id: int) -> bool:
        return any(b["telegram_id"] == telegram_id and b.get("active") for b in self.collections["bans"])

    async def set_ban(self, telegram_id: int, active: bool, reason: str | None = None) -> None:
        self.collections["bans"].append({"telegram_id": telegram_id, "active": active, "reason": reason})

    async def stats(self) -> dict[str, int]:
        return {
            "total_users": len(self.collections["users"]),
            "premium_users": sum(1 for u in self.collections["users"] if u.get("premium_until")),
            "banned_users": sum(1 for b in self.collections["bans"] if b.get("active")),
            "total_reports": len(self.collections["reports"]),
            "error_count": len(self.collections["errors"]),
            "payment_stats": len(self.collections["payments"]),
            "referral_stats": len(self.collections["referrals"]),
            "broadcast_stats": len(self.collections["broadcasts"]),
        }

    async def active_force_sub_channels(self) -> list[dict[str, Any]]:
        return [c for c in self.collections["force_sub_channels"] if c.get("active")]

    async def log(self, event: str, payload: dict[str, Any]) -> None:
        self.collections["logs"].append({"event": event, "payload": payload})

    async def log_error(self, code: str, payload: dict[str, Any]) -> None:
        self.collections["errors"].append({"code": code, "payload": payload})

    async def get_setting(self, key: str, default: Any = None) -> Any:
        row = next((s for s in self.collections["settings"] if s.get("key") == key), None)
        return row.get("value") if row else default

    async def set_setting(self, key: str, value: Any, updated_by: int | None = None) -> None:
        existing = next((s for s in self.collections["settings"] if s.get("key") == key), None)
        payload = {"key": key, "value": value, "updated_by": updated_by}
        if existing:
            existing.update(payload)
        else:
            self.collections["settings"].append(payload)
