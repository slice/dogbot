"""
Reminders for Dogbot.
"""

import asyncio
import datetime
import logging

import discord
from discord.ext import commands

from dog import Cog
from dog.core import converters, utils
from dog.core.utils import AsyncQueue

logger = logging.getLogger(__name__)


class ReminderQueue(AsyncQueue):
    async def get_latest_item(self):
        async with self.bot.pgpool.acquire() as conn:
            latest_reminder = await conn.fetchrow('SELECT * FROM reminders ORDER BY due ASC LIMIT 1')
            if latest_reminder:
                logger.debug('Got latest reminder -- rid=%d', latest_reminder['id'])
            return latest_reminder

    async def fulfill_item(self, reminder):
        # wait
        remaining_duration = (reminder['due'] - datetime.datetime.utcnow()).total_seconds() + 1
        logger.debug('Remaining duration: %ds', remaining_duration)
        if remaining_duration > 0:
            await asyncio.sleep(remaining_duration)

        # notify
        author = self.bot.get_user(reminder['author_id'])
        logger.debug('Notifying author of reminder %d', reminder['id'])
        if not author:
            logger.debug('Not totally fulfilling reminder -- couldn\'t find author. rid=%d', reminder['id'])
            return
        else:
            await author.send(f'\N{ALARM CLOCK} {reminder["note"]}')

        # remove it from the database
        logger.debug('Removing reminder %d', reminder['id'])
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM reminders WHERE id = $1', reminder['id'])


class Reminders(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.queue = ReminderQueue(bot, 'Reminders')

    def __unload(self):
        self.queue.handler.cancel()

    async def create_reminder(self, ctx, due, note):
        async with self.bot.pgpool.acquire() as conn:
            cid = ctx.channel.id if isinstance(ctx.channel, discord.TextChannel) else ctx.author.id
            await conn.execute('INSERT INTO reminders (author_id, channel_id, note, due) VALUES ($1, $2, $3, $4)',
                               ctx.author.id, cid, note, due)
        logger.debug('Creating reminder -- due=%s note=%s cid=%d aid=%d', due, note, cid, ctx.author.id)

        # we just created a reminder, we definitely have one now!
        self.queue.has_item.set()

        # check if it's earlier
        if self.queue.current_item and self.queue.current_item['due'] > due:
            logger.debug('Got a reminder that is due earlier than the current one, rebooting task!')
            self.queue.reboot()

    @commands.group(invoke_without_command=True)
    async def remind(self, ctx, due_in: converters.HumanTime, *, note: commands.clean_content):
        """ Creates a reminder. """
        if due_in > (24 * 60 * 60) * 40:
            return await ctx.send('The maximum time allowed is 40 days.')
        due = datetime.datetime.utcnow() + datetime.timedelta(seconds=due_in)
        await self.create_reminder(ctx, due, note)
        await ctx.ok()

    @remind.command()
    async def list(self, ctx):
        """ Lists your reminders. """
        async with ctx.acquire() as conn:
            reminders = await conn.fetch('SELECT * FROM reminders WHERE author_id = $1', ctx.author.id)
            top = f'You currently have {len(reminders)} reminder(s).\n\n'
            lst = [f'#{r["id"]} `{r["note"]}` \N{EM DASH} due {utils.ago(r["due"])}' for r in reminders]
            await ctx.send(top + '\n'.join(lst))

    @remind.command()
    async def cancel(self, ctx, rid: int):
        """ Cancels a reminder. """
        async with ctx.acquire() as conn:
            reminder = await conn.fetchrow('SELECT * FROM reminders WHERE id = $1 AND author_id = $2',
                                           rid, ctx.author.id)
            if not reminder:
                return await ctx.send('I couldn\'t find that reminder, or you didn\'t create that one.')
            await conn.execute('DELETE FROM reminders WHERE id = $1', rid)
            await ctx.send('Alright, I went ahead and cancelled that one for you.')
            self.queue.has_item.clear()
            self.queue.reboot()


def setup(bot):
    bot.add_cog(Reminders(bot))
