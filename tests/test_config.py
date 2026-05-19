from __future__ import annotations

from app.config import Settings


def test_settings_accept_common_heroku_aliases() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="123:abc",
        ADMIN_ID="1001",
        MONGO_DB_URL="mongodb+srv://example.mongodb.net/db",
    )

    assert settings.bot_token == "123:abc"
    assert settings.owner_id == 1001
    assert settings.mongo_uri == "mongodb+srv://example.mongodb.net/db"

