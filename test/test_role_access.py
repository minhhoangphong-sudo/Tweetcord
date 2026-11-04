import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import discord
import pytest
from discord import app_commands

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import role_check


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_PATH', str(tmp_path))


def get_predicate():
    async def dummy(interaction): ...
    role_check.has_allowed_role()(dummy)
    return dummy.__discord_app_commands_checks__[0]


def make_itn(user_id=1, role_ids=(), admin=False, guild_id=50):
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.roles = [SimpleNamespace(id=r) for r in role_ids]
    member.guild_permissions = SimpleNamespace(administrator=admin)
    return SimpleNamespace(user=member, guild=SimpleNamespace(id=guild_id))


def test_user_storage_add_remove_clear():
    assert role_check.add_allowed_user(50, 7) is True
    assert role_check.add_allowed_user(50, 7) is False
    role_check.add_allowed_role(50, 100)
    assert role_check.get_allowed_users(50) == {7}
    assert role_check.get_allowed_users(51) == set()
    assert role_check.remove_allowed_user(50, 7) is True
    assert role_check.remove_allowed_user(50, 7) is False
    role_check.add_allowed_user(50, 8)
    assert role_check.clear_allowed(50) == 2
    assert role_check.get_allowed_roles(50) == set() and role_check.get_allowed_users(50) == set()


async def test_admin_always_allowed():
    assert await get_predicate()(make_itn(admin=True)) is True


async def test_nobody_configured_blocks_non_admin():
    with pytest.raises(role_check.NotAllowed):
        await get_predicate()(make_itn())


async def test_allowed_role_passes_and_others_blocked():
    role_check.add_allowed_role(50, 100)
    assert await get_predicate()(make_itn(role_ids=[100])) is True
    with pytest.raises(role_check.NotAllowed):
        await get_predicate()(make_itn(role_ids=[999]))


async def test_allowed_user_passes_without_role():
    role_check.add_allowed_user(50, 42)
    assert await get_predicate()(make_itn(user_id=42)) is True
    with pytest.raises(role_check.NotAllowed):
        await get_predicate()(make_itn(user_id=43))


async def test_other_server_not_affected():
    role_check.add_allowed_user(51, 42)
    with pytest.raises(role_check.NotAllowed):
        await get_predicate()(make_itn(user_id=42, guild_id=50))


def get_admin_predicate():
    async def dummy(interaction): ...
    role_check.admin_only()(dummy)
    return dummy.__discord_app_commands_checks__[0]


async def test_superuser_passes_every_check(monkeypatch):
    monkeypatch.setenv('SUPERUSER_IDS', '111, 222')
    itn = make_itn(user_id=222)
    assert await get_predicate()(itn) is True
    assert await get_admin_predicate()(itn) is True
    # works in any server, no role or admin permission needed
    assert await get_predicate()(make_itn(user_id=111, guild_id=999)) is True


async def test_non_superuser_still_blocked(monkeypatch):
    monkeypatch.setenv('SUPERUSER_IDS', '111')
    with pytest.raises(role_check.NotAllowed):
        await get_predicate()(make_itn(user_id=333))
    with pytest.raises(role_check.NotAnAdmin):
        await get_admin_predicate()(make_itn(user_id=333))


def test_bad_superuser_values_ignored(monkeypatch):
    monkeypatch.setenv('SUPERUSER_IDS', '_reixd, abc,,123')
    assert role_check.get_superuser_ids() == {123}
