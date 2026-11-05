"""
cogs/yap.py - /yap posts a GIF in the channel (public, anyone can use it).

Each time it picks at random between:
  * the online GIF link (YAP_GIF_URL), and
  * a GIF from the localdata folder (any *.gif file in it, subfolders included).
    The folder is searched for in the project (up to 3 levels deep, any
    capitalization), so it doesn't have to be in the project root.
If localdata can't be found, has no usable GIF, or the upload fails, it posts
the link instead. The bot logs where it found the folder when it starts, and
every /yap writes what it chose and why (see /download_log, lines starting
with "yap:").

To limit it to admins and allowed roles like the other commands, add
`from src.role_check import has_allowed_role` and put `@has_allowed_role()`
under the @app_commands.command line.
"""

import os
import random

import discord
from discord import app_commands
from discord.ext import commands

from core.classes import Cog_Extension
from src.log import setup_logger

log = setup_logger(__name__)

YAP_GIF_URL = 'https://klipy.com/gifs/kotori-blue-archive-1'
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEARCH_ROOTS = [PROJECT_ROOT, os.getcwd()]  # where to look for the localdata folder
MIN_UPLOAD_LIMIT = 10 * 1024 * 1024  # Discord's default upload limit, in bytes


SKIP_DIRS = {'__pycache__', 'node_modules', 'venv', 'env'}
MAX_SEARCH_DEPTH = 3


def find_localdata_dir() -> str | None:
    """The localdata folder (any capitalization), searched for in the project and the working directory."""
    for root in dict.fromkeys(SEARCH_ROOTS):
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip(os.sep).count(os.sep)
        for current, dirs, _ in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.'))
            for d in dirs:
                if d.lower() == 'localdata':
                    return os.path.join(current, d)
            if current.rstrip(os.sep).count(os.sep) - base_depth >= MAX_SEARCH_DEPTH - 1:
                dirs[:] = []
    return None


def find_gifs(folder: str) -> list[str]:
    """Every .gif file in the folder and its subfolders."""
    found = []
    for current, _, names in os.walk(folder):
        found.extend(os.path.join(current, n) for n in names if n.lower().endswith('.gif'))
    return sorted(found)


def pick_gif(folder: str | None, max_bytes: int, rng=random) -> tuple[str | None, str]:
    """(path of a local GIF, or None for the link, and the reason, for the log). 50/50 when a local GIF is usable."""
    if folder is None:
        return None, f'no localdata folder found in {", ".join(dict.fromkeys(SEARCH_ROOTS))}'
    gifs = find_gifs(folder)
    if not gifs:
        return None, f'no .gif files in {folder}'
    usable = [p for p in gifs if os.path.getsize(p) <= max_bytes]
    if not usable:
        sizes = ', '.join(f'{os.path.basename(p)}={os.path.getsize(p)} bytes' for p in gifs)
        return None, f'every gif is over the {max_bytes} byte upload limit ({sizes})'
    if rng.random() < 0.5:
        return rng.choice(usable), 'random pick: local gif'
    return None, 'random pick: link'


class Yap(Cog_Extension):

    async def cog_load(self) -> None:
        folder = find_localdata_dir()
        if folder is None:
            log.warning(f'yap: no localdata folder found in {", ".join(dict.fromkeys(SEARCH_ROOTS))}, /yap will only send the link')
        else:
            log.info(f'yap: localdata folder is {folder} with {len(find_gifs(folder))} gif(s)')

    @app_commands.command(name='yap', description='Yap.')
    async def yap(self, itn: discord.Interaction) -> None:
        # Uploading a GIF can take longer than the 3 seconds Discord allows for a first
        # reply (slow on free hosting), so acknowledge right away and send it afterwards.
        await itn.response.defer()

        guild_limit = itn.guild.filesize_limit if itn.guild else 0
        path, reason = pick_gif(find_localdata_dir(), max(guild_limit, MIN_UPLOAD_LIMIT))

        if path is not None:
            try:
                await itn.followup.send(file=discord.File(path))
                log.info(f'yap: local gif {os.path.basename(path)} ({reason})')
                return
            except discord.HTTPException as e:
                reason = f'uploading {os.path.basename(path)} failed: {e}'

        # Plain link as the message so Discord shows its preview.
        await itn.followup.send(YAP_GIF_URL)
        log.info(f'yap: link ({reason})')


async def setup(bot: commands.Bot):
    await bot.add_cog(Yap(bot))
