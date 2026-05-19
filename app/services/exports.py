from __future__ import annotations

import csv
import io
from typing import Any

from app.models import ReportContext
from app.utils import pretty_json


class ExportService:
    def report_txt(self, report: ReportContext) -> str:
        lines: list[str] = []
        for section in report.sections:
            lines.append(section.title)
            for field in section.fields:
                lines.append(f"{field.label}: {field.display_value()}")
            lines.append("")
        return "\n".join(lines).strip()

    def report_json(self, report: ReportContext) -> str:
        return pretty_json(report.raw)

    def reports_csv(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return ""
        output = io.StringIO()
        fieldnames = sorted({key for row in rows for key in row.keys()})
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

