from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId


COLLECTIONS = [
    "users",
    "reports",
    "raw_reports",
    "saved_reports",
    "payments",
    "referrals",
    "bans",
    "broadcasts",
    "logs",
    "errors",
    "settings",
    "force_sub_channels",
    "file_vault",
    "compare_sessions",
]


class MongoRepository:
    def __init__(self, uri: str, db_name: str) -> None:
        self.client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=7000)
        self.db: AsyncIOMotorDatabase = self.client[db_name]

    async def ping(self) -> None:
        await self.client.admin.command("ping")

    async def close(self) -> None:
        self.client.close()

    async def ensure_indexes(self) -> None:
        await self.db.users.create_index("telegram_id", unique=True)
        await self.db.users.create_index("last_active_at")
        await self.db.reports.create_index([("owner_user_id", 1), ("created_at", -1)])
        await self.db.raw_reports.create_index("report_id", unique=True)
        await self.db.saved_reports.create_index([("owner_user_id", 1), ("name", 1)])
        await self.db.payments.create_index("telegram_payment_charge_id", unique=True, sparse=True)
        await self.db.referrals.create_index("referrer_id")
        await self.db.bans.create_index("telegram_id", unique=True)
        await self.db.force_sub_channels.create_index("chat_id", unique=True)
        await self.db.file_vault.create_index([("owner_user_id", 1), ("unique_file_id", 1)])
        await self.db.compare_sessions.create_index([("owner_user_id", 1), ("created_at", -1)])

    async def upsert_user(self, user: dict[str, Any]) -> dict[str, Any]:
        now = user.get("last_active_at") or datetime.utcnow()
        telegram_id = user["telegram_id"]
        update = {
            "$set": {**user, "last_active_at": now},
            "$setOnInsert": {"first_seen_at": now, "total_reports": 0},
        }
        await self.db.users.update_one({"telegram_id": telegram_id}, update, upsert=True)
        return await self.db.users.find_one({"telegram_id": telegram_id}) or user

    async def increment_user_reports(self, telegram_id: int, report_type: str) -> None:
        await self.db.users.update_one(
            {"telegram_id": telegram_id},
            {"$inc": {"total_reports": 1, f"report_counts.{report_type}": 1}},
            upsert=True,
        )

    async def insert_report(self, report: dict[str, Any], raw: dict[str, Any]) -> str:
        inserted = await self.db.reports.insert_one(report)
        report_id = str(inserted.inserted_id)
        await self.db.raw_reports.insert_one({"report_id": report_id, **raw})
        return report_id

    async def get_report(self, report_id: str) -> dict[str, Any] | None:
        try:
            query: dict[str, Any] = {"_id": ObjectId(report_id)}
        except Exception:
            query = {"_id": report_id}
        return await self.db.reports.find_one(query)

    async def get_raw_report(self, report_id: str) -> dict[str, Any] | None:
        return await self.db.raw_reports.find_one({"report_id": report_id})

    async def save_report(self, owner_user_id: int, report_id: str, name: str | None = None) -> None:
        await self.db.saved_reports.update_one(
            {"owner_user_id": owner_user_id, "report_id": report_id},
            {
                "$set": {
                    "owner_user_id": owner_user_id,
                    "report_id": report_id,
                    "name": name or f"Report {report_id[-6:]}",
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

    async def saved_reports(self, owner_user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        return [
            doc
            async for doc in self.db.saved_reports.find({"owner_user_id": owner_user_id}).sort("updated_at", -1).limit(limit)
        ]

    async def is_banned(self, telegram_id: int) -> bool:
        return await self.db.bans.find_one({"telegram_id": telegram_id, "active": True}) is not None

    async def set_ban(self, telegram_id: int, active: bool, reason: str | None = None) -> None:
        await self.db.bans.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"telegram_id": telegram_id, "active": active, "reason": reason, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    async def stats(self) -> dict[str, int]:
        users = await self.db.users.count_documents({})
        premium = await self.db.users.count_documents({"premium_until": {"$ne": None}})
        banned = await self.db.bans.count_documents({"active": True})
        reports = await self.db.reports.count_documents({})
        errors = await self.db.errors.count_documents({})
        payments = await self.db.payments.count_documents({})
        referrals = await self.db.referrals.count_documents({})
        broadcasts = await self.db.broadcasts.count_documents({})
        return {
            "total_users": users,
            "premium_users": premium,
            "banned_users": banned,
            "total_reports": reports,
            "error_count": errors,
            "payment_stats": payments,
            "referral_stats": referrals,
            "broadcast_stats": broadcasts,
        }

    async def export_collection(self, name: str) -> list[dict[str, Any]]:
        if name not in COLLECTIONS:
            raise ValueError(f"unknown collection: {name}")
        return [doc async for doc in self.db[name].find({})]

    async def log(self, event: str, payload: dict[str, Any]) -> None:
        await self.db.logs.insert_one({"event": event, "payload": payload, "created_at": datetime.utcnow()})

    async def log_error(self, code: str, payload: dict[str, Any]) -> None:
        await self.db.errors.insert_one({"code": code, "payload": payload, "created_at": datetime.utcnow()})

    async def active_force_sub_channels(self) -> list[dict[str, Any]]:
        return [doc async for doc in self.db.force_sub_channels.find({"active": True})]

    async def iter_users(self, filter_query: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        async for user in self.db.users.find(filter_query or {}):
            yield user
