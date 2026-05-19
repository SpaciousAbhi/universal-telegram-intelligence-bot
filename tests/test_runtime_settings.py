from __future__ import annotations

import pytest

from app.repositories.memory import MemoryRepository
from app.services.settings import RuntimeSettingsService


@pytest.mark.asyncio
async def test_runtime_settings_use_defaults_until_admin_sets_values() -> None:
    repo = MemoryRepository()
    service = RuntimeSettingsService()

    assert await service.support_url(repo, "https://t.me/support") == "https://t.me/support"
    assert await service.log_channel_id(repo) is None

    await service.set_support_url(repo, "https://t.me/my_support", 1)
    await service.set_log_channel_id(repo, "-1001234567890", 1)

    assert await service.support_url(repo, "https://t.me/support") == "https://t.me/my_support"
    assert await service.log_channel_id(repo) == -1001234567890


@pytest.mark.asyncio
async def test_support_url_validation_keeps_admin_input_clean() -> None:
    repo = MemoryRepository()
    service = RuntimeSettingsService()

    with pytest.raises(ValueError):
        await service.set_support_url(repo, "https://example.com/help", 1)

