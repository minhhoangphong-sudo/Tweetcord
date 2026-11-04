"""
cogs/access.py - admin-only /access commands to choose who can use Tweetcord's commands.

bot.py loads every .py file in the cogs folder, so this cog needs no extra setup.

    /access add <role or user>       allow a role or a user
    /access remove <role or user>    stop allowing one that was allowed before (pick from the suggestions)
    /access list                     show the allowed roles and users
    /access clear                    remove everyone from the list

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
    add_allowed_user,
    admin_only,
    clear_allowed,
    get_allowed_roles,
    get_allowed_users,
    is_superuser,
    remove_allowed_role,
    remove_allowed_user,
)

NO_PING = discord.AllowedMentions.none()
MAX_CHOICES = 25


class Access(Cog_Extension):
    # default_permissions hides the commands from non-admins in Discord's UI;
    # the admin_only() check below enforces it even if a server owner changes
    # the visibility in Server Settings > Integrations.
    access = app_commands.Group(
        name="access",
        description="Choose who can use Tweetcord commands (admins only)",
        guild_only=True,
        default_permissions=ADMINISTRATOR,
    )

    @access.command(name="add", description="Allow a role or a user to use Tweetcord commands")
    @admin_only()
    @app_commands.describe(target="The role or user to allow")
    async def add(self, interaction: discord.Interaction, target: discord.Role | discord.Member):
        if isinstance(target, discord.Role):
            if target.is_default():
                await interaction.response.send_message(
                    "\u274c You can't allow @everyone, that would let every member use Tweetcord. "
                    "Pick a specific role or user.",
                    ephemeral=True,
                )
                return
            added = add_allowed_role(interaction.guild.id, target.id)
        else:
            added = add_allowed_user(interaction.guild.id, target.id)

        if added:
            message = f"\u2705 {target.mention} can now use Tweetcord commands."
        else:
            message = f"{target.mention} is already allowed."
        await interaction.response.send_message(message, ephemeral=True, allowed_mentions=NO_PING)

    @access.command(name="remove", description="Stop allowing a role or user that was allowed before")
    @admin_only()
    @app_commands.describe(target="Pick an allowed role or user from the list")
    async def remove(self, interaction: discord.Interaction, target: str):
        kind, _, raw_id = target.partition(":")
        if kind not in ("role", "user") or not raw_id.isdigit():
            await interaction.response.send_message(
                "\u274c Please pick an entry from the suggestions. Use `/access list` to see who is allowed.",
                ephemeral=True,
            )
            return

        entry_id = int(raw_id)
        if kind == "role":
            removed = remove_allowed_role(interaction.guild.id, entry_id)
            mention = f"<@&{entry_id}>"
        else:
            removed = remove_allowed_user(interaction.guild.id, entry_id)
            mention = f"<@{entry_id}>"

        message = (
            f"\u2705 {mention} can no longer use Tweetcord commands."
            if removed
            else f"{mention} wasn't in the allowed list."
        )
        await interaction.response.send_message(message, ephemeral=True, allowed_mentions=NO_PING)

    @remove.autocomplete("target")
    async def remove_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        # Autocomplete isn't covered by the command check, so enforce admin-only here too.
        member = interaction.user
        if interaction.guild is None or not isinstance(member, discord.Member) or not (is_superuser(member.id) or member.guild_permissions.administrator):
            return []

        guild = interaction.guild
        entries = []
        for rid in sorted(get_allowed_roles(guild.id)):
            role = guild.get_role(rid)
            entries.append((f"Role: @{role.name}" if role else f"Role: deleted ({rid})", f"role:{rid}"))
        for uid in sorted(get_allowed_users(guild.id)):
            user = guild.get_member(uid)
            entries.append((f"User: {user.display_name}" if user else f"User: unknown ({uid})", f"user:{uid}"))

        needle = current.lower()
        return [
            app_commands.Choice(name=name[:100], value=value)
            for name, value in entries
            if needle in name.lower()
        ][:MAX_CHOICES]

    @access.command(name="list", description="Show which roles and users can use Tweetcord commands")
    @admin_only()
    async def list_allowed(self, interaction: discord.Interaction):
        role_ids = get_allowed_roles(interaction.guild.id)
        user_ids = get_allowed_users(interaction.guild.id)
        if not role_ids and not user_ids:
            message = (
                "Nobody is set, so only server admins can use Tweetcord commands. "
                "Use `/access add` to allow a role or user."
            )
        else:
            parts = ["Allowed to use Tweetcord commands:"]
            if role_ids:
                parts.append("**Roles**\n" + "\n".join(f"\u2022 <@&{rid}>" for rid in sorted(role_ids)))
            if user_ids:
                parts.append("**Users**\n" + "\n".join(f"\u2022 <@{uid}>" for uid in sorted(user_ids)))
            message = "\n\n".join(parts)
            if ADMINS_ALWAYS_ALLOWED:
                message += "\n\nServer admins can always use them."
        await interaction.response.send_message(message, ephemeral=True, allowed_mentions=NO_PING)

    @access.command(name="clear", description="Remove every allowed role and user")
    @admin_only()
    async def clear(self, interaction: discord.Interaction):
        count = clear_allowed(interaction.guild.id)
        message = (
            f"\u2705 Removed {count} allowed role(s)/user(s). Only server admins can use Tweetcord commands now."
            if count
            else "There was nobody to remove."
        )
        await interaction.response.send_message(message, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        # Keep the list clean when a role is deleted from the server.
        remove_allowed_role(role.guild.id, role.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # A user who leaves the server loses their access.
        remove_allowed_user(member.guild.id, member.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Access(bot))
