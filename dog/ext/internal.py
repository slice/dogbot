"""
Dogbot internal commands.
"""
import datetime
import logging
import os

import asyncpg
import discord
import psutil
from discord.ext.commands import command, group

from dog import Cog
from dog.core import utils, converters
from dog.core.checks import user_is_bot_admin
from dog.core.utils.formatting import describe

logger = logging.getLogger(__name__)


class Internal(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.socket_events = 0

    async def __local_check(self, ctx):
        return await user_is_bot_admin(ctx, ctx.author)

    async def on_socket_raw_receive(self, _):
        self.socket_events += 1

    @command()
    async def dstats(self, ctx):
        """Shows detailed stats."""
        desc = """{0} (`{1}`, <@{1}>)\nCreated: {2}""".format(
            ctx.bot.user, ctx.bot.user.id, ctx.bot.user.created_at)
        embed = discord.Embed(
            title='Detailed stats',
            description=desc,
            color=discord.Color.blurple())

        # ram
        process = psutil.Process(os.getpid())
        mem = process.memory_info()
        vmem = psutil.virtual_memory()
        total = round(vmem.total / 10**9, 3)
        avail = round(vmem.available / 10**9, 3)
        mem_gb = round(mem.rss / 10**9, 2)
        mem_mb = round(mem.rss / 10**6, 2)
        ttl = f'Using {round(mem_gb / total * 100, 2)}% of total RAM'
        embed.add_field(
            name='RAM',
            value=
            f'{avail} GB/{total} GB total\n{mem_mb} MB, {mem_gb} GB\n{ttl}')

        # owner
        owner = (await ctx.bot.application_info()).owner
        embed.add_field(name='Owner', value=f'{owner.id}\n<@{owner.id}>')

        # guilds
        embed.add_field(
            name='Guilds', value=f'{utils.commas(len(ctx.bot.guilds))} total')

        # voice
        clients = ctx.bot.voice_clients
        embed.add_field(name='Voice', value=f'{len(clients)} voice client(s)')

        async with ctx.acquire() as conn:
            record = await conn.fetchrow(
                'SELECT SUM(times_used) FROM command_statistics')
            embed.add_field(
                name='Commands Ran',
                value=utils.commas(record['sum']) + ' total')

        await ctx.send(embed=embed)

    @command(aliases=['bl'])
    async def blacklist(self, ctx, guild: int):
        """
        Blacklists a guild.

        Blacklisted guilds will be automatically left by the bot upon being added to one.
        """
        async with ctx.acquire() as conn:
            try:
                await conn.execute(
                    'INSERT INTO blacklisted_guilds VALUES ($1)', guild)
            except asyncpg.UniqueViolationError:
                return await ctx.send('That guild is already blacklisted.')
        await ctx.ok()

    @command(aliases=['ubl'])
    async def unblacklist(self, ctx, guild: int):
        """Unblacklists a guild."""
        async with ctx.acquire() as conn:
            await conn.execute(
                'DELETE FROM blacklisted_guilds WHERE guild_id = $1', guild)
        await ctx.ok()

    @group(aliases=['gb'])
    async def globalbans(self, ctx):
        """Manages global bot bans."""

    @globalbans.command(name='flush')
    async def gb_flush(self, ctx):
        """
        Flushes the global ban cache.

        When someone speaks, Dogbot fetches whether that person has been banned or not, and stores
        that value in Redis for 2 hours. When the value expires, Dogbot checks again. But while we
        have the cached value during that 2 hour period, we go off of that instead of the actual banned
        value. That is why there is "ban cached" and "actually banned". When we create a ban, the cached
        value for that user is instantly invalidated, so the ban takes effect immediately. However, unbans do
        not invalidate cache. With this command, Dogbot will check all cached bans and check if they are actually
        banned. If they are, the cached value is removed so unbans will take effect immediately.
        """
        results = []

        async for key in ctx.bot.redis.iscan(match='cache:globalbans:*'):
            if (await
                    ctx.bot.redis.get(key.decode())).decode() == 'not banned':
                logger.debug('Ignoring present "not banned" cache value (%s).',
                             key.decode())
                continue

            id = int(key.decode().split(':')[2])
            logger.debug('Flushing ban for %s (%d)', key.decode(), id)

            user = ctx.bot.get_user(id)
            if not user:
                # wat
                results.append(
                    f'\N{CROSS MARK} Could not resolve user `{id}`, not flushed.'
                )
                continue

            async with ctx.acquire() as conn:
                ban_row = await conn.fetchrow(
                    'SELECT * FROM globalbans WHERE user_id = $1', user.id)

            if ban_row is None:
                results.append(
                    f'{ctx.green_tick} Removed ban for {describe(user)}')
                await ctx.bot.redis.delete(key.decode())
                logger.debug(
                    'Removing ban for %s (%s) as part of flush operation.',
                    key.decode(), user)
            else:
                results.append(
                    f'\N{HAMMER} Persisting ban for {describe(user)}, still banned!'
                )

        await ctx.send('\n'.join(results) if results else 'Nothing happened.')

    @globalbans.command(name='add')
    async def gb_add(self, ctx, who: converters.RawMember, *, reason):
        """Adds a global ban."""
        async with ctx.acquire() as conn:
            try:
                sql = 'INSERT INTO globalbans (user_id, reason, created_at) VALUES ($1, $2, $3)'
                await conn.execute(sql, who.id, reason,
                                   datetime.datetime.utcnow())
            except asyncpg.UniqueViolationError:
                return await ctx.send(
                    'That user has already been global banned.')
        # invalidate cache
        logger.info('%s was just global banned, invalidating cached value.')
        await ctx.bot.redis.delete(f'cache:globalbans:{who.id}')
        await ctx.ok()

    @globalbans.command(name='status')
    async def gb_status(self, ctx, who: converters.RawMember):
        """Checks on global ban status."""
        is_banned = await ctx.bot.is_global_banned(who)
        is_banned_cached = (await
                            ctx.bot.redis.get(f'cache:globalbans:{who.id}')
                            ).decode() == 'banned'

        async with ctx.acquire() as conn:
            actual_ban = await conn.fetchrow(
                'SELECT * FROM globalbans WHERE user_id = $1', who.id)

        embed = discord.Embed(
            color=(
                discord.Color.red() if is_banned else discord.Color.green()))
        embed.set_author(name=who, icon_url=who.avatar_url_as(format='png'))
        embed.add_field(
            name='Ban cached', value='Yes' if is_banned_cached else 'No')
        embed.add_field(
            name='Actually banned',
            value='Yes' if actual_ban is not None else 'No')

        if actual_ban:
            embed.description = f'**Banned for:** {actual_ban["reason"]}'
            embed.add_field(
                name='Banned', value=utils.ago(actual_ban["created_at"]))

        await ctx.send(embed=embed)

    @globalbans.command(name='remove')
    async def gb_remove(self, ctx, who: converters.RawMember):
        """Removes a global ban."""
        async with ctx.acquire() as conn:
            await conn.execute('DELETE FROM globalbans WHERE user_id = $1',
                               who.id)
        await ctx.ok()


def setup(bot):
    bot.add_cog(Internal(bot))
