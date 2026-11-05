"""
cogs/yap.py - /yap posts a GIF link in the channel (public, anyone can use it).

To limit it to admins and allowed roles like the other commands, add
`from src.role_check import has_allowed_role` and put `@has_allowed_role()`
under the @app_commands.command line.
"""

import discord
from discord import app_commands
from discord.ext import commands

from core.classes import Cog_Extension

YAP_GIF_URL = 'https://klipy.com/gifs/kotori-blue-archive-1'


class Yap(Cog_Extension):

    @app_commands.command(name='yap', description='Yap.')
    async def yap(self, itn: discord.Interaction) -> None:
        # Plain link as the message so Discord shows its preview.
        await itn.response.send_message(YAP_GIF_URL)


async def setup(bot: commands.Bot):
    await bot.add_cog(Yap(bot))
