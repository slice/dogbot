import datetime
import logging
import discord
import platform
from bson.objectid import ObjectId
from pymongo import MongoClient
from subprocess import check_output
from discord.ext import commands
from dog import Cog, checks
from dog_config import mongo_url, owner_id, github

logger = logging.getLogger(__name__)

class About(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        logger.info('mongo url: %s', mongo_url)

        self.client = MongoClient(mongo_url)
        self.coll = self.client.dog.feedback
        self.blocked_coll = self.client.dog.feedback_blocked

    def not_blocked():
        def predicate(ctx):
            if ctx.cog is None:
                return True
            blocked_coll = ctx.cog.blocked_coll
            result = blocked_coll.find_one({'user_id': ctx.message.author.id})
            return result is None
        return commands.check(predicate)

    @commands.command()
    async def about(self, ctx):
        """ Shows information about the bot. """
        git_revision = check_output(['git', 'rev-parse', '--short', 'HEAD'])\
            .strip().decode('utf-8')
        maker = await self.bot.get_user_info(owner_id)
        embed = discord.Embed(
            title='Dogbot',
            description=f'A nice Discord bot by {maker.mention} ({maker.id}).'
            f' Available on GitHub [here](https://github.com/{github})!')
        embed.add_field(name='Git revision', value=f'[{git_revision}](https://github.com/'
                        f'{github}/commit/{git_revision})')
        embed.add_field(name='Python', value=platform.python_version())
        embed.set_footer(text=f'{maker.name}#{maker.discriminator}',
                         icon_url=maker.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name='github', aliases=['git', 'source', 'source_code'])
    async def _github(self, ctx):
        """ Tells you my GitHub link! """
        gh = f'https://github.com/{github}'
        await ctx.send(f'I\'m on GitHub at {gh}. Feel free to use handy'
                       ' tidbits of my source code!')

    @commands.group()
    async def feedback(self, ctx):
        """ Feedback commands for the bot. """

    @feedback.command(name='submit')
    @not_blocked()
    async def feedback_submit(self, ctx, *, feedback: str):
        """ Submits feedback. """
        if len(feedback) > 500:
            await self.bot.say('That feedback is too big! Keep it under 500 characters.')
            return

        logger.info('new feedback from %s: %s', ctx.message.author.id, feedback)
        self.coll.insert_one({
            'user_id': ctx.message.author.id,
            'content': feedback,
            'when': datetime.datetime.utcnow()
        })
        await ctx.send('Your feedback has been submitted.')
        owner = discord.utils.get(list(self.bot.get_all_members()), id=owner_id)
        new_feedback_fmt = """New feedback from {0.mention} (`{0.id}`)!

```
{1}
```"""
        await owner.send(new_feedback_fmt.format(ctx.message.author, feedback))

    @feedback.command(name='from')
    @checks.is_owner()
    async def feedback_from(self, ctx, who: discord.User):
        """ Fetches feedback from a specific person. """
        cursor = self.coll.find({'user_id': who.id})
        lines = '\n'.join(f'• `{f["_id"]}`, {f["content"]}' for f in cursor)
        if lines == '':
            await ctx.send('This user has no feedbacks.')
        else:
            await ctx.send(lines)

    @feedback.command(name='block')
    @checks.is_owner()
    async def feedback_block(self, ctx, who: discord.User):
        """ Blocks someone from submitting feedback. """
        self.blocked_coll.insert_one({'user_id': who.id})
        await ctx.send('\N{OK HAND SIGN}')
        logger.info('blocked %s from using feedback', who.id)

    @feedback.command(name='delete', aliases=['remove'])
    @checks.is_owner()
    async def feedback_delete(self, ctx, feedback_id: str):
        """ Removes a specific feedback. """
        self.coll.delete_one({'_id': ObjectId(feedback_id)})
        await ctx.send('Deleted.')

    @feedback.command(name='unblock')
    @checks.is_owner()
    async def feedback_unblock(self, ctx, who: discord.User):
        """ Unblocks someone from submitting feedback. """
        self.blocked_coll.delete_one({'user_id': who.id})
        await ctx.send('\N{OK HAND SIGN}')
        logger.info('unblocked %s from using feedback', who.id)

    @feedback.command(name='purge')
    @checks.is_owner()
    async def feedback_purge(self, ctx, who: discord.User):
        """ Purges all feedback from a specific person. """
        result = self.coll.delete_many({'user_id': who.id})
        await ctx.send(f'Deleted {result.deleted_count} feedback(s).')

    @feedback.command(name='stats')
    @checks.is_owner()
    async def feedback_stats(self, ctx):
        """ Shows the amount of feedbacks sent. """
        feedbacks = len(list(self.coll.find()))
        await ctx.send(f'A total of {feedbacks} feedback(s) have been submitted.')

    @commands.command()
    @checks.is_owner()
    async def stats(self, ctx):
        """ Shows participation info about the bot. """
        num_members = len(list(self.bot.get_all_members()))
        num_channels = len(list(self.bot.get_all_channels()))
        num_servers = len(self.bot.guilds)
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
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(About(bot))
