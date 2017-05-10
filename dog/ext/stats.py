"""
Statistics extension.
"""

import datetime
import logging
from typing import List, Union

import asyncpg
import discord
from discord.ext import commands

from dog import Cog
from dog.core import utils

logger = logging.getLogger(__name__)


async def get_statistics(pg: asyncpg.connection.Connection, command_name: str) -> \
        Union[List[asyncpg.Record], None]:
    """
    Fetches statistics for a specific ``discord.ext.commands.Context``.

    If no record was found, ``None`` is returned.
    """
    return await pg.fetchrow('SELECT * FROM command_statistics WHERE command_name = $1',
                             command_name)


async def last_used(pg: asyncpg.connection.Connection) -> datetime.datetime:
    """
    Returns a ``datetime.datetime`` of the latest usage.
    """
    row = await pg.fetchrow('SELECT * FROM command_statistics WHERE command_name != '
                            '\'command_stats\' ORDER BY last_used DESC')
    return row['last_used']


async def update_statistics(pg: asyncpg.connection.Connection, ctx: commands.Context):
    """
    Updates command statistics for a specific ``discord.ext.commands.Context``.

    If no record was found for a command, it is created. Otherwise, the ``times_used`` and
    ``last_used`` fields are updated.
    """
    row = await get_statistics(pg, str(ctx.command))

    if row is None:
        # first time command is being used, insert it into the database
        insert = 'INSERT INTO command_statistics VALUES ($1, 1, $2)'
        await pg.execute(insert, str(ctx.command), datetime.datetime.utcnow())
        logger.info('First command usage for %s', ctx.command)
    else:
        # command was used before, increment time_used and update last_used
        update = ('UPDATE command_statistics SET times_used = times_used + 1, last_used = $2 '
                  'WHERE command_name = $1')
        await pg.execute(update, str(ctx.command), datetime.datetime.utcnow())
        logger.info('Increment usage for %s', ctx.command)


class Stats(Cog):
    async def on_command_completion(self, ctx):
        if any(['is_owner' in fun.__qualname__ for fun in ctx.command.checks]):
            logger.info('Not tracking %s, it\'s an owner command!', ctx.command)
            return
        await update_statistics(self.bot.pg, ctx)

    @commands.command(aliases=['cstats'])
    async def command_stats(self, ctx, *, command: str=None):
        """ Shows commands statistics. """

        if command:
            record = await get_statistics(self.bot.pg, command)
            if not record:
                return await ctx.send('There are no statistics for that command.')
            embed = discord.Embed(title=f'Statistics for `{command}`')
            embed.add_field(name='Times used', value=utils.commas(record['times_used']))
            embed.add_field(name='Last used', value=utils.ago(record['last_used']))
            return await ctx.send(embed=embed)

        select = 'SELECT * FROM command_statistics ORDER BY times_used DESC LIMIT 5'
        records = await self.bot.pg.fetch(select)

        medals = [':first_place:', ':second_place:', ':third_place:']
        embed = discord.Embed(title='Most used commands')
        lu = utils.ago(await last_used(self.bot.pg))
        embed.set_footer(text=f'Last command usage was {lu}')

        for index, record in enumerate(records):
            medal = medals[index] if index < 3 else ''
            td = utils.ago(record['last_used'])
            used = 'Used {} time(s) (last used {})'.format(utils.commas(record['times_used']), td)
            embed.add_field(name=medal + record['command_name'], value=used, inline=False)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Stats(bot))
