"""
Contains commands that manage levels.
"""

import logging

import discord
from discord.ext import commands

from dog import Cog
from dog.core import utils


class Level(Cog):
    @commands.group(aliases=['lv', 'lvl'])
    @commands.has_permissions(manage_guild=True)
    async def level(self, ctx):
        """
        This command group contains commands that manage command levels. Command levels are a
        per-server way of managing which roles get access to which commands.

        A command level is simply an integer. You can assign the command level for each command.
        Server members may execute commands in which their command level (calculated based on
        their roles) is greater than or equal to that command.

        Each role may have their own command level attached to them.

        For example, if a server member named Aaron had a command level of 100, they would be able
        to execute commands with a command level of 100 or lower. They may not execute commands with
        a command level greater than 100.
        """
        pass

    async def get_role_command_level(self, role: discord.Role) -> int:
        """ Returns the command level for a role. """
        level = await self.bot.redis.get(f'levels:role:{role.id}')
        if not level:
            return 0
        return int(level.decode())

    async def get_command_level(self, guild: discord.Guild, qual_name: str) -> int:
        """ Returns the command level for a command. """
        level = await self.bot.redis.get(f'levels:cmd:{guild.id}:{qual_name}')
        if not level:
            return 0
        return int(level.decode())

    async def calculate_command_level(self, member: discord.Member) -> int:
        """ Calculates a command level for someone. """
        levels = [await self.get_role_command_level(r) for r in member.roles]
        return max(levels)

    async def can_execute(self, member: discord.Member, qual_name: str) -> bool:
        """ Returns whether a member can execute a command by its qualified name. """
        role_level = await self.calculate_command_level(member)
        cmd_level = await self.get_command_level(member.guild, qual_name)
        return role_level >= cmd_level

    @level.command(name='for')
    async def level_for(self, ctx, who: discord.Member):
        """
        Views the calculated command level for someone.

        Examples:
        d?level for @someone
            Shows you the command level for @someone.
        """
        level = await self.calculate_command_level(who)
        await ctx.send('Command level for `{}`: **{}**'.format(who, level))

    @level.command(name='can_execute')
    async def level_can_execute(self, ctx, who: discord.Member, *, qual_name: str):
        """
        Views whether someone can execute a command or not.
        """
        can = await self.can_execute(who, qual_name)
        await ctx.send('`{}` can execute `d?{}`?: {}'.format(who, qual_name, can))

    @level.command(name='levels')
    async def level_levels(self, ctx):
        """ Lists the roles in this server, and their levels. """
        lvls = {r.name: await self.get_role_command_level(r) for r in ctx.guild.roles}
        await ctx.send(utils.format_dict(lvls))

    @level.command(name='cmd_level', aliases=['cl'])
    async def level_cmd_level(self, ctx, cmd: str, level: int=0):
        """
        Assigns a command level to a command, or views it. You will set it if a secondary argument
        is passed. A command invoker must have a command level matching the command or higher in
        order to execute it.

        Examples:
        d?level cmd_level ping 50
            Requires a command level of 50 or higher in order to execute d?ping.
        d?level cmd_level "tag delete" 250
            Requires a command level of 250 or higher in order to execute d?tag delete.
        """
        if level:
            if len(cmd) > 120:
                return await ctx.send('That isn\'t a command name!')
            await self.bot.redis.set(f'levels:cmd:{ctx.guild.id}:{cmd}', level)
            await self.bot.ok(ctx)
        else:
            lvl = await self.get_command_level(ctx.guild, cmd)
            await ctx.send('Command level for `d?{}`: **{}**'.format(cmd, lvl))

    @level.command(name='role_level', aliases=['rl'])
    async def level_role_level(self, ctx, role: discord.Role, level: int=0):
        """
        Assigns a command level to a role, or views it. You will set it if a secondary arugment is
        passed. If someone has a role with a command level, then it will be taken into calculation
        when determining someone's command level.

        A command level of zero is equivalent to no command level at all.

        Examples:
        d?level role_level "my role" 900
            Gives a role named "my role" a command level of 900.
        """

        if level:
            await self.bot.redis.set(f'levels:role:{role.id}', level)
            await self.bot.ok(ctx)
        else:
            lvl = await self.get_role_command_level(role)
            await ctx.send('Command level for role `{}`: **{}**'.format(role.name, lvl))


def setup(bot):
    bot.add_cog(Level(bot))
