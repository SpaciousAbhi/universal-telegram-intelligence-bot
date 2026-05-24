from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.repositories.mongo import MongoRepository


def test_mongo_repository_sets_application_name() -> None:
    repo = MongoRepository("mongodb://localhost:27017", "test")
    try:
        assert repo.client.options.pool_options.appname == "universal-telegram-intelligence-bot"
    finally:
        repo.client.close()


@pytest.mark.asyncio
async def test_mongo_repository_get_user() -> None:
    repo = MongoRepository("mongodb://localhost:27017", "test")
    try:
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {"telegram_id": 12345, "username": "testuser"}
        repo.db = MagicMock()
        repo.db.users = mock_collection

        user = await repo.get_user(12345)
        mock_collection.find_one.assert_called_once_with({"telegram_id": 12345})
        assert user == {"telegram_id": 12345, "username": "testuser"}
    finally:
        repo.client.close()
