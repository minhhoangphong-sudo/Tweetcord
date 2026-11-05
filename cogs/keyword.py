"""
cogs/keyword.py - keyword filters for notifications.

    /keyword filter add <keywords> [username] [channel]
    /keyword filter remove <keywords> [username] [channel]
    /keyword filter list

<keywords> are separated by a comma or a semicolon, e.g. `release, update; patch`.
Once a filter applies to a notifier, the bot only posts tweets that contain at
least one of its keywords (not case sensitive). With no filters, everything is
posted like before.

Without username and channel, a keyword applies to every notifier on the server.
Adding username and/or channel narrows it to that account and/or that channel.
Same permissions as the other commands: admins and allowed roles.
"""

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from configs.constants import AUTOCOMPLETE_MAX_CHOICES
from core.classes import Cog_Extension
from src.db_function.readonly_db import connect_readonly
from src.keyword_filter import (
    MAX_KEYWORD_LENGTH,
    MAX_KEYWORDS_PER_COMMAND,
    MAX_KEYWORDS_PER_SERVER,
    TABLE_SQL,
    db_path,
    parse_keywords,
)
from src.role_check import has_allowed_role

NO_PING = discord.AllowedMentions.none()
MESSAGE_LIMIT = 1900


def describe_scope(username: str | None, channel_id: str | None) -> str:
    if username and channel_id:
        return f'for **{username}** in <#{channel_id}>'
    if username:
        return f'for **{username}** in every channel'
    if channel_id:
        return f'for every account in <#{channel_id}>'
    return 'for every notifier on this server'


def check_keywords(keywords: list[str]) -> str | None:
    """An error message if the keyword list can't be used, otherwise None."""
    if not keywords:
        return '\u274c Please give at least one keyword, separated by a comma or a semicolon.'
    if len(keywords) > MAX_KEYWORDS_PER_COMMAND:
        return f'\u274c Please use at most {MAX_KEYWORDS_PER_COMMAND} keywords at a time.'
    too_long = [k for k in keywords if len(k) > MAX_KEYWORD_LENGTH]
    if too_long:
        return f'\u274c Keywords can be at most {MAX_KEYWORD_LENGTH} characters long.'
    return None


class Keyword(Cog_Extension):
    keyword_group = app_commands.Group(name='keyword', description='Keyword filters for notifications', guild_only=True)
    filter_group = app_commands.Group(name='filter', description='Only post tweets that contain certain keywords', parent=keyword_group)

    async def _resolve_username(self, db: aiosqlite.Connection, guild_id: int, username: str | None):
        """(user_id, display username), or (None, None) when no username was given. Raises LookupError if not tracked here."""
        if not username:
            return '', None
        async with db.execute(
            'SELECT u.id, u.username FROM user u '
            'JOIN notification n ON n.user_id = u.id '
            'JOIN channel c ON c.id = n.channel_id '
            'WHERE u.username = ? COLLATE NOCASE AND c.server_id = ? LIMIT 1',
            (username.lstrip('@'), str(guild_id)),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise LookupError(username)
        return row[0], row[1]

    @filter_group.command(name='add', description='Only post tweets that contain one of these keywords')
    @has_allowed_role()
    @app_commands.describe(
        keywords='Keywords separated by a comma or a semicolon, e.g. release, update; patch',
        username='Only for this tracked account (default: every account)',
        channel='Only for this channel (default: every channel)',
    )
    async def add(self, itn: discord.Interaction, keywords: str, username: str = None, channel: discord.TextChannel | discord.Thread = None):
        parsed = parse_keywords(keywords)
        if (error := check_keywords(parsed)):
            await itn.response.send_message(error)
            return

        await itn.response.defer()
        async with aiosqlite.connect(db_path()) as db:
            await db.execute(TABLE_SQL)
            try:
                user_id, shown_name = await self._resolve_username(db, itn.guild_id, username)
            except LookupError:
                await itn.followup.send(f"\u274c **{username}** isn't tracked on this server. Add them with `/add notifier` first.")
                return

            async with db.execute('SELECT count(*) FROM keyword_filter WHERE guild_id = ?', (str(itn.guild_id),)) as cursor:
                existing = (await cursor.fetchone())[0]
            if existing + len(parsed) > MAX_KEYWORDS_PER_SERVER:
                await itn.followup.send(f'\u274c A server can have at most {MAX_KEYWORDS_PER_SERVER} filter keywords.')
                return

            channel_id = str(channel.id) if channel else ''
            added, already = [], []
            for keyword in parsed:
                cursor = await db.execute(
                    'INSERT OR IGNORE INTO keyword_filter (guild_id, user_id, channel_id, keyword) VALUES (?, ?, ?, ?)',
                    (str(itn.guild_id), user_id, channel_id, keyword),
                )
                (added if cursor.rowcount > 0 else already).append(keyword)
            await db.commit()

        scope = describe_scope(shown_name, channel_id)
        lines = []
        if added:
            lines.append(f"\u2705 Added {', '.join(f'`{k}`' for k in added)} {scope}. "
                         'The bot now only posts tweets that contain one of the keywords.')
        if already:
            lines.append(f"Already in the filter: {', '.join(f'`{k}`' for k in already)}.")
        await itn.followup.send('\n'.join(lines), allowed_mentions=NO_PING)

    @filter_group.command(name='remove', description='Remove keywords from the filter')
    @has_allowed_role()
    @app_commands.describe(
        keywords='Keywords separated by a comma or a semicolon, e.g. release, update; patch',
        username='The account the keywords were added for (leave empty if you added them for everyone)',
        channel='The channel the keywords were added for (leave empty if you added them for every channel)',
    )
    async def remove(self, itn: discord.Interaction, keywords: str, username: str = None, channel: discord.TextChannel | discord.Thread = None):
        parsed = parse_keywords(keywords)
        if (error := check_keywords(parsed)):
            await itn.response.send_message(error)
            return

        await itn.response.defer()
        async with aiosqlite.connect(db_path()) as db:
            await db.execute(TABLE_SQL)
            try:
                user_id, shown_name = await self._resolve_username(db, itn.guild_id, username)
            except LookupError:
                await itn.followup.send(f"\u274c **{username}** isn't tracked on this server.")
                return

            channel_id = str(channel.id) if channel else ''
            removed, missing = [], []
            for keyword in parsed:
                cursor = await db.execute(
                    'DELETE FROM keyword_filter WHERE guild_id = ? AND user_id = ? AND channel_id = ? AND keyword = ?',
                    (str(itn.guild_id), user_id, channel_id, keyword),
                )
                (removed if cursor.rowcount > 0 else missing).append(keyword)
            await db.commit()
            async with db.execute('SELECT count(*) FROM keyword_filter WHERE guild_id = ?', (str(itn.guild_id),)) as cursor:
                left = (await cursor.fetchone())[0]

        scope = describe_scope(shown_name, channel_id)
        lines = []
        if removed:
            lines.append(f"\u2705 Removed {', '.join(f'`{k}`' for k in removed)} {scope}.")
            if left == 0:
                lines.append('No filters are left, so every tweet is posted again.')
        if missing:
            lines.append(f"Not found {scope}: {', '.join(f'`{k}`' for k in missing)}. Use `/keyword filter list` to see what is set.")
        await itn.followup.send('\n'.join(lines), allowed_mentions=NO_PING)

    @filter_group.command(name='list', description='Show the keyword filters on this server')
    @has_allowed_role()
    async def list_filters(self, itn: discord.Interaction):
        await itn.response.defer()
        async with aiosqlite.connect(db_path()) as db:
            await db.execute(TABLE_SQL)
            async with db.execute(
                'SELECT k.user_id, k.channel_id, k.keyword, u.username FROM keyword_filter k '
                'LEFT JOIN user u ON u.id = k.user_id WHERE k.guild_id = ? ORDER BY k.user_id, k.channel_id, k.keyword',
                (str(itn.guild_id),),
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            await itn.followup.send('No keyword filters are set, so every tweet is posted. Add one with `/keyword filter add`.')
            return

        groups: dict[tuple[str, str], tuple[str | None, list[str]]] = {}
        for user_id, channel_id, keyword, username in rows:
            groups.setdefault((user_id, channel_id), (username, []))[1].append(keyword)

        lines = ['**Keyword filters** (a tweet is posted only if it contains one of the keywords that apply to it):']
        for (user_id, channel_id), (username, words) in groups.items():
            scope = describe_scope(username or (user_id and 'unknown account'), channel_id)
            lines.append(f"\u2022 {scope[0].upper() + scope[1:]}: {', '.join(f'`{w}`' for w in words)}")
        message = '\n'.join(lines)
        if len(message) > MESSAGE_LIMIT:
            message = message[:MESSAGE_LIMIT].rsplit('\n', 1)[0] + '\n\u2026 (list shortened)'
        await itn.followup.send(message, allowed_mentions=NO_PING)

    @add.autocomplete('username')
    @remove.autocomplete('username')
    async def username_autocomplete(self, itn: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        async with connect_readonly(db_path()) as db:
            async with db.execute(
                'SELECT DISTINCT u.username FROM user u '
                'JOIN notification n ON n.user_id = u.id JOIN channel c ON c.id = n.channel_id '
                'WHERE c.server_id = ? AND n.enabled = 1',
                (str(itn.guild_id),),
            ) as cursor:
                names = [row[0] async for row in cursor]
        return [app_commands.Choice(name=n, value=n) for n in sorted(names) if current.lower().lstrip('@') in n.lower()][:AUTOCOMPLETE_MAX_CHOICES]


async def setup(bot: commands.Bot):
    await bot.add_cog(Keyword(bot))
