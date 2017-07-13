"""
Dogbot internal commands.
"""
import datetime
import io
import logging
import os
from time import monotonic

import asyncpg
import discord
import objgraph
import psutil
from discord.ext import commands
from dog import Cog
from dog.core import utils, converters

DETAILED_PING = '''**message create:** {}
**message edit:** {}
**message delete:** {}
'''

logger = logging.getLogger(__name__)


class Internal(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.socket_events = 0

    async def __local_check(self, ctx):
        return await self.bot.is_owner(ctx.message.author)

    async def on_socket_raw_receive(self, _):
        self.socket_events += 1

    @commands.command()
    async def paginate(self, ctx, split_by: int, *, text):
        """ Tests the paginator. """
        pr = utils.Paginator(text, split_by)
        await pr.paginate(ctx)

    @commands.command()
    async def humantime(self, ctx, *, time: converters.HumanTime):
        """ Humantime debug. """
        await ctx.send(f'```py\n{repr(time)}\n```')

    @commands.command()
    async def dstats(self, ctx):
        """ Shows detailed stats. """
        desc = """{0} (`{1}`, <@{1}>)\nCreated: {2}""".format(ctx.bot.user, ctx.bot.user.id, ctx.bot.user.created_at)
        embed = discord.Embed(title='Detailed stats', description=desc, color=discord.Color.blurple())

        # ram
        process = psutil.Process(os.getpid())
        mem = process.memory_info()
        vmem = psutil.virtual_memory()
        total = round(vmem.total / 10 ** 9, 3)
        avail = round(vmem.available / 10 ** 9, 3)
        mem_gb = round(mem.rss / 10 ** 9, 2)
        mem_mb = round(mem.rss / 10 ** 6, 2)
        ttl = f'Using {round(mem_gb / total * 100, 2)}% of total RAM'
        embed.add_field(name='RAM', value=f'{avail} GB/{total} GB total\n{mem_mb} MB, {mem_gb} GB\n{ttl}')

        # owner
        owner = (await ctx.bot.application_info()).owner
        embed.add_field(name='Owner', value=f'{owner.id}\n<@{owner.id}>')

        # guilds
        embed.add_field(name='Guilds', value=f'{utils.commas(len(ctx.bot.guilds))} total')

        # voice
        clients = ctx.bot.voice_clients
        embed.add_field(name='Voice', value=f'{len(clients)} voice client(s)')

        async with ctx.bot.pgpool.acquire() as conn:
            record = await conn.fetchrow('SELECT SUM(times_used) FROM command_statistics')
            embed.add_field(name='Commands Ran', value=utils.commas(record['sum']) + ' total')

        await ctx.send(embed=embed)

    @commands.command(aliases=['bl'])
    async def blacklist(self, ctx, guild: int):
        """
        Blacklists a guild.

        Blacklisted guilds will be automatically left by the bot upon being added to one.
        """
        async with ctx.bot.pgpool.acquire() as conn:
            try:
                await conn.execute('INSERT INTO blacklisted_guilds VALUES ($1)', guild)
            except asyncpg.UniqueViolationError:
                return await ctx.send('That guild is already blacklisted.')
        await ctx.ok()

    @commands.command(aliases=['ubl'])
    async def unblacklist(self, ctx, guild: int):
        """ Unblacklists a guild. """
        async with ctx.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM blacklisted_guilds WHERE guild_id = $1', guild)
        await ctx.ok()

    @commands.group(aliases=['gb'])
    async def globalbans(self, ctx):
        """ Manages global bot bans. """

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
            if (await ctx.bot.redis.get(key.decode())).decode() == 'not banned':
                logger.debug('Ignoring present "not banned" cache value (%s).', key.decode())
                continue

            id = int(key.decode().split(':')[2])
            logger.debug('Flushing ban for %s (%d)', key.decode(), id)

            user = ctx.bot.get_user(id)
            if not user:
                # wat
                results.append(f'\N{CROSS MARK} Could not resolve user `{id}`, not flushed.')
                continue

            async with ctx.bot.pgpool.acquire() as conn:
                ban_row = await conn.fetchrow('SELECT * FROM globalbans WHERE user_id = $1', user.id)

            if ban_row is None:
                results.append(f'\N{WHITE HEAVY CHECK MARK} Removed ban for {user} (`{user.id}`).')
                await ctx.bot.redis.delete(key.decode())
                logger.debug('Removing ban for %s (%s) as part of flush operation.', key.decode(), user)
            else:
                results.append(f'\N{HAMMER} Persisting ban for {user} (`{user.id}`), still banned!')

        await ctx.send('\n'.join(results) if results else 'Nothing happened.')

    @globalbans.command(name='add')
    async def gb_add(self, ctx, who: converters.RawMember, *, reason):
        """ Adds a global ban. """
        async with ctx.bot.pgpool.acquire() as conn:
            try:
                sql = 'INSERT INTO globalbans (user_id, reason, created_at) VALUES ($1, $2, $3)'
                await conn.execute(sql, who.id, reason, datetime.datetime.utcnow())
            except asyncpg.UniqueViolationError:
                return await ctx.send('That user has already been global banned.')
        # invalidate cache
        logger.info('%s was just global banned, invalidating cached value.')
        await ctx.bot.redis.delete(f'cache:globalbans:{who.id}')
        await ctx.ok()

    @globalbans.command(name='status')
    async def gb_status(self, ctx, who: converters.RawMember):
        """ Checks on global ban status. """
        is_banned = await ctx.bot.is_global_banned(who)
        is_banned_cached = (await ctx.bot.redis.get(f'cache:globalbans:{who.id}')).decode() == 'banned'

        async with ctx.bot.pgpool.acquire() as conn:
            actual_ban = await conn.fetchrow('SELECT * FROM globalbans WHERE user_id = $1', who.id)

        embed = discord.Embed(color=(discord.Color.red() if is_banned else discord.Color.green()))
        embed.set_author(name=who, icon_url=who.avatar_url_as(format='png'))
        embed.add_field(name='Ban cached', value='Yes' if is_banned_cached else 'No')
        embed.add_field(name='Actually banned', value='Yes' if actual_ban is not None else 'No')

        if actual_ban:
            embed.description = f'**Banned for:** {actual_ban["reason"]}'
            embed.add_field(name='Banned', value=utils.ago(actual_ban["created_at"]))

        await ctx.send(embed=embed)

    @globalbans.command(name='remove')
    async def gb_remove(self, ctx, who: converters.RawMember):
        """ Removes a global ban. """
        async with ctx.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM globalbans WHERE user_id = $1', who.id)
        await ctx.ok()

    @commands.command()
    async def prefix_cache(self, ctx, guild_id: int = None):
        """ Inspects prefix cache for a guild. """
        guild_id = guild_id if guild_id else ctx.guild.id
        await ctx.send(f'`{repr(ctx.bot.prefix_cache.get(guild_id))}`')

    @commands.command()
    async def dping(self, ctx):
        """ Detailed ping. """
        def ms(before, after):
            return str(round((after - before) * 1000, 2)) + 'ms'

        # do it
        before_send = monotonic()
        msg = await ctx.send('...')
        after_send = monotonic()
        await msg.edit(content='..')
        after_edit = monotonic()
        await msg.delete()
        after_delete = monotonic()

        await ctx.send(DETAILED_PING.format(
            ms(before_send, after_send),
            ms(after_send, after_edit),
            ms(after_edit, after_delete)
        ))

    @commands.group()
    async def mem(self, ctx):
        """ Memory statistics. """
        pass

    @mem.command()
    async def count(self, ctx, type_name):
        """ Counts the amount of an object tracked by the GC. """
        cnt = objgraph.count(type_name)
        if not cnt:
            return await ctx.send('Not found.')
        await ctx.send('`{}`: {}'.format(type_name, utils.commas(cnt)))

    @mem.command()
    async def common_types(self, ctx, limit: int=5):
        """ Shows common types tracked by the GC. """
        with io.StringIO() as stdout:
            objgraph.show_most_common_types(limit=limit, file=stdout)
            await ctx.send('```\n{}\n```'.format(stdout.getvalue()))


def setup(bot):
    bot.add_cog(Internal(bot))
