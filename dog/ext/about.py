import os
import json
import datetime
import logging
import discord
import platform
from bson.objectid import ObjectId
from pymongo import MongoClient
from subprocess import check_output
from discord.ext import commands
from dog import Cog, checks

logger = logging.getLogger(__name__)
owner_id = '97104885337575424'

class About(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.client = MongoClient()
        self.coll = self.client.dog.feedback
        self.blocked = []

        # read blocked users from file
        if os.path.isfile('dog_blocked.json'):
            logger.info('found blocked, loading')
            with open('dog_blocked.json', 'r') as f:
                self.blocked = json.load(f)

    def _blocked_save(self):
        # save
        logger.info('saving blocked users')
        with open('dog_blocked.json', 'w') as f:
            json.dump(self.blocked, f)

    def not_blocked():
        def predicate(ctx):
            if ctx.cog is None:
                return True
            return ctx.message.author.id not in ctx.cog.blocked
        return commands.check(predicate)

    @commands.command()
    async def about(self):
        """ Shows information about the bot. """
        git_revision = check_output(['git', 'rev-parse', '--short', 'HEAD'])\
            .strip().decode('utf-8')
        maker = await self.bot.get_user_info(owner_id)
        embed = discord.Embed(
            title='Dogbot',
            description=f'A nice Discord bot by {maker.mention} ({maker.id}).'
            ' Available on GitHub [here](https://github.com/sliceofcode/dogbot)!')
        embed.add_field(name='Git revision', value=f'[{git_revision}](https://github.com/'
                        f'sliceofcode/dogbot/commit/{git_revision})')
        embed.add_field(name='Python', value=platform.python_version())
        embed.set_footer(text=f'{maker.name}#{maker.discriminator}',
                         icon_url=maker.avatar_url)
        await self.bot.say(embed=embed)

    @commands.command()
    async def github(self):
        """ Tells you my GitHub link! """
        gh = 'https://github.com/sliceofcode/dogbot'
        await self.bot.say(f'I\'m on GitHub at {gh}. Feel free to use handy'
                           ' tidbits of my source code!')

    @commands.group()
    async def feedback(self):
        """ Feedback commands for the bot. """

    @feedback.command(name='submit', pass_context=True)
    @not_blocked()
    async def feedback_submit(self, ctx, *, feedback: str):
        """ Submits feedback. """
        if len(feedback) > 500:
            await self.bot.say('That feedback is too big! Keep it under 500 characters.')
            return

        self.coll.insert_one({
            'user_id': ctx.message.author.id,
            'content': feedback,
            'when': datetime.datetime.utcnow()
        })
        await self.bot.say('Your feedback has been submitted.')
        owner = discord.utils.get(list(self.bot.get_all_members()), id=owner_id)
        new_feedback_fmt = """New feedback from {0.mention} (`{0.id}`)!

```
{1}
```"""
        await self.bot.send_message(owner, new_feedback_fmt.format(
            ctx.message.author, feedback))

    @feedback.command(name='from', pass_context=True)
    @checks.is_owner()
    async def feedback_from(self, ctx, who: discord.User):
        """ Fetches feedback from a specific person. """
        cursor = self.coll.find({'user_id': who.id})
        lines = '\n'.join(f'• `{f["_id"]}`, {f["content"]}' for f in cursor)
        if lines == '':
            await self.bot.say('This user has no feedbacks.')
        else:
            await self.bot.say(lines)

    @feedback.command(name='block')
    @checks.is_owner()
    async def feedback_block(self, who: discord.User):
        """ Blocks someone from submitting feedback. """
        self.blocked.append(who.id)
        self._blocked_save()
        await self.bot.say('\N{OK HAND SIGN}')
        logger.info('blocked %s from using feedback', who.id)

    @feedback.command(name='delete', aliases=['remove'])
    @checks.is_owner()
    async def feedback_delete(self, feedback_id: str):
        """ Removes a specific feedback. """
        self.coll.delete_one({'_id': ObjectId(feedback_id)})
        await self.bot.say('Deleted.')

    @feedback.command(name='unblock')
    @checks.is_owner()
    async def feedback_unblock(self, who: discord.User):
        """ Unblocks someone from submitting feedback. """
        self.blocked.remove(who.id)
        self._blocked_save()
        await self.bot.say('\N{OK HAND SIGN}')
        logger.info('unblocked %s from using feedback', who.id)

    @feedback.command(name='purge')
    @checks.is_owner()
    async def feedback_purge(self, who: discord.User):
        """ Purges all feedback from a specific person. """
        result = self.coll.delete_many({'user_id': who.id})
        await self.bot.say(f'Deleted {result.deleted_count} feedback(s).')

    @feedback.command(name='stats')
    @checks.is_owner()
    async def feedback_stats(self):
        """ Shows the amount of feedbacks sent. """
        feedbacks = len(list(self.coll.find()))
        await self.bot.say(f'A total of {feedbacks} feedback(s) have been submitted.')

    @commands.command()
    @checks.is_owner()
    async def stats(self):
        """ Shows participation info about the bot. """
        num_members = len(list(self.bot.get_all_members()))
        num_channels = len(list(self.bot.get_all_channels()))
        num_servers = len(self.bot.servers)
        uptime = str(datetime.datetime.utcnow() - self.bot.boot_time)[:-7]

        embed = discord.Embed(title='Statistics',
                              description='Statistics and participation information.')
        fields = {
            'Members': num_members,
            'Channels': num_channels,
            'Servers': num_servers,
            'Uptime': uptime,
        }
        for name, value in fields.items():
            embed.add_field(name=name, value=value)
        await self.bot.say(embed=embed)

def setup(bot):
    bot.add_cog(About(bot))
