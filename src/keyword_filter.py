"""
src/keyword_filter.py - keyword filters for notifications.

A filter is a keyword saved for a server, optionally narrowed to one tracked
account and/or one channel. A notification only goes out when no filter applies
to it, or when the tweet contains at least one keyword of the filters that do
apply (case-insensitive, plain text match).

The rules live in the keyword_filter table of tracked_accounts.db, so they are
backed up to Turso by turso_sync along with everything else in that file.
"""

import os
import re

import aiosqlite

from src.db_function.readonly_db import connect_readonly
from src.log import setup_logger

log = setup_logger(__name__)

TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS keyword_filter ("
    " guild_id TEXT NOT NULL,"
    " user_id TEXT NOT NULL DEFAULT '',"      # '' = every tracked account
    " channel_id TEXT NOT NULL DEFAULT '',"   # '' = every channel
    " keyword TEXT NOT NULL,"
    " PRIMARY KEY (guild_id, user_id, channel_id, keyword))"
)

MAX_KEYWORD_LENGTH = 100
MAX_KEYWORDS_PER_COMMAND = 25
MAX_KEYWORDS_PER_SERVER = 200

_SEPARATORS = re.compile(r'[,;\uff0c\uff1b\n]')  # , ; and their full-width versions


def db_path() -> str:
    return os.path.join(os.getenv('DATA_PATH'), 'tracked_accounts.db')


def parse_keywords(raw: str) -> list[str]:
    """Split on commas / semicolons, trim, drop blanks and duplicates (ignoring case)."""
    seen, result = set(), []
    for part in _SEPARATORS.split(raw or ''):
        keyword = part.strip().casefold()
        if keyword and keyword not in seen:
            seen.add(keyword)
            result.append(keyword)
    return result


async def ensure_table() -> None:
    """Create the table in databases made before this feature existed."""
    async with aiosqlite.connect(db_path()) as db:
        await db.execute(TABLE_SQL)
        await db.commit()


async def load_rules(user_id: str) -> list[tuple[str, str, str, str]]:
    """(guild_id, user_id, channel_id, keyword) rows that can apply to this account's tweets."""
    try:
        async with connect_readonly(db_path()) as db:
            async with db.execute(
                "SELECT guild_id, user_id, channel_id, keyword FROM keyword_filter WHERE user_id IN ('', ?)",
                (str(user_id),),
            ) as cursor:
                return [tuple(row) async for row in cursor]
    except aiosqlite.OperationalError as e:
        # Table missing or database busy: never block notifications because of the filter.
        log.warning(f'could not read keyword filters ({e}), posting without filtering')
        return []


def tweet_search_text(tweet) -> str:
    """The tweet's text, plus the text of the tweet it retweets or quotes."""
    parts = [getattr(tweet, 'text', None)]
    for attr in ('retweeted_tweet', 'quoted_tweet'):
        parts.append(getattr(getattr(tweet, attr, None), 'text', None))
    return '\n'.join(p for p in parts if p)


def passes_filter(rules, guild_id, user_id, channel_id, text: str) -> bool:
    """True when the tweet may be posted to this channel."""
    guild_id, user_id, channel_id = str(guild_id), str(user_id), str(channel_id)
    applicable = [
        keyword for g, u, c, keyword in rules
        if g == guild_id and u in ('', user_id) and c in ('', channel_id)
    ]
    if not applicable:
        return True
    haystack = (text or '').casefold()
    return any(keyword in haystack for keyword in applicable)
