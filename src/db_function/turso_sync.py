"""
src/db_function/turso_sync.py - keep tracked_accounts.db and role_access.db backed up in Turso.

Two local files are covered: tracked_accounts.db and role_access.db (the /access
roles). They share one Turso database; their table names don't overlap.

Render's free tier has an ephemeral disk: every restart or redeploy wipes
./data. The bot keeps working on its local SQLite file (so none of the existing
queries change), and this module makes Turso the durable copy:

  * on startup  -> restore(): pulls the database from Turso into the local file.
                   If Turso is still empty, the local file is uploaded instead
                   (first-time migration).
  * while running -> a background task pushes only the rows that changed to Turso.
  * on shutdown -> one last push.

Environment variables (set them in Render). Several spellings are accepted:
  TURSO_DATABASE_URL  (or TURSO_DB_URL / TURSODBURL)    e.g. libsql://name-org.turso.io
  TURSO_AUTH_TOKEN    (or TURSOAUTHTOKEN)
  TURSO_SYNC_INTERVAL optional, seconds between pushes (default 15)

If the URL or token is missing, everything here is a no-op and the bot behaves
exactly as before.
"""

import asyncio
import os
import re
import sqlite3

from src.log import setup_logger

log = setup_logger(__name__)

_URL_KEYS = {'TURSODATABASEURL', 'TURSODBURL'}
_TOKEN_KEYS = {'TURSOAUTHTOKEN'}
_BATCH_SIZE = 400

# Tables that live in role_access.db; every other table belongs to tracked_accounts.db
ROLE_TABLES = {'allowed_roles', 'allowed_users'}
_FILES = [
    ('tracked_accounts.db', lambda name: name not in ROLE_TABLES),
    ('role_access.db', lambda name: name in ROLE_TABLES),
]

_state = {
    'ready': False,        # restore finished OK, pushing is allowed
    'attempted': False,    # restore() already ran in this process
    'baseline': {},        # {filename: {table: {key: row}}} as last known to be in Turso
    'task': None,
}


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def _find_env(candidates: set[str]) -> str | None:
    for key, value in os.environ.items():
        if key.upper().replace('_', '') in candidates and value.strip():
            return value.strip()
    return None


def get_config() -> tuple[str, str] | None:
    url = _find_env(_URL_KEYS)
    token = _find_env(_TOKEN_KEYS)
    if not url or not token:
        return None
    # libsql:// would open a websocket; plain HTTPS is more reliable on Render.
    if url.startswith('libsql://'):
        url = 'https://' + url[len('libsql://'):]
    return url, token


def is_enabled() -> bool:
    return get_config() is not None


def _local_path(filename: str) -> str:
    return os.path.join(os.getenv('DATA_PATH'), filename)


def _create_client():
    import libsql_client
    url, token = get_config()
    if url.startswith('file:'):  # used by the tests
        return libsql_client.create_client(url)
    return libsql_client.create_client(url, auth_token=token)


# --------------------------------------------------------------------------
# Local helpers (sqlite3, run in a worker thread)
# --------------------------------------------------------------------------

def _is_internal(name: str) -> bool:
    return name.startswith(('sqlite_', '_', 'libsql_'))


def _local_schema(path: str) -> list[tuple[str, str]]:
    if not os.path.exists(path):
        return []
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL").fetchall()
    return [(n, s) for n, s in rows if not _is_internal(n)]


def _local_column_info(path: str, table: str) -> list[tuple]:
    with sqlite3.connect(path) as conn:
        return conn.execute(f'PRAGMA table_info("{table}")').fetchall()


async def _ensure_remote_columns(client, path: str, belongs) -> None:
    """Apply additive local column migrations to existing remote tables."""
    local_tables = await asyncio.to_thread(_local_schema, path)
    remote_tables = {
        name for name, _ in await _remote_schema(client, belongs)
    }

    for table, _ in local_tables:
        if table not in remote_tables:
            continue

        # SELECT ... LIMIT 0 returns the remote column names without reading rows.
        remote_info = await client.execute(f'SELECT * FROM "{table}" LIMIT 0')
        remote_columns = set(remote_info.columns)
        local_columns = await asyncio.to_thread(_local_column_info, path, table)

        for column in local_columns:
            # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
            _, name, column_type, not_null, default_value, primary_key = column
            if name in remote_columns:
                continue

            definition = f'"{name}" {column_type or "TEXT"}'
            if default_value is not None:
                definition += f' DEFAULT {default_value}'
            if not_null:
                definition += ' NOT NULL'
            if primary_key:
                log.warning(
                    f'cannot add primary-key column {name} to remote table {table} automatically'
                )
                continue

            await client.execute(f'ALTER TABLE "{table}" ADD COLUMN {definition}')
            remote_columns.add(name)
            log.info(f'added remote column {table}.{name} to match local schema')


def _table_meta(conn: sqlite3.Connection, table: str) -> tuple[list[str], list[str]]:
    info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    cols = [r[1] for r in info]
    pk = [r[1] for r in sorted((r for r in info if r[5] > 0), key=lambda r: r[5])]
    return cols, pk or cols


def _order_tables(conn: sqlite3.Connection, tables: list[str]) -> list[str]:
    """Parents before children, so foreign keys are never violated."""
    deps = {t: {r[2] for r in conn.execute(f'PRAGMA foreign_key_list("{t}")')} & set(tables) - {t} for t in tables}
    ordered: list[str] = []
    while len(ordered) < len(tables):
        ready = [t for t in tables if t not in ordered and deps[t] <= set(ordered)]
        if not ready:  # cycle, just keep the remaining order
            ready = [t for t in tables if t not in ordered]
        ordered.extend(ready)
    return ordered


def _snapshot_local(path: str) -> dict:
    """{table: {'cols': [...], 'pk': [...], 'rows': {key: row_tuple}}} in FK order."""
    if not os.path.exists(path):
        return {}
    snap = {}
    with sqlite3.connect(path) as conn:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL")]
        names = [n for n in names if not _is_internal(n)]
        for table in _order_tables(conn, names):
            cols, pk = _table_meta(conn, table)
            idx = [cols.index(c) for c in pk]
            rows = {}
            for row in conn.execute(f'SELECT * FROM "{table}"'):
                rows[tuple(row[i] for i in idx)] = tuple(row)
            snap[table] = {'cols': cols, 'pk': pk, 'rows': rows}
    return snap


def _write_local(path: str, schema: list[tuple[str, str]], data: dict[str, tuple[list[str], list[tuple]]]) -> None:
    """Build a fresh sqlite file from Turso data and atomically swap it in."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.restore'
    for suffix in ('', '-journal', '-wal', '-shm'):
        if os.path.exists(tmp + suffix):
            os.remove(tmp + suffix)
    with sqlite3.connect(tmp) as conn:
        for _, sql in schema:
            conn.execute(sql)
        for table, (cols, rows) in data.items():
            if rows:
                marks = ','.join('?' * len(cols))
                col_sql = ','.join(f'"{c}"' for c in cols)
                conn.executemany(f'INSERT INTO "{table}" ({col_sql}) VALUES ({marks})', rows)
        conn.commit()
    conn.close()
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Remote helpers (Turso)
# --------------------------------------------------------------------------

async def _remote_schema(client, belongs) -> list[tuple[str, str]]:
    rs = await client.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL")
    return [(r[0], r[1]) for r in rs.rows if not _is_internal(r[0]) and belongs(r[0])]


async def _remote_count(client, tables: list[str]) -> int:
    total = 0
    for table in tables:
        rs = await client.execute(f'SELECT count(*) FROM "{table}"')
        total += rs.rows[0][0]
    return total


async def _run_batches(client, statements: list[tuple[str, list]]) -> None:
    for i in range(0, len(statements), _BATCH_SIZE):
        await client.batch(statements[i:i + _BATCH_SIZE])


def _create_if_missing(sql: str) -> str:
    return re.sub(r'^\s*CREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS)', 'CREATE TABLE IF NOT EXISTS ', sql, count=1, flags=re.IGNORECASE)


def _diff_statements(snap: dict, baseline: dict) -> tuple[list[tuple[str, list]], dict]:
    """Statements that turn Turso's known state (baseline) into snap."""
    upserts, deletes = [], []
    new_baseline = {}
    for table, info in snap.items():
        old_rows = baseline.get(table, {})
        cols, pk = info['cols'], info['pk']
        col_sql = ','.join(f'"{c}"' for c in cols)
        marks = ','.join('?' * len(cols))
        for key, row in info['rows'].items():
            if old_rows.get(key) != row:
                upserts.append((f'INSERT OR REPLACE INTO "{table}" ({col_sql}) VALUES ({marks})', list(row)))
        where = ' AND '.join(f'"{c}" = ?' for c in pk)
        for key in old_rows.keys() - info['rows'].keys():
            deletes.append((f'DELETE FROM "{table}" WHERE {where}', list(key)))
        new_baseline[table] = dict(info['rows'])
    # children first when deleting, parents first when inserting
    return list(reversed(deletes)) + upserts, new_baseline


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

async def restore() -> bool:
    """Run once at startup, before the bot touches the local databases."""
    if _state['attempted'] or not is_enabled():
        return _state['ready']
    _state['attempted'] = True

    last_error = None
    for attempt in range(1, 4):
        try:
            async with _create_client() as client:
                for filename, belongs in _FILES:
                    await _restore_file(client, filename, belongs)
            _state['ready'] = True
            log.info('turso sync ready')
            return True
        except Exception as e:
            last_error = e
            log.warning(f'turso restore attempt {attempt}/3 failed: {e}')
            await asyncio.sleep(2 * attempt)

    _state['baseline'] = {}
    log.error(f'could not reach turso ({last_error}); running on the local databases only and NOT pushing changes, '
              f'so existing Turso data is not overwritten. Restart the bot once Turso is reachable.')
    return False


async def _restore_file(client, filename: str, belongs) -> None:
    path = _local_path(filename)
    remote_schema = await _remote_schema(client, belongs)
    remote_tables = [n for n, _ in remote_schema]
    remote_rows = await _remote_count(client, remote_tables) if remote_tables else 0
    local_snap = await asyncio.to_thread(_snapshot_local, path)
    local_rows = sum(len(t['rows']) for t in local_snap.values())

    if remote_rows > 0:
        # Turso is the source of truth: rebuild the local file from it.
        data = {}
        for table in remote_tables:
            rs = await client.execute(f'SELECT * FROM "{table}"')
            data[table] = (list(rs.columns), [tuple(r) for r in rs.rows])
        await asyncio.to_thread(_write_local, path, remote_schema, data)
        snap = await asyncio.to_thread(_snapshot_local, path)
        _state['baseline'][filename] = {t: i['rows'] for t, i in snap.items()}
        log.info(f'restored {sum(len(r) for _, r in data.values())} rows from turso into {filename}')
        return

    # Turso has nothing for this file: create its tables and upload whatever exists locally.
    local_schema = await asyncio.to_thread(_local_schema, path)
    if local_schema:
        await _run_batches(client, [(_create_if_missing(sql), []) for _, sql in local_schema])
        statements, _ = _diff_statements(local_snap, {})
        await _run_batches(client, statements)
        _state['baseline'][filename] = {t: i['rows'] for t, i in local_snap.items()}
        log.info(f'turso had no data for {filename}, uploaded the local copy ({local_rows} rows)')
    else:
        _state['baseline'][filename] = {}
        log.info(f'no data for {filename} in turso or locally, nothing to restore')


async def push_now() -> bool:
    """Push rows that changed since the last push. Safe to call at any time."""
    if not _state['ready']:
        return False
    try:
        statements: list[tuple[str, list]] = []
        new_baseline = {}
        for filename, _ in _FILES:
            path = _local_path(filename)
            snap = await asyncio.to_thread(_snapshot_local, path)
            known = _state['baseline'].get(filename, {})
            file_statements, _ = _diff_statements(snap, known)
            for name, sql in await asyncio.to_thread(_local_schema, path):
                if name not in known:  # table created after startup
                    statements.append((_create_if_missing(sql), []))
            statements.extend(file_statements)
            new_baseline[filename] = {t: dict(i['rows']) for t, i in snap.items()}
        if not statements:
            return True
        async with _create_client() as client:
            for filename, belongs in _FILES:
                await _ensure_remote_columns(
                    client,
                    _local_path(filename),
                    belongs
                )
            await _run_batches(client, statements)
        _state['baseline'] = new_baseline
        log.info(f'pushed {len(statements)} change(s) to turso')
        return True
    except Exception as e:
        log.error(f'turso push failed, will retry: {e}')
        return False


async def _push_loop(interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        await push_now()


def start_background_push() -> None:
    """Start the periodic push task (only once, only if restore succeeded)."""
    if not _state['ready'] or (_state['task'] and not _state['task'].done()):
        return
    try:
        interval = max(5.0, float(os.getenv('TURSO_SYNC_INTERVAL', '15')))
    except ValueError:
        interval = 15.0
    _state['task'] = asyncio.get_running_loop().create_task(_push_loop(interval), name='TursoPush')
    log.info(f'turso background push started (every {interval:g}s)')


async def shutdown() -> None:
    task = _state['task']
    if task:
        task.cancel()
    await push_now()
