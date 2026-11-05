"""
cogs/send.py - owner-only /send posts a sample notification in the current channel.

It is built the same way the notifier builds a real one (same message template,
same embed layout, same button for the configured embed type), but every
variable is the text PLACEHOLDER: mention, author, action, url, the embed
title/description/author. Handy for checking how notifications look.

Discord rejects link fields (embed url, images, thumbnail, avatar, link buttons)
that are not real URLs, so those are left out instead of showing PLACEHOLDER.
"""

import discord
from discord import app_commands
from discord.ext import commands

from cogs.owner import owner_only
from configs.load_configs import configs
from core.classes import Cog_Extension
from src.i18n import t
from src.notification.display_tools import get_footer_name
from src.permission import ADMINISTRATOR

PLACEHOLDER = 'PLACEHOLDER'
EMBED_TYPE: str = configs['embed']['type']


def build_placeholder_notification() -> tuple[str, list[discord.Embed] | None, discord.ui.View | None]:
    """(message text, embeds, view) laid out like a real notification, filled with PLACEHOLDER."""
    msg = configs['default_message'].format(
        mention=f'{PLACEHOLDER} ', author=PLACEHOLDER, action=PLACEHOLDER, url=PLACEHOLDER,
    )

    if EMBED_TYPE == 'proxy':
        embeds = None
    else:
        embed = discord.Embed(title=PLACEHOLDER, description=PLACEHOLDER, color=0x1da0f2)
        embed.set_author(name=f'{PLACEHOLDER} (@{PLACEHOLDER})')
        embed.set_footer(
            text='Twitter' if configs['embed']['built_in']['legacy_logo'] else 'X',
            icon_url='attachment://footer.png',
        )
        embeds = [embed]

    view = None
    if EMBED_TYPE == 'proxy' and configs['embed']['proxy']['original_url_button']:
        # The real button is a link button; without a real URL it can only be a disabled one.
        view = discord.ui.View(timeout=5)
        view.add_item(discord.ui.Button(label=t('display.button.view_original'), style=discord.ButtonStyle.secondary, disabled=True))

    return msg, embeds, view


class Send(Cog_Extension):

    @app_commands.command(name='send', description='Post a placeholder notification in this channel (owner only)')
    @app_commands.default_permissions(ADMINISTRATOR)
    @owner_only()
    async def send(self, itn: discord.Interaction) -> None:
        msg, embeds, view = build_placeholder_notification()
        kwargs = {}
        if embeds:
            kwargs['embeds'] = embeds
            kwargs['file'] = discord.File(f'images/{get_footer_name()}', filename='footer.png')
        if view:
            kwargs['view'] = view
        await itn.response.send_message(msg, **kwargs)


async def setup(bot: commands.Bot):
    await bot.add_cog(Send(bot))
