import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db_function import turso_sync

SCHEMA = [
    "CREATE TABLE user (id TEXT PRIMARY KEY, username TEXT, latest_tweet TEXT, client_used TEXT, enabled INTEGER DEFAULT 1)",
    "CREATE TABLE channel (id TEXT PRIMARY KEY, server_id TEXT)",
    "CREATE TABLE notification (user_id TEXT, channel_id TEXT, role_id TEXT, enabled INTEGER DEFAULT 1, FOREIGN KEY (user_id) REFERENCES user (id), FOREIGN KEY (channel_id) REFERENCES channel (id), PRIMARY KEY(user_id, channel_id))",
]


def make_db(path, with_rows=True):
    conn = sqlite3.connect(path)
    for sql in SCHEMA:
        conn.execute(sql)
    if with_rows:
        conn.execute("INSERT INTO user VALUES ('1', 'alice', '2026-01-01 00:00:00', 'main', 1)")
        conn.execute("INSERT INTO user VALUES ('2', 'bob', '2026-01-01 00:00:00', 'main', 1)")
        conn.execute("INSERT INTO channel VALUES ('10', '99')")
        conn.execute("INSERT INTO notification VALUES ('1', '10', '', 1)")
    conn.commit()
    conn.close()


def rows(path, table):
    conn = sqlite3.connect(path)
    try:
        return sorted(conn.execute(f'SELECT * FROM {table}').fetchall())
    finally:
        conn.close()


@pytest.fixture
def env(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    data.mkdir()
    remote = tmp_path / 'turso.db'
    monkeypatch.setenv('DATA_PATH', str(data))
    monkeypatch.setenv('TURSO_DB_URL', f'file:{remote}')
    monkeypatch.setenv('TURSO_AUTH_TOKEN', 'x')
    monkeypatch.setattr(turso_sync, '_state', {'ready': False, 'attempted': False, 'baseline': {}, 'task': None})
    return str(data / 'tracked_accounts.db'), str(remote)


def test_disabled_without_env(monkeypatch):
    for key in list(os.environ):
        if 'TURSO' in key.upper():
            monkeypatch.delenv(key)
    assert not turso_sync.is_enabled()


def test_env_name_variants_and_libsql_scheme(monkeypatch):
    for key in list(os.environ):
        if 'TURSO' in key.upper():
            monkeypatch.delenv(key)
    monkeypatch.setenv('TURSODBURL', 'libsql://db-org.turso.io')
    monkeypatch.setenv('TURSOAUTHTOKEN', 'tok')
    assert turso_sync.get_config() == ('https://db-org.turso.io', 'tok')


async def test_first_run_uploads_local_db(env):
    local, remote = env
    make_db(local)
    assert await turso_sync.restore()
    assert rows(remote, 'user') == rows(local, 'user')
    assert rows(remote, 'notification') == [('1', '10', '', 1)]


async def test_restore_replaces_wiped_local_db(env):
    local, remote = env
    make_db(remote)                      # Turso already holds data
    assert await turso_sync.restore()    # local file doesn't exist (Render wiped it)
    assert rows(local, 'user') == rows(remote, 'user')
    assert rows(local, 'channel') == [('10', '99')]


async def test_turso_wins_over_stale_local(env):
    local, remote = env
    make_db(remote)
    make_db(local)
    sqlite3.connect(local).execute("INSERT INTO user VALUES ('3', 'stale', '', 'main', 1)").connection.commit()
    await turso_sync.restore()
    assert [r[1] for r in rows(local, 'user')] == ['alice', 'bob']


async def test_push_sends_inserts_updates_deletes(env):
    local, remote = env
    make_db(local)
    await turso_sync.restore()

    conn = sqlite3.connect(local)
    conn.execute("UPDATE user SET latest_tweet = 'NEW' WHERE id = '1'")
    conn.execute("INSERT INTO user VALUES ('3', 'carol', '', 'main', 1)")
    conn.execute("DELETE FROM notification WHERE user_id = '1'")
    conn.execute("DELETE FROM user WHERE id = '2'")
    conn.commit()
    conn.close()

    assert await turso_sync.push_now()
    assert rows(remote, 'user') == rows(local, 'user')
    assert rows(remote, 'notification') == []


async def test_push_creates_tables_when_both_sides_empty(env):
    local, remote = env
    make_db(local, with_rows=False)
    await turso_sync.restore()
    conn = sqlite3.connect(local)
    conn.execute("INSERT INTO channel VALUES ('5', '6')")
    conn.commit()
    conn.close()
    assert await turso_sync.push_now()
    assert rows(remote, 'channel') == [('5', '6')]


async def test_unreachable_turso_never_pushes(env, monkeypatch):
    local, _ = env
    make_db(local)

    def boom():
        raise RuntimeError('network down')

    async def no_sleep(_):
        pass

    monkeypatch.setattr(turso_sync, '_create_client', boom)
    monkeypatch.setattr(turso_sync.asyncio, 'sleep', no_sleep)
    assert not await turso_sync.restore()
    assert not await turso_sync.push_now()


ROLE_SCHEMA = "CREATE TABLE allowed_roles (guild_id INTEGER NOT NULL, role_id INTEGER NOT NULL, PRIMARY KEY (guild_id, role_id))"


def make_roles_db(path, pairs):
    conn = sqlite3.connect(path)
    conn.execute(ROLE_SCHEMA)
    conn.executemany('INSERT INTO allowed_roles VALUES (?, ?)', pairs)
    conn.commit()
    conn.close()


async def test_roles_uploaded_then_restored_after_wipe(env):
    local, remote = env
    roles = os.path.join(os.path.dirname(local), 'role_access.db')
    make_db(local)
    make_roles_db(roles, [(1, 100), (1, 200)])
    await turso_sync.restore()
    assert rows(remote, 'allowed_roles') == [(1, 100), (1, 200)]

    # Render wipes the disk, bot restarts
    os.remove(local)
    os.remove(roles)
    turso_sync._state.update(ready=False, attempted=False, baseline={})
    await turso_sync.restore()
    assert rows(roles, 'allowed_roles') == [(1, 100), (1, 200)]
    assert len(rows(local, 'user')) == 2


async def test_role_changes_are_pushed(env):
    local, remote = env
    roles = os.path.join(os.path.dirname(local), 'role_access.db')
    make_db(local)
    await turso_sync.restore()          # role_access.db doesn't exist yet (no /access used)

    make_roles_db(roles, [(1, 100)])    # created lazily by role_check.py
    assert await turso_sync.push_now()
    assert rows(remote, 'allowed_roles') == [(1, 100)]

    conn = sqlite3.connect(roles)
    conn.execute('DELETE FROM allowed_roles WHERE role_id = 100')
    conn.execute('INSERT INTO allowed_roles VALUES (2, 300)')
    conn.commit()
    conn.close()
    assert await turso_sync.push_now()
    assert rows(remote, 'allowed_roles') == [(2, 300)]


async def test_allowed_users_table_is_synced(env):
    local, remote = env
    roles = os.path.join(os.path.dirname(local), 'role_access.db')
    make_db(local)
    await turso_sync.restore()
    conn = sqlite3.connect(roles)
    conn.execute(ROLE_SCHEMA)
    conn.execute("CREATE TABLE allowed_users (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY (guild_id, user_id))")
    conn.execute("INSERT INTO allowed_users VALUES (1, 77)")
    conn.commit()
    conn.close()
    assert await turso_sync.push_now()
    assert rows(remote, 'allowed_users') == [(1, 77)]
    os.remove(roles)
    turso_sync._state.update(ready=False, attempted=False, baseline={})
    await turso_sync.restore()
    assert rows(roles, 'allowed_users') == [(1, 77)]
