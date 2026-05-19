from __future__ import annotations

from app.repositories.mongo import MongoRepository


def test_mongo_repository_sets_application_name() -> None:
    repo = MongoRepository("mongodb://localhost:27017", "test")
    try:
        assert repo.client.options.pool_options.appname == "universal-telegram-intelligence-bot"
    finally:
        repo.client.close()
