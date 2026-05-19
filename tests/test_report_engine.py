from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace as NS

from app.models import Availability, ReportKind
from app.services.report_engine import ReportEngine


def test_user_profile_marks_missing_username_and_language() -> None:
    engine = ReportEngine()
    user = NS(id=1001, first_name="Asha", last_name=None, username=None, is_bot=False, language_code=None)

    report = engine.user_profile(user)

    assert report.kind == ReportKind.USER
    flat = {field.label: field for section in report.sections for field in section.fields}
    assert flat["Telegram User ID"].value == 1001
    assert flat["Username"].status == Availability.NOT_PROVIDED
    assert "User has no username" in flat["Username"].reason


def test_forward_report_never_fakes_hidden_source() -> None:
    engine = ReportEngine()
    msg = NS(
        message_id=55,
        date=datetime.now(timezone.utc),
        text="forwarded",
        caption=None,
        entities=[],
        caption_entities=[],
        chat=NS(id=-100, title="Test Group", type="supergroup"),
        from_user=NS(id=77, first_name="Sender", last_name=None, username="sender"),
        sender_chat=None,
        reply_to_message=None,
        forward_origin=NS(type="hidden_user", date=datetime.now(timezone.utc)),
    )

    report = engine.message_report(msg)

    assert report.kind == ReportKind.FORWARD
    source = next(section for section in report.sections if "Source Trace" in section.title)
    result = {field.label: field for field in source.fields}
    assert result["Source trace result"].value == "Original source is hidden by Telegram privacy settings."
    assert result["Original user/channel/group"].status == Availability.HIDDEN


def test_media_report_extracts_file_ids() -> None:
    engine = ReportEngine()
    msg = NS(
        message_id=9,
        date=datetime.now(timezone.utc),
        text=None,
        caption="demo",
        entities=[],
        caption_entities=[],
        chat=NS(id=1, title=None, type="private"),
        from_user=NS(id=88, first_name="Dev", last_name=None, username=None),
        sender_chat=None,
        reply_to_message=None,
        forward_origin=None,
        document=NS(file_id="file-1", file_unique_id="unique-1", file_size=123, mime_type="text/plain"),
    )

    report = engine.message_report(msg)

    assert report.kind == ReportKind.MEDIA
    flat = {field.label: field for section in report.sections for field in section.fields}
    assert flat["File ID"].value == "file-1"
    assert flat["Unique file ID"].value == "unique-1"


def test_report_document_is_mongo_serializable_shape() -> None:
    engine = ReportEngine()
    report = engine.user_profile(NS(id=1001, first_name="Asha", last_name=None, username=None, is_bot=False))

    doc = engine.to_document(report)

    assert doc["kind"] == "user"
    assert doc["sections"][0]["fields"][0]["status"] == "✅ Available"
