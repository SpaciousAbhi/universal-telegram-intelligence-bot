from __future__ import annotations

from app.models import ReportContext


class ComparisonService:
    def compare(self, left: ReportContext, right: ReportContext) -> dict[str, object]:
        left_fields = self._flatten(left)
        right_fields = self._flatten(right)
        keys = sorted(set(left_fields) | set(right_fields))
        same = []
        different = []
        for key in keys:
            if left_fields.get(key) == right_fields.get(key):
                same.append(key)
            else:
                different.append({"field": key, "left": left_fields.get(key), "right": right_fields.get(key)})
        return {
            "left_kind": left.kind.value,
            "right_kind": right.kind.value,
            "same_fields": same,
            "different_fields": different,
            "same_sender": left.owner_user_id is not None and left.owner_user_id == right.owner_user_id,
            "same_chat": left.chat_id is not None and left.chat_id == right.chat_id,
            "same_message": left.message_id is not None and left.message_id == right.message_id,
        }

    def _flatten(self, report: ReportContext) -> dict[str, str]:
        return {
            f"{section.title}:{field.label}": field.display_value()
            for section in report.sections
            for field in section.fields
        }

