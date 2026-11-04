"""
cogs/access.py - admin-only /access commands to choose which roles can use Tweetcord.

bot.py loads every .py file in the cogs folder, so this cog needs no extra setup.

    /access add role:@Role      allow a role (run it again to allow more roles)
    /access remove role:@Role   stop allowing a role
    /access list                show the allowed roles
    /access clear               remove all allowed roles

Only members with the Administrator permission can run these commands.
"""

import discord
from discord import app_commands
from discord.ext import commands

from core.classes import Cog_Extension
from src.permission import ADMINISTRATOR
from src.role_check import (
    ADMINS_ALWAYS_ALLOWED,
    add_allowed_role,
    admin_only,
    clear_allowed_roles,
    get_allowed_roles,
    remove_allowed_role,
)

NO_PING = discord.AllowedMentions.none()


class Access(Cog_Extension):
    # default_permissions hides the commands from non-admins in Discord's UI;
    # the admin_only() check below enforces it even if a server owner changes
    # the visibility in Server Settings > Integrations.
    access = app_commands.Group(
        name="access",
        description="Choose which roles can use Tweetcord commands (admins only)",
        guild_only=True,
        default_permissions=ADMINISTRATOR,
    )

    @access.command(name="add", description="Allow a role to use Tweetcord commands")
    @admin_only()
    @app_commands.describe(role="The role to allow")
    async def add(self, interaction: discord.Interaction, role: discord.Role):
        if role.is_default():
            await interaction.response.send_message(
                "\u274c You can't allow @everyone, that would let every member use Tweetcord. "
                "Pick a specific role.",
                ephemeral=True,
            )
            return

        added = add_allowed_role(interaction.guild.id, role.id)
        message = (
            f"\u2705 Members with {role.mention} can now use Tweetcord commands."
            if added
            else f"{role.mention} is already allowed."
        )
        await interaction.response.send_message(message, ephemeral=True, allowed_mentions=NO_PING)

    @access.command(name="remove", description="Stop allowing a role to use Tweetcord commands")
    @admin_only()
    @app_commands.describe(role="The role to remove")
    async def remove(self, interaction: discord.Interaction, role: discord.Role):
        removed = remove_allowed_role(interaction.guild.id, role.id)
        message = (
            f"\u2705 {role.mention} can no longer use Tweetcord commands."
            if removed
            else f"{role.mention} wasn't in the allowed list."
        )
        await interaction.response.send_message(message, ephemeral=True, allowed_mentions=NO_PING)

    @access.command(name="list", description="Show which roles can use Tweetcord commands")
    @admin_only()
    async def list_roles(self, interaction: discord.Interaction):
        role_ids = get_allowed_roles(interaction.guild.id)
        if not role_ids:
            message = (
                "No roles are set, so only server admins can use Tweetcord commands. "
                "Use `/access add` to allow a role."
            )
        else:
            lines = "\n".join(f"\u2022 <@&{rid}>" for rid in sorted(role_ids))
            message = f"Roles allowed to use Tweetcord commands:\n{lines}"
            if ADMINS_ALWAYS_ALLOWED:
                message += "\n\nServer admins can always use them."
        await interaction.response.send_message(message, ephemeral=True, allowed_mentions=NO_PING)

    @access.command(name="clear", description="Remove every allowed role")
    @admin_only()
    async def clear(self, interaction: discord.Interaction):
        count = clear_allowed_roles(interaction.guild.id)
        message = (
            f"\u2705 Removed {count} allowed role(s). Only server admins can use Tweetcord commands now."
            if count
            else "There were no allowed roles to remove."
        )
        await interaction.response.send_message(message, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        # Keep the list clean when a role is deleted from the server.
        remove_allowed_role(role.guild.id, role.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Access(bot))
