import asyncio
import logging
import os

import discord
import psutil
from discord.ext import commands
from dog import Cog
from dog.core import utils

logger = logging.getLogger(__name__)


class Measurer:
    def __init__(self, loop, *, interval=60):
        self.total = 0
        self.steps = 0
        self.task = None
        self.interval = interval

        self.start_task(loop)

    def start_task(self, loop):
        self.task = loop.create_task(self.measure())

    def cancel_task(self):
        if self.task:
            self.task.cancel()
            self.task = None

    def increment(self):
        self.total += 1

    async def measure(self):
        while True:
            await asyncio.sleep(self.interval)
            self.steps += 1

    def __str__(self):
        average = self.total / self.steps
        return '{:,.0f} avg/{}s, {:,d} total'.format(average, self.interval, self.total)


class Spy(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.presence_updates = Measurer(bot.loop, interval=5)
        self.messages = Measurer(bot.loop, interval=5)

    def __unload(self):
        self.presence_updates.cancel_task()
        self.messages.cancel_task()

    async def on_member_update(self, before, after):
        if before.game != after.game or before.status is not after.status:
            self.presence_updates.increment()

    async def on_message(self, msg: discord.Message):
        if isinstance(msg.channel, discord.abc.GuildChannel):
            self.messages.increment()

    @commands.group(invoke_without_command=True)
    async def spy(self, ctx, member: discord.Member):
        """ Spies on someone. """
        shared = sum(member in g.members for g in ctx.bot.guilds)

        data = {
            'member': f'{member} ({member.id})',
            'highest role': f'{member.top_role.name} ({member.top_role.id})',
            'shared': f'{shared} guild(s)',
            'created': f'{utils.ago(member.created_at)} ({utils.american_datetime(member.created_at)} UTC)',
            'joined': f'{utils.ago(member.joined_at)} ({utils.american_datetime(member.joined_at)} UTC)'
        }
        await ctx.send(utils.format_dict(data, style='ini'))

    @spy.command(name='stats')
    async def spy_stats(self, ctx):
        """ Spies on statistics. """
        members = utils.commas(sum(g.member_count for g in ctx.bot.guilds))

        process = psutil.Process(os.getpid())
        mem = process.memory_info()
        vmem = psutil.virtual_memory()
        mem_gib = round(mem.rss / 1024 ** 3, 2)
        mem_mib = round(mem.rss / 1024 ** 2, 2)
        percentage = round(mem.rss / vmem.total * 100, 2)

        data = {
            'guilds': f'{utils.commas(len(ctx.bot.guilds))} total guilds',
            'users': f'{utils.commas(len(ctx.bot.users))} total users',
            'members': f'{members} total members',
            'mem usage': f'{mem_gib} GiB, {mem_mib} MiB (using {percentage}% of total RAM)'
        }

        if self.presence_updates.steps:
            data['presence'] = str(self.presence_updates)

        if self.messages.steps:
            data['msg'] = str(self.messages)

        await ctx.send(utils.format_dict(data, style='ini'))


def setup(bot):
    bot.add_cog(Spy(bot))
