from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace as NS

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


def test_renderer_includes_truth_and_unavailable_sections_without_dirty_badges() -> None:
    report = ReportEngine().user_profile(
        NS(id=1, first_name="A", last_name=None, username=None, is_bot=False, language_code=None)
    )

    text = Renderer().report(report)

    assert "👤 User Identity Report" in text
    assert text.count("👤 User Identity Report") == 1
    assert "🧠 What This Means" in text
    assert "⚠️ Unavailable Fields" in text
    assert "User has no username" in text
    assert "❌ Not provided by Telegram API" not in text


def test_renderer_formats_forwarded_media_as_clean_card() -> None:
    caption = "A" * 300
    report = ReportEngine().message_report(
        NS(
            message_id=6,
            date=datetime(2026, 5, 19, 6, 31, tzinfo=timezone.utc),
            text=None,
            caption=caption,
            entities=[],
            caption_entities=[NS(type="hashtag"), NS(type="hashtag"), NS(type="text_link")],
            chat=NS(id=6938449843, title=None, type="private"),
            from_user=NS(id=6938449843, first_name="R04VENOM", last_name=None, username="R04VENOM"),
            sender_chat=None,
            reply_to_message=None,
            forward_origin=NS(
                type="channel",
                chat=NS(id=-1003909579270, title="POSTING || VENOM STONE NETWORK!", username="hellloohelloo"),
                message_id=421,
                date=datetime(2026, 5, 18, 11, 5, tzinfo=timezone.utc),
            ),
            photo=[NS(file_id="file-photo", file_unique_id="unique-photo", file_size=94530, width=1280, height=720)],
        )
    )

    text = Renderer().report(report)

    assert "🔎 Forwarded Media Report" in text
    assert "• Sender ID: <code>6938449843</code>" in text
    assert "• Channel ID: <code>-1003909579270</code>" in text
    assert "• File Size: <code>92.3 KB</code>" in text
    assert "• Resolution: <code>1280 × 720</code>" in text
    assert "📝 Caption Preview" in text
    assert caption not in text
    assert "Full caption is available in Export / Raw Data." in text
    assert "❌ Not provided by Telegram API" not in text


def test_comparison_reports_same_sender_and_differences() -> None:
    engine = ReportEngine()
    left = engine.user_profile(NS(id=1, first_name="A", username="a", is_bot=False))
    right = engine.user_profile(NS(id=1, first_name="B", username="b", is_bot=False))

    result = ComparisonService().compare(left, right)

    assert result["same_sender"] is True
    assert result["different_fields"]


def test_exports_include_human_and_raw_formats() -> None:
    report = ReportEngine().user_profile(NS(id=10, first_name="A", username="a", is_bot=False))
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
    report = ReportEngine().user_profile(NS(id=10, first_name="A", username="a", is_bot=False))
    report_id = await repo.insert_report(ReportEngine().to_document(report), report.raw)

    await repo.save_report(10, report_id, "Identity")
    rows = await repo.saved_reports(10)

    assert rows[0]["name"] == "Identity"
    assert rows[0]["report_id"] == report_id


@pytest.mark.asyncio
async def test_force_sub_only_returns_missing_channels() -> None:
    repo = MemoryRepository()
    await repo.set_force_sub_settings({"enabled": True, "check_mode": "all", "admin_bypass": True}, updated_by=0)
    repo.collections["force_sub_channels"].extend(
        [
            {"chat_id": -1, "title": "Joined", "active": True},
            {"chat_id": -2, "title": "Missing", "active": True},
        ]
    )

    class Bot:
        async def get_chat_member(self, chat_id, user_id):
            return type("Member", (), {"status": "member" if chat_id == -1 else "left"})()

    res = await ForceSubscriptionService().check_user_access(Bot(), repo, 123, None, 0)
    assert res is not None
    missing = res["missing"]

    assert [channel["title"] for channel in missing] == ["Missing"]


def test_broadcast_summary_has_operator_counts() -> None:
    text = BroadcastService().summary(BroadcastStats(total=10, sent=7, failed=1, blocked=1, invalid=1))

    assert "Sent: 7" in text
    assert "Remaining: 0" in text

