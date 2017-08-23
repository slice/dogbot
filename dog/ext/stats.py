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
    Returns a `datetime.datetime` of the latest usage.
    """
    row = await pg.fetchrow('SELECT * FROM command_statistics WHERE command_name != '
                            '\'command_stats\' ORDER BY last_used DESC')
    return row['last_used']


async def update_statistics(pg: asyncpg.connection.Connection, ctx: commands.Context):
    """
    Updates command statistics for a specific `discord.ext.commands.Context`.

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


class Stats(Cog):
    async def on_command_completion(self, ctx):
        if any('is_owner' in fun.__qualname__ for fun in ctx.command.checks):
            return
        async with self.bot.pgpool.acquire() as conn:
            await update_statistics(conn, ctx)

    @commands.command()
    async def stats(self, ctx):
        """ Shows participation info about the bot. """
        # TODO: Make this function neater. It's currently trash.

        # member stats
        all_members = list(self.bot.get_all_members())

        def filter_members_by_status(status):
            return len([m for m in all_members if m.status == status])
        num_members = len(all_members)
        num_online = filter_members_by_status(discord.Status.online)
        num_idle = filter_members_by_status(discord.Status.idle)
        num_dnd = filter_members_by_status(discord.Status.dnd)
        num_offline = filter_members_by_status(discord.Status.offline)
        perc_online = f'{round(num_online / num_members * 100, 2)}% is online'

        # channel stats
        all_channels = list(self.bot.get_all_channels())
        num_channels = len(all_channels)
        num_voice_channels = len([c for c in all_channels if isinstance(c, discord.VoiceChannel)])
        num_text_channels = len([c for c in all_channels if isinstance(c, discord.TextChannel)])

        # other stats
        num_emojis = len(self.bot.emojis)
        num_emojis_managed = len([e for e in self.bot.emojis if e.managed])
        num_servers = len(self.bot.guilds)
        member_counts = [len(g.members) for g in self.bot.guilds]
        average_member_count = int(sum(member_counts) / len(member_counts))
        uptime = str(datetime.datetime.utcnow() - self.bot.boot_time)[:-7]

        def cm(v):
            return utils.commas(v)

        embed = discord.Embed(title='Statistics')
        embed.set_footer(text=f'Booted at {utils.standard_datetime(self.bot.boot_time)} UTC')
        fields = {
            'Members': f'{cm(num_members)} total, {cm(num_online)} online\n{cm(num_dnd)} DnD, '
                       f'{cm(num_idle)} idle\n{cm(num_offline)} offline\n\n{perc_online}',
            'Channels': f'{cm(num_channels)} total\n'
                        f'{cm(num_voice_channels)} voice channel(s)\n'
                        f'{cm(num_text_channels)} text channel(s)\n',
            'Emoji': f'{cm(num_emojis)} total\n{cm(num_emojis_managed)} managed',
            'Servers': f'{cm(num_servers)} total\n{cm(average_member_count)} average members\n'
                       f'{cm(max(member_counts))} max, {cm(min(member_counts))} min',
            'Uptime': uptime
        }
        for name, value in fields.items():
            embed.add_field(name=name, value=value)
        await ctx.send(embed=embed)

    @commands.command(aliases=['cstats'])
    async def command_stats(self, ctx, *, command: str=None):
        """ Shows commands statistics. """

        if command:
            async with self.bot.pgpool.acquire() as conn:
                record = await get_statistics(conn, command)
            if not record:
                return await ctx.send('There are no statistics for that command.')
            embed = discord.Embed(title=f'Statistics for `{command}`')
            embed.add_field(name='Times used', value=utils.commas(record['times_used']))
            embed.add_field(name='Last used', value=utils.ago(record['last_used']))
            return await ctx.send(embed=embed)

        select = 'SELECT * FROM command_statistics ORDER BY times_used DESC LIMIT 5'
        async with self.bot.pgpool.acquire() as conn:
            records = await conn.fetch(select)

        medals = [':first_place:', ':second_place:', ':third_place:']
        embed = discord.Embed(title='Most used commands')
        async with self.bot.pgpool.acquire() as conn:
            lu = utils.ago(await last_used(conn))
        embed.set_footer(text=f'Last command usage was {lu}')

        for index, record in enumerate(records):
            medal = medals[index] if index < 3 else ''
            td = utils.ago(record['last_used'])
            used = 'Used {} time(s) (last used {})'.format(utils.commas(record['times_used']), td)
            embed.add_field(name=medal + record['command_name'], value=used, inline=False)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Stats(bot))
