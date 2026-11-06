"""
cogs/help.py - /help lists the commands you can use and what they do.

The list is built from the commands the bot has registered, so it never goes
out of date. Admin-only and owner-only commands only show up for the people
who can run them. The reply is public and paginated like /list users, except when
the viewer is an admin or owner: their list includes the private commands, so it is ephemeral.
"""

import discord
from discord import app_commands
from discord.ext import commands

from configs.load_configs import configs
from core.classes import Cog_Extension
from src.discord_ui.pagination import Pagination
from src.i18n import t
from src.role_check import is_superuser

PSIZE = configs['users_list_pagination_size']
PCPOS = configs['users_list_page_counter_position']

ADMIN_ROOTS = {'access'}
OWNER_ROOTS = {'load', 'unload', 'reload', 'download_log', 'download_data', 'upload_data', 'send'}

# Shown in this order; anything not listed goes at the end, alphabetically.
ORDER = [
    'help', 'add notifier', 'remove notifier', 'customize settings', 'translation language', 'translation toggle',
    'list users', 'keyword filter add', 'keyword filter remove', 'keyword filter list', 'sync', 'yap', 'access add', 'access remove', 'access list', 'access clear',
    'load', 'unload', 'reload', 'download_log', 'download_data', 'upload_data', 'send',
]


def usage(command) -> str:
    parts = [f'/{command.qualified_name}']
    for param in command.parameters:
        parts.append(f'<{param.display_name}>' if param.required else f'[{param.display_name}]')
    return ' '.join(parts)


def build_entries(commands_: list, is_admin: bool, is_owner: bool) -> list[str]:
    """One numbered line per command the viewer is allowed to see."""
    visible = []
    for command in commands_:
        root = command.qualified_name.split(' ')[0]
        if root in OWNER_ROOTS and not is_owner:
            continue
        if root in ADMIN_ROOTS and not is_admin:
            continue
        visible.append(command)

    def sort_key(command):
        name = command.qualified_name
        return (ORDER.index(name), '') if name in ORDER else (len(ORDER), name)

    lines = []
    for i, command in enumerate(sorted(visible, key=sort_key), start=1):
        root = command.qualified_name.split(' ')[0]
        tag = ''
        if root in OWNER_ROOTS:
            tag = ' *(owner only)*'
        elif root in ADMIN_ROOTS:
            tag = ' *(admins only)*'
        description = command.description.replace(' (owner only)', '')
        lines.append(f'{i}. ```{usage(command)}``` {description}{tag}')
    return lines


class Help(Cog_Extension):

    @app_commands.command(name='help', description='Show what each Tweetcord command does.')
    @app_commands.guild_only()
    async def help(self, itn: discord.Interaction) -> None:
        member = itn.user
        superuser = is_superuser(member.id)
        is_admin = superuser or (isinstance(member, discord.Member) and member.guild_permissions.administrator)
        is_owner = superuser or await self.bot.is_owner(member)

        all_commands = [c for c in self.bot.tree.walk_commands() if isinstance(c, app_commands.Command)]
        formatted_data = build_entries(all_commands, is_admin, is_owner)

        async def get_page(page: int):
            offset = (page - 1) * PSIZE
            page_data = formatted_data[offset:offset + PSIZE]
            total_pages = Pagination.compute_total_pages(len(formatted_data), PSIZE)
            page_counter = t('list.title_page_counter', page=page, total=total_pages) if PCPOS == 'title' else ''
            title = f'Command List in __***{itn.guild.name}***__{page_counter}'
            embed = discord.Embed(title=title, description='\n'.join(page_data), color=0x778899)
            if PCPOS == 'footer':
                embed.set_footer(text=t('list.footer', page=page, total=total_pages))
            return embed, total_pages

        await Pagination(itn, get_page).navegate(ephemeral=is_admin or is_owner)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
