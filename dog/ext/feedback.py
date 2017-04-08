import discord
import datetime
from discord.ext import commands
import logging
from bson.objectid import ObjectId
from pymongo import MongoClient
from dog import Cog, checks
from dog_config import mongo_url, owner_id

logger = logging.getLogger(__name__)


class Feedback(Cog):
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

    @commands.group()
    async def feedback(self, ctx):
        """ Feedback commands for the bot. """

    @feedback.command(name='submit')
    @not_blocked()
    async def feedback_submit(self, ctx, *, feedback: str):
        """ Submits feedback. """
        if len(feedback) > 500:
            await ctx.send('That feedback is too big! '
                           'Keep it under 500 characters please!')
            return

        logger.info('new feedback from %s: %s',
                    ctx.message.author.id, feedback)
        inserted_id = self.coll.insert_one({
            'user_id': ctx.message.author.id,
            'content': feedback,
            'when': datetime.datetime.utcnow()
        }).inserted_id
        await ctx.send('Your feedback has been submitted.')
        everyone = list(self.bot.get_all_members())
        owner = discord.utils.get(everyone, id=owner_id)
        new_feedback_fmt = """New feedback (`{2}`) by {0.mention} (`{0.id}`)!

```
{1}
```"""
        await owner.send(new_feedback_fmt.format(
            ctx.message.author, feedback, inserted_id))

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

    @feedback.command(name='respond')
    @checks.is_owner()
    async def feedback_respond(self, ctx, feedback_id: str, *, message: str):
        """
        Responds to feedback.

        d?feedback respond 58e5ae2f8dbfcf6a7fbf90de Thank you!
            Responds to a feedback with the ID of 58e5ae2f8dbfcf6a7fbf90de
            with the message "Thank you!"
        """
        feedback = self.coll.find_one({'_id': ObjectId(feedback_id)})
        if feedback is None:
            await ctx.send('That feedback wasn\'t found!')
            return
        user_id = int(feedback['user_id'])
        memb = discord.utils.get(list(self.bot.get_all_members()), id=user_id)
        if not memb:
            await ctx.send('I couldn\'t find the author of that feedback.'
                           f' Their ID is `{memb}`.')
            return
        await memb.send(
            f'Hey, {memb.mention}! My creator has responded to the feedback'
            f' that you sent earlier! You said:```\n{feedback["content"]}\n```'
            f'My creator says: ```\n{message}\n```\nThank you for submitting'
            ' feedback!'
        )
        await ctx.send('\N{OK HAND SIGN}')

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
        await ctx.send(f'A total of {feedbacks} feedback(s) '
                       'have been submitted.')

def setup(bot):
    bot.add_cog(Feedback(bot))
