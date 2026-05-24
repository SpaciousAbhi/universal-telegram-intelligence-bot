from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError


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
    "join_requests",
    "force_sub_attempts",
]


class MongoStartupError(RuntimeError):
    pass


class MongoRepository:
    def __init__(self, uri: str, db_name: str) -> None:
        kwargs: dict[str, Any] = {
            "serverSelectionTimeoutMS": 15000,
            "connectTimeoutMS": 20000,
            "socketTimeoutMS": 20000,
            "appname": "universal-telegram-intelligence-bot",
        }
        if uri.startswith("mongodb+srv://"):
            kwargs["tls"] = True
        self.client = AsyncIOMotorClient(uri, **kwargs)
        self.db: AsyncIOMotorDatabase = self.client[db_name]

    async def ping(self) -> None:
        try:
            await self.client.admin.command("ping")
        except (ServerSelectionTimeoutError, ConfigurationError, OperationFailure) as exc:
            raise MongoStartupError(
                "MongoDB connection failed. Check Heroku MONGO_URI/MONGO_DB_URL, Atlas Database Access credentials, "
                "and Atlas Network Access. For Heroku without static outbound IPs, add 0.0.0.0/0 to Atlas Network "
                "Access or use a static-egress add-on. If your Mongo password contains @, :, /, ?, #, &, or %, "
                "URL-encode it in the connection string. Original error: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

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
        await self.db.join_requests.create_index([("user_id", 1), ("chat_id", 1)], unique=True)
        await self.db.force_sub_attempts.create_index([("user_id", 1), ("timestamp", -1)])

    async def upsert_user(self, user: dict[str, Any]) -> dict[str, Any]:
        now = user.get("last_active_at") or datetime.utcnow()
        telegram_id = user["telegram_id"]
        update = {
            "$set": {**user, "last_active_at": now},
            "$setOnInsert": {"first_seen_at": now, "total_reports": 0},
        }
        await self.db.users.update_one({"telegram_id": telegram_id}, update, upsert=True)
        return await self.db.users.find_one({"telegram_id": telegram_id}) or user

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        return await self.db.users.find_one({"telegram_id": user_id})

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

    async def get_setting(self, key: str, default: Any = None) -> Any:
        row = await self.db.settings.find_one({"key": key})
        return row.get("value") if row else default

    async def set_setting(self, key: str, value: Any, updated_by: int | None = None) -> None:
        await self.db.settings.update_one(
            {"key": key},
            {"$set": {"key": key, "value": value, "updated_by": updated_by, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    async def active_force_sub_channels(self) -> list[dict[str, Any]]:
        return [doc async for doc in self.db.force_sub_channels.find({"active": True})]

    async def iter_users(self, filter_query: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        async for user in self.db.users.find(filter_query or {}):
            yield user

    async def get_force_sub_settings(self) -> dict[str, Any]:
        doc = await self.db.settings.find_one({"key": "force_sub_global_settings"})
        defaults = {
            "enabled": False,
            "message_template": (
                "🔒 <b>Access Locked</b>\n\n"
                "Hello {first_name}, to use this bot, please join all required channels below.\n\n"
                "After joining, tap the verification button to unlock access."
            ),
            "button_text": "✅ I Joined / Verify",
            "media_file_id": None,
            "media_type": None,
            "admin_bypass": True,
            "bypass_users": [],
            "check_mode": "all",  # "start", "command", "all"
            "recheck_mode": "every_time",  # "every_time", "once", "time_limit"
            "recheck_ttl_seconds": 86400,
            "leave_behavior": "block_again",  # "block_again", "ignore"
        }
        if doc and "value" in doc:
            return {**defaults, **doc["value"]}
        return defaults

    async def set_force_sub_settings(self, settings: dict[str, Any], updated_by: int | None = None) -> None:
        await self.db.settings.update_one(
            {"key": "force_sub_global_settings"},
            {"$set": {"key": "force_sub_global_settings", "value": settings, "updated_by": updated_by, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    async def add_force_sub_channel(self, channel: dict[str, Any]) -> None:
        chat_id = channel["chat_id"]
        channel["updated_at"] = datetime.utcnow()
        if "created_at" not in channel:
            channel["created_at"] = datetime.utcnow()
        await self.db.force_sub_channels.update_one(
            {"chat_id": chat_id},
            {"$set": channel},
            upsert=True,
        )

    async def remove_force_sub_channel(self, chat_id: int | str) -> None:
        try:
            chat_id = int(chat_id)
        except ValueError:
            pass
        await self.db.force_sub_channels.delete_one({"chat_id": chat_id})

    async def get_force_sub_channels(self) -> list[dict[str, Any]]:
        return [doc async for doc in self.db.force_sub_channels.find({})]

    async def get_force_sub_channel(self, chat_id: int | str) -> dict[str, Any] | None:
        try:
            chat_id = int(chat_id)
        except ValueError:
            pass
        return await self.db.force_sub_channels.find_one({"chat_id": chat_id})

    async def log_force_sub_attempt(self, user_id: int, chat_id: int | str, status: str, details: str = "") -> None:
        try:
            chat_id = int(chat_id)
        except ValueError:
            pass
        await self.db.force_sub_attempts.insert_one({
            "user_id": user_id,
            "chat_id": chat_id,
            "status": status,
            "details": details,
            "timestamp": datetime.utcnow()
        })

    async def get_force_sub_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        return [doc async for doc in self.db.force_sub_attempts.find({}).sort("timestamp", -1).limit(limit)]

    async def record_join_request(self, user_id: int, chat_id: int, status: str) -> None:
        await self.db.join_requests.update_one(
            {"user_id": user_id, "chat_id": chat_id},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    async def get_join_request(self, user_id: int, chat_id: int) -> dict[str, Any] | None:
        return await self.db.join_requests.find_one({"user_id": user_id, "chat_id": chat_id})

    async def update_user_force_sub_status(self, user_id: int, verified: bool, bypass: bool = False) -> None:
        await self.db.users.update_one(
            {"telegram_id": user_id},
            {
                "$set": {
                    "fs_verified": verified,
                    "fs_last_verified_at": datetime.utcnow() if verified else None,
                    "fs_bypass": bypass,
                }
            },
            upsert=True,
        )

    async def get_force_sub_stats(self) -> dict[str, Any]:
        active_chats = await self.db.force_sub_channels.count_documents({"active": True})
        broken_chats = await self.db.force_sub_channels.count_documents({"active": True, "bot_status": {"$ne": "ok"}})
        
        total_verified = await self.db.users.count_documents({"fs_verified": True})
        total_blocked = await self.db.users.count_documents({"fs_verified": {"$ne": True}, "fs_bypass": {"$ne": True}})
        
        total_attempts = await self.db.force_sub_attempts.count_documents({})
        failed_attempts = await self.db.force_sub_attempts.count_documents({"status": "failed"})
        
        pipeline = [
            {"$match": {"status": "failed"}},
            {"$group": {"_id": "$chat_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 1}
        ]
        most_missed_chat_id = None
        most_missed_count = 0
        async for r in self.db.force_sub_attempts.aggregate(pipeline):
            most_missed_chat_id = r["_id"]
            most_missed_count = r["count"]
            
        most_missed_title = "None"
        if most_missed_chat_id is not None:
            ch = await self.get_force_sub_channel(most_missed_chat_id)
            if ch:
                most_missed_title = f"{ch.get('title', ch.get('chat_id'))} ({most_missed_count} misses)"
            else:
                most_missed_title = f"ID: {most_missed_chat_id} ({most_missed_count} misses)"
                
        now = datetime.utcnow()
        from datetime import datetime as dt_type, timedelta
        today_start = dt_type(now.year, now.month, now.day)
        week_start = today_start - timedelta(days=now.weekday())
        
        verified_today = await self.db.users.count_documents({"fs_verified": True, "fs_last_verified_at": {"$gte": today_start}})
        verified_week = await self.db.users.count_documents({"fs_verified": True, "fs_last_verified_at": {"$gte": week_start}})
        
        return {
            "total_blocked": total_blocked,
            "total_verified": total_verified,
            "total_failed_attempts": failed_attempts,
            "total_attempts": total_attempts,
            "most_missed_channel": most_missed_title,
            "verified_today": verified_today,
            "verified_week": verified_week,
            "active_chats": active_chats,
            "broken_chats": broken_chats,
        }
