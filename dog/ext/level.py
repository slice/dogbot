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

    async def get_command_level(self, role: discord.Role) -> int:
        """ Returns the command level for a role. """
        level = (await self.bot.redis.get(f'levels:{role.id}'))
        if not level:
            return 0
        return int(level.decode())

    async def calculate_command_level(self, member: discord.Member) -> int:
        """ Calculates a command level for someone. """
        levels = [await self.get_command_level(r) for r in member.roles]
        return max(levels)

    @level.command(name='for')
    async def level_for(self, ctx, member: discord.Member):
        """
        Views the calculated command level for someone.

        Examples:
        d?level for @someone
            Shows you the command level for @someone.
        """
        level = await self.calculate_command_level(member)
        await ctx.send('Command level for `{}`: **{}**'.format(member, level))

    @level.command(name='levels')
    async def level_levels(self, ctx):
        """ Lists the roles in this server, and their levels. """
        lvls = {r.name: await self.get_command_level(r) for r in ctx.guild.roles}
        await ctx.send(utils.format_dict(lvls))

    @level.command(name='assign_level')
    async def level_assign_level(self, ctx, role: discord.Role, level: int):
        """
        Assigns a command level to a role. If someone has a role with a command level, then it will
        be taken into calculation when determining someone's command level.

        A command level of zero is equivalent to no command level at all.

        Examples:
        d?level assign_level "my role" 900
            Gives a role named "my role" a command level of 900.
        """

        await self.bot.redis.set(f'levels:{role.id}', level)
        await self.bot.ok(ctx)


def setup(bot):
    bot.add_cog(Level(bot))
