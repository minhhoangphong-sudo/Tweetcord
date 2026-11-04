"""
cogs/owner.py - owner-only slash commands. Every reply is ephemeral ("Only you can see this").

    /load <extension>       load a cog
    /unload <extension>     unload a cog
    /reload <extension>     reload a cog
    /download_log           get console.log
    /download_data          get tracked_accounts.db
    /upload_data <file>     replace tracked_accounts.db with the attached .db file

Allowed: the bot's owner (Discord application owner/team) and anyone listed in
the SUPERUSER_IDS environment variable. These replace the old ko! prefix
commands, which could not hide their replies from the channel.
"""

import os

import discord
from discord import app_commands
from discord.ext import commands

from core.classes import Cog_Extension
from src.log import setup_logger
from src.permission import ADMINISTRATOR
from src.role_check import is_superuser

log = setup_logger(__name__)

SQLITE_HEADER = b'SQLite format 3\x00'
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class NotOwner(app_commands.CheckFailure):
    """The user is neither the bot owner nor a superuser."""


def owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if is_superuser(interaction.user.id) or await interaction.client.is_owner(interaction.user):
            return True
        raise NotOwner('Only the bot owner can use this command.')
    return app_commands.check(predicate)


def _db_path() -> str:
    return os.path.join(os.getenv('DATA_PATH'), 'tracked_accounts.db')


def is_sqlite_file(raw: bytes) -> bool:
    return raw.startswith(SQLITE_HEADER)


class Owner(Cog_Extension):

    @app_commands.command(name='load', description='Load a cog (owner only)')
    @app_commands.default_permissions(ADMINISTRATOR)
    @owner_only()
    async def load(self, itn: discord.Interaction, extension: str):
        await self.bot.load_extension(f'cogs.{extension}')
        await itn.response.send_message(f'Loaded {extension} done.', ephemeral=True)

    @app_commands.command(name='unload', description='Unload a cog (owner only)')
    @app_commands.default_permissions(ADMINISTRATOR)
    @owner_only()
    async def unload(self, itn: discord.Interaction, extension: str):
        await self.bot.unload_extension(f'cogs.{extension}')
        await itn.response.send_message(f'Un - Loaded {extension} done.', ephemeral=True)

    @app_commands.command(name='reload', description='Reload a cog (owner only)')
    @app_commands.default_permissions(ADMINISTRATOR)
    @owner_only()
    async def reload(self, itn: discord.Interaction, extension: str):
        await self.bot.reload_extension(f'cogs.{extension}')
        await itn.response.send_message(f'Re - Loaded {extension} done.', ephemeral=True)

    @load.autocomplete('extension')
    @unload.autocomplete('extension')
    @reload.autocomplete('extension')
    async def extension_autocomplete(self, itn: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        # Autocomplete isn't covered by the command check, so enforce owner-only here too.
        if not (is_superuser(itn.user.id) or await self.bot.is_owner(itn.user)):
            return []
        names = sorted(f[:-3] for f in os.listdir('./cogs') if f.endswith('.py'))
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    @app_commands.command(name='download_log', description='Download console.log (owner only)')
    @app_commands.default_permissions(ADMINISTRATOR)
    @owner_only()
    async def download_log(self, itn: discord.Interaction):
        await itn.response.send_message(file=discord.File('console.log'), ephemeral=True)

    @app_commands.command(name='download_data', description='Download tracked_accounts.db (owner only)')
    @app_commands.default_permissions(ADMINISTRATOR)
    @owner_only()
    async def download_data(self, itn: discord.Interaction):
        await itn.response.send_message(file=discord.File(_db_path()), ephemeral=True)

    @app_commands.command(name='upload_data', description='Replace tracked_accounts.db with an uploaded .db file (owner only)')
    @app_commands.default_permissions(ADMINISTRATOR)
    @app_commands.describe(file='The tracked_accounts.db file to upload')
    @owner_only()
    async def upload_data(self, itn: discord.Interaction, file: discord.Attachment):
        await itn.response.defer(ephemeral=True)

        if not file.filename.endswith('.db'):
            await itn.followup.send('\u274c Please attach a `.db` file.', ephemeral=True)
            return
        if file.size > MAX_UPLOAD_BYTES:
            await itn.followup.send('\u274c That file is too large.', ephemeral=True)
            return

        raw = await file.read()
        if not is_sqlite_file(raw):
            await itn.followup.send('\u274c That file is not a SQLite database, nothing was changed.', ephemeral=True)
            return

        with open(_db_path(), 'wb') as wbf:
            wbf.write(raw)
        log.info(f'{itn.user} replaced tracked_accounts.db through /upload_data')
        await itn.followup.send('\u2705 Successfully uploaded data.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
