import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogs import owner


def get_predicate():
    async def dummy(interaction): ...
    owner.owner_only()(dummy)
    return dummy.__discord_app_commands_checks__[0]


def make_itn(user_id, is_owner=False):
    client = SimpleNamespace(is_owner=AsyncMock(return_value=is_owner))
    return SimpleNamespace(user=SimpleNamespace(id=user_id), client=client)


async def test_bot_owner_allowed():
    assert await get_predicate()(make_itn(1, is_owner=True)) is True


async def test_superuser_allowed(monkeypatch):
    monkeypatch.setenv('SUPERUSER_IDS', '5')
    assert await get_predicate()(make_itn(5)) is True


async def test_everyone_else_blocked(monkeypatch):
    monkeypatch.setenv('SUPERUSER_IDS', '5')
    with pytest.raises(owner.NotOwner):
        await get_predicate()(make_itn(6))


def test_sqlite_header_check():
    assert owner.is_sqlite_file(b'SQLite format 3\x00rest')
    assert not owner.is_sqlite_file(b'not a database')
