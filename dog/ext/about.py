import datetime
import logging
import discord
import platform
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

    @commands.group()
    async def feedback(self):
        """ Feedback commands for the bot. """

    @feedback.command(name='submit', pass_context=True)
    async def feedback_submit(self, ctx, *, feedback: str):
        """ Submits feedback. """
        self.coll.insert_one({
            'user_id': ctx.message.author.id,
            'content': feedback,
            'when': datetime.datetime.utcnow()
        })
        await self.bot.say('Your feedback has been submitted.')

    @feedback.command(name='from', pass_context=True)
    async def feedback_from(self, ctx, who: discord.User):
        """ Fetches feedback from a specific person. """
        cursor = self.coll.find({'user_id': who.id})
        lines = '\n'.join(f'• {f["content"]}' for f in cursor)
        await self.bot.say(lines)

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
