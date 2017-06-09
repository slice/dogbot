"""
Reminders for Dogbot.
"""

import asyncio
import datetime
import logging

import discord
from discord.ext import commands
from dog import Cog
from dog.core import converters

logger = logging.getLogger(__name__)


class Reminders(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.has_a_reminder = asyncio.Event()
        self.current_reminder = None
        self.handler_task = bot.loop.create_task(self.handle_reminders())

    def __unload(self):
        self.handler_task.cancel()

    async def create_reminder(self, ctx, due, note):
        async with self.bot.pgpool.acquire() as conn:
            cid = ctx.channel.id if isinstance(ctx.channel, discord.TextChannel) else ctx.author.id
            await conn.execute('INSERT INTO reminders (author_id, channel_id, note, due) VALUES ($1, $2, $3, $4)',
                               ctx.author.id, cid, note, due)
        logger.debug('Creating reminder -- due=%s note=%s cid=%d aid=%d', due, note, cid, ctx.author.id)

        # we just created a reminder, we definitely have one now!
        self.has_a_reminder.set()

        # check if it's earlier
        if self.current_reminder and self.current_reminder['due'] > due:
            logger.debug('Got a reminder that is due earlier than the current one, rebooting task!')
            self.handler_task.cancel()
            self.handler_task = self.bot.loop.create_task(self.handle_reminders())

    async def get_latest_reminder(self):
        async with self.bot.pgpool.acquire() as conn:
            latest_reminder = await conn.fetchrow('SELECT * FROM reminders ORDER BY due ASC LIMIT 1')
            if latest_reminder:
                logger.debug('Got latest reminder -- rid=%d', latest_reminder['id'])
            return latest_reminder

    async def fulfill_reminder(self, reminder):
        logger.debug('Removing reminder %d', reminder['id'])
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM reminders WHERE id = $1', reminder['id'])

        # notify
        author = self.bot.get_user(reminder['author_id'])
        logger.debug('Fulfilling reminder %d', reminder['id'])
        if not author:
            logger.debug('Not totally fulfilling reminder -- couldn\'t find author. rid=%d', reminder['id'])
            return
        else:
            await author.send(f'\N{ALARM CLOCK} **Ring ring!** {reminder["note"]}')

        if not await self.get_latest_reminder():
            # no more reminders
            logger.debug('No more reminders! Clearing flag.')
            self.has_a_reminder.clear()

    async def handle_reminders(self):
        logger.debug('Reminder handler started!')

        # when this first starts, the flag might not be set, but there could be a reminder. we should check
        if await self.get_latest_reminder():
            self.has_a_reminder.set()

        while not self.bot.is_closed():
            logger.debug('Waiting for a reminder...')

            # wait for a reminder
            await self.has_a_reminder.wait()

            # grab it
            reminder = self.current_reminder = await self.get_latest_reminder()
            logger.debug('Got a reminder! rid=%d', reminder['id'])

            # get remaining duration
            remaining_duration = (reminder['due'] - datetime.datetime.utcnow()).total_seconds() + 1
            logger.debug('Remaining duration: %ds', remaining_duration)
            if remaining_duration > 0:
                await asyncio.sleep(remaining_duration)

            # fulfill reminder
            await self.fulfill_reminder(reminder)
            self.current_reminder = None
            logger.debug('Handler: Fulfilled reminder #%d.', reminder['id'])

    @commands.command()
    async def remind(self, ctx, due_in: converters.HumanTime, *, note: str):
        """ Creates a reminder. """
        if due_in > (24 * 60 * 60) * 40:
            return await ctx.send('The maximum time allowed is 40 days.')
        due = datetime.datetime.utcnow() + datetime.timedelta(seconds=due_in)
        await self.create_reminder(ctx, due, note)
        await ctx.send('\N{ALARM CLOCK} Created your reminder.')


def setup(bot):
    bot.add_cog(Reminders(bot))
