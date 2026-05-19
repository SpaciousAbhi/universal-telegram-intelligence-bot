from __future__ import annotations

from typing import Any


class FileVaultService:
    async def save_file(self, repo: Any, owner_user_id: int, file_doc: dict[str, Any]) -> None:
        payload = {"owner_user_id": owner_user_id, **file_doc}
        vault = getattr(repo, "collections", {}).get("file_vault")
        if vault is not None:
            vault.append(payload)
        else:
            await repo.db.file_vault.update_one(
                {"owner_user_id": owner_user_id, "unique_file_id": file_doc.get("unique_file_id")},
                {"$set": payload},
                upsert=True,
            )
        await repo.log("file_saved", {"owner_user_id": owner_user_id, "unique_file_id": file_doc.get("unique_file_id")})

    async def search(self, repo: Any, owner_user_id: int, query: str) -> list[dict[str, Any]]:
        vault = getattr(repo, "collections", {}).get("file_vault")
        if vault is not None:
            return [row for row in vault if row.get("owner_user_id") == owner_user_id and query.lower() in str(row).lower()]
        return [
            row
            async for row in repo.db.file_vault.find(
                {"owner_user_id": owner_user_id, "$text": {"$search": query}}
            )
        ]

