from __future__ import annotations

import pytest

from app.models import BroadcastStats
from app.repositories.memory import MemoryRepository
from app.services.broadcast import BroadcastService
from app.services.comparison import ComparisonService
from app.services.exports import ExportService
from app.services.force_sub import ForceSubscriptionService
from app.services.premium import PremiumService
from app.services.report_engine import ReportEngine
from app.ui.renderer import Renderer


def test_renderer_includes_truth_and_limitation_sections() -> None:
    report = ReportEngine().user_profile(
        type("User", (), {"id": 1, "first_name": "A", "last_name": None, "username": None, "is_bot": False})()
    )

    text = Renderer().report(report)

    assert "🧠 What This Means" in text
    assert "🛡 Privacy & Limitations" in text
    assert "User has no username" in text


def test_comparison_reports_same_sender_and_differences() -> None:
    engine = ReportEngine()
    left = engine.user_profile(type("User", (), {"id": 1, "first_name": "A", "username": "a", "is_bot": False})())
    right = engine.user_profile(type("User", (), {"id": 1, "first_name": "B", "username": "b", "is_bot": False})())

    result = ComparisonService().compare(left, right)

    assert result["same_sender"] is True
    assert result["different_fields"]


def test_exports_include_human_and_raw_formats() -> None:
    report = ReportEngine().user_profile(type("User", (), {"id": 10, "first_name": "A", "username": "a", "is_bot": False})())
    exports = ExportService()

    assert "Telegram User ID: 10" in exports.report_txt(report)
    assert '"user"' in exports.report_json(report)
    assert "a,b" in exports.reports_csv([{"a": 1, "b": 2}])


@pytest.mark.asyncio
async def test_premium_activation_extends_user() -> None:
    repo = MemoryRepository()
    service = PremiumService([{"code": "p30", "title": "30 days", "days": 30, "stars": 199}])

    expiry = await service.activate(repo, 100, 30, "test", {"telegram_payment_charge_id": "charge"})

    assert expiry
    assert service.is_premium(repo.collections["users"][0])
    assert repo.collections["payments"][0]["telegram_payment_charge_id"] == "charge"


@pytest.mark.asyncio
async def test_saved_reports_are_premium_storage_records() -> None:
    repo = MemoryRepository()
    report = ReportEngine().user_profile(type("User", (), {"id": 10, "first_name": "A", "username": "a", "is_bot": False})())
    report_id = await repo.insert_report(ReportEngine().to_document(report), report.raw)

    await repo.save_report(10, report_id, "Identity")
    rows = await repo.saved_reports(10)

    assert rows[0]["name"] == "Identity"
    assert rows[0]["report_id"] == report_id


@pytest.mark.asyncio
async def test_force_sub_only_returns_missing_channels() -> None:
    repo = MemoryRepository()
    repo.collections["force_sub_channels"].extend(
        [
            {"chat_id": -1, "title": "Joined", "active": True},
            {"chat_id": -2, "title": "Missing", "active": True},
        ]
    )

    class Bot:
        async def get_chat_member(self, chat_id, user_id):
            return type("Member", (), {"status": "member" if chat_id == -1 else "left"})()

    missing = await ForceSubscriptionService().missing_channels(Bot(), repo, 123)

    assert [channel["title"] for channel in missing] == ["Missing"]


def test_broadcast_summary_has_operator_counts() -> None:
    text = BroadcastService().summary(BroadcastStats(total=10, sent=7, failed=1, blocked=1, invalid=1))

    assert "Sent: 7" in text
    assert "Remaining: 0" in text
