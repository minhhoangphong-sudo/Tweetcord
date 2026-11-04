"""
src/role_check.py - let server admins choose which roles may use Tweetcord commands.

Allowed roles and users are stored per server in role_access.db inside DATA_PATH (backed up to Turso by
src/db_function/turso_sync.py, and a separate file
from tracked_accounts.db, so the owner's .upload_data command can't overwrite it).

Use has_allowed_role() as a decorator on a slash command:

    from src.role_check import has_allowed_role

    @add_group.command(name='notifier', ...)
    @has_allowed_role()
    async def notifier(self, itn: discord.Interaction, ...):
        ...

When a check fails, bot.py's existing on_tree_error handler sends the error
text to the user as an ephemeral message, so no extra error handler is needed.

Admins pick the roles with the /access commands in cogs/access.py.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing

import discord
from discord import app_commands

# Server admins can always use Tweetcord commands, even when no role has been
# set yet. Set to False to make admins need one of the allowed roles too.
ADMINS_ALWAYS_ALLOWED = True


def get_superuser_ids() -> set[int]:
    """Discord user IDs from the SUPERUSER_IDS environment variable (comma separated).

    Superusers pass every Tweetcord check in every server: they can run all the
    bot's commands and manage /access without being a server admin or having an
    allowed role. IDs are used instead of usernames because usernames can change.
    """
    ids = set()
    for part in os.getenv("SUPERUSER_IDS", "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def is_superuser(user_id: int) -> bool:
    return user_id in get_superuser_ids()


class NotAllowed(app_commands.CheckFailure):
    """The user has none of the roles allowed to use Tweetcord commands."""


class NotAnAdmin(app_commands.CheckFailure):
    """The user ran an admin-only command without administrator permission."""


# --------------------------------------------------------------------------
# Storage (SQLite, one row per allowed role per server)
# --------------------------------------------------------------------------

def _db_path() -> str:
    folder = os.getenv("DATA_PATH", "")
    if folder:
        os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "role_access.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS allowed_roles ("
        " guild_id INTEGER NOT NULL,"
        " role_id INTEGER NOT NULL,"
        " PRIMARY KEY (guild_id, role_id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS allowed_users ("
        " guild_id INTEGER NOT NULL,"
        " user_id INTEGER NOT NULL,"
        " PRIMARY KEY (guild_id, user_id))"
    )
    return conn


def get_allowed_roles(guild_id: int) -> set[int]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT role_id FROM allowed_roles WHERE guild_id = ?", (guild_id,)
        ).fetchall()
    return {row[0] for row in rows}


def add_allowed_role(guild_id: int, role_id: int) -> bool:
    """Returns True if the role was newly added, False if it was already allowed."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO allowed_roles (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id),
        )
        return cur.rowcount > 0


def remove_allowed_role(guild_id: int, role_id: int) -> bool:
    """Returns True if the role was removed, False if it wasn't in the list."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM allowed_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        )
        return cur.rowcount > 0


def get_allowed_users(guild_id: int) -> set[int]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT user_id FROM allowed_users WHERE guild_id = ?", (guild_id,)
        ).fetchall()
    return {row[0] for row in rows}


def add_allowed_user(guild_id: int, user_id: int) -> bool:
    """Returns True if the user was newly added, False if they were already allowed."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO allowed_users (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        return cur.rowcount > 0


def remove_allowed_user(guild_id: int, user_id: int) -> bool:
    """Returns True if the user was removed, False if they weren't in the list."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM allowed_users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return cur.rowcount > 0


def clear_allowed(guild_id: int) -> int:
    """Removes every allowed role and user for the server. Returns how many were removed."""
    with closing(_connect()) as conn, conn:
        roles = conn.execute("DELETE FROM allowed_roles WHERE guild_id = ?", (guild_id,)).rowcount
        users = conn.execute("DELETE FROM allowed_users WHERE guild_id = ?", (guild_id,)).rowcount
        return roles + users


# Old name, kept so existing imports keep working
clear_allowed_roles = clear_allowed


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def has_allowed_role():
    """Slash-command check: only members with an admin-configured role may run it."""

    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user

        # Roles only exist inside a server, so block DMs.
        if interaction.guild is None or not isinstance(member, discord.Member):
            raise NotAllowed("This command can only be used inside a server.")

        if is_superuser(member.id):
            return True

        if ADMINS_ALWAYS_ALLOWED and member.guild_permissions.administrator:
            return True

        allowed_ids = get_allowed_roles(interaction.guild.id)
        allowed_users = get_allowed_users(interaction.guild.id)
        if not allowed_ids and not allowed_users:
            raise NotAllowed(
                "No role or user has been allowed to use this command yet. "
                "A server admin can allow one with `/access add`."
            )

        if member.id in allowed_users or any(role.id in allowed_ids for role in member.roles):
            return True

        if allowed_ids:
            mentions = " ".join(f"<@&{rid}>" for rid in sorted(allowed_ids))
            raise NotAllowed(f"You need one of these roles to use this command: {mentions}")
        raise NotAllowed("You aren't allowed to use this command. Ask a server admin to allow you.")

    return app_commands.check(predicate)


def admin_only():
    """Slash-command check: only server administrators may run it."""

    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if interaction.guild is None or not isinstance(member, discord.Member):
            raise NotAnAdmin("This command can only be used inside a server.")
        if is_superuser(member.id) or member.guild_permissions.administrator:
            return True
        raise NotAnAdmin("Only server administrators can use this command.")

    return app_commands.check(predicate)
