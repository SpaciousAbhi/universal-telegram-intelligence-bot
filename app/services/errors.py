from __future__ import annotations

import traceback
from typing import Any
from uuid import uuid4


class ErrorService:
    async def capture(self, repo: Any, exc: BaseException, context: dict[str, Any] | None = None) -> str:
        code = f"ERR-{uuid4().hex[:8].upper()}"
        await repo.log_error(
            code,
            {
                "error": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback.format_exc(),
                "context": context or {},
            },
        )
        return code

