import os

import aiosqlite

from src.log import setup_logger
from src.utils import get_utcnow
from src.db_function import turso_sync
from src.keyword_filter import TABLE_SQL as KEYWORD_FILTER_SQL

log = setup_logger(__name__)


async def _ensure_translation_schema(db: aiosqlite.Connection) -> None:
    """Create/migrate per-server translation preferences without deleting existing values."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS server_user_config (
            server_id TEXT,
            user_id TEXT,
            translate TEXT DEFAULT 'en',
            translation_enabled INTEGER DEFAULT NULL,
            PRIMARY KEY(server_id, user_id),
            FOREIGN KEY (user_id) REFERENCES user (id)
        )
    """)

    async with db.execute("PRAGMA table_info(server_user_config)") as cursor:
        columns = {row[1] async for row in cursor}

    if "translate" not in columns:
        await db.execute("ALTER TABLE server_user_config ADD COLUMN translate TEXT DEFAULT 'en'")
    if "translation_enabled" not in columns:
        # NULL means "follow the existing global auto_translation config".
        await db.execute("ALTER TABLE server_user_config ADD COLUMN translation_enabled INTEGER DEFAULT NULL")


async def init_db():
    data_path = os.getenv('DATA_PATH')
    if not os.path.exists(data_path):
        os.makedirs(data_path)

    # Pull the database from Turso first (no-op if Turso isn't configured).
    await turso_sync.restore()

    db_path = os.path.join(data_path, 'tracked_accounts.db')
    db_exists = os.path.exists(db_path)

    async with aiosqlite.connect(db_path) as db:
        if not db_exists:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS user (id TEXT PRIMARY KEY, username TEXT, latest_tweet TEXT, client_used TEXT, enabled INTEGER DEFAULT 1);
                CREATE TABLE IF NOT EXISTS channel (id TEXT PRIMARY KEY, server_id TEXT);
                CREATE TABLE IF NOT EXISTS notification (user_id TEXT, channel_id TEXT, role_id TEXT, enabled INTEGER DEFAULT 1, enable_type TEXT DEFAULT 11, enable_media_type TEXT DEFAULT 11, customized_msg TEXT DEFAULT NULL, FOREIGN KEY (user_id) REFERENCES user (id), FOREIGN KEY (channel_id) REFERENCES channel (id), PRIMARY KEY(user_id, channel_id));
            """)

        await db.execute(KEYWORD_FILTER_SQL)
        await _ensure_translation_schema(db)
        await db.commit()

    if not db_exists:
        log.info('database file not found, a blank database file has been created')
    else:
        log.info('database schema migrations checked')


async def init_latest_tweet_on_startup(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('UPDATE user SET latest_tweet = ?', (get_utcnow(),))
        await db.commit()

    log.info('all latest_tweet timestamps have been updated to current time')
