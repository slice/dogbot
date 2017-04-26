"""
Contains utility commands that help you get stuff done.
"""

import datetime
import random
import re

import aiohttp
import discord
from asteval import Interpreter
from discord.ext import commands

from dog import Cog
from dog.core import utils

async def jisho(query: str):
    query_url = utils.urlescape(query)
    JISHO_ENDPOINT = 'http://jisho.org/api/v1/search/words?keyword={}'
    async with aiohttp.ClientSession() as session:
        async with session.get(JISHO_ENDPOINT.format(query_url)) as resp:
            data = await resp.json()

            # failed, or no data
            if data['meta']['status'] != 200 or not data['data']:
                return None

            return data['data']

class Utility(Cog):
    @commands.command()
    @commands.is_owner()
    async def exception(self, ctx, message: str='Test exception'):
        raise RuntimeError(message)

    @commands.command()
    async def jisho(self, ctx, *, query: str):
        """ Looks up Jisho definitions. """
        result = await jisho(query)
        if not result:
            await ctx.send('No results found.')
            return
        result = result[0]

        embed = discord.Embed(title=query, description='')
        for j in result['japanese']:
            word = j['word'] if 'word' in j else query
            embed.description += f'{word}: {j["reading"]}\n'
        embed.description += '\n'
        for sense in result['senses']:
            restr = ', '.join(sense['restrictions'])
            sense_value = ', '.join(sense['english_definitions'])
            if sense['info']:
                sense_value += f' ({", ".join(sense["info"])})'
            if not sense['restrictions']:
                # not restricted
                embed.description += f'\N{BULLET} {sense_value}\n'
            else:
                embed.add_field(name=restr,
                                value=sense_value, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def avatar(self, ctx, target: discord.User=None):
        """
        Shows someone's avatar.

        If no arguments were passed, your avatar is shown.
        """
        if target is None:
            target = ctx.message.author
        await ctx.send(target.avatar_url)

    def _make_joined_embed(self, member):
        embed = utils.make_profile_embed(member)
        joined_dif = utils.pretty_timedelta(datetime.datetime.utcnow() - member.created_at)
        embed.add_field(name='Joined Discord',
                        value=(f'{joined_dif} ago\n' +
                               utils.american_datetime(member.created_at)))
        return embed

    @commands.command()
    async def jumbo(self, ctx, emoji: str):
        """ Views a custom emoji at a big resolution. """

        match = re.match(r'<:([a-z0-9A-Z_-]+):([0-9]+)>', emoji)
        if not match:
            await ctx.send('Not a custom emoji!')
            return

        # get emoji id
        emoji_id = match.groups()[1]
        emoji_cdn = 'https://discordapp.com/api/emojis/{}.png'

        # create wrapping embed
        wrapper_embed = discord.Embed()
        wrapper_embed.set_image(url=emoji_cdn.format(emoji_id))

        # send
        await ctx.send(embed=wrapper_embed)

    @commands.command()
    @commands.guild_only()
    async def default_channel(self, ctx):
        """ Shows you the default channel. """
        await ctx.send(ctx.guild.default_channel.mention)

    @commands.command()
    @commands.guild_only()
    async def earliest(self, ctx):
        """ Shows who in this server had the earliest Discord join time. """
        members = {m: m.created_at for m in ctx.guild.members if not m.bot}
        earliest_time = min(members.values())
        for member, time in members.items():
            if earliest_time == time:
                await ctx.send(embed=self._make_joined_embed(member))

    @commands.command(name='calc')
    async def calc(self, ctx, *, expression: str):
        """ Evaluates a math expression. """
        terp = Interpreter()
        result = terp.eval(expression)
        if result != '' and result is not None:
            await ctx.send(result)
        else:
            await ctx.send('Empty result.')

    @commands.command(aliases=['random', 'choose'])
    async def pick(self, ctx, *args):
        """
        Randomly picks things that you give it.

        d?pick one two three
            Makes the bot randomly pick from three words, and displays
            the chosen word.
        """
        await ctx.send(random.choice(args))

    @commands.command()
    @commands.guild_only()
    async def joined(self, ctx, target: discord.Member=None):
        """
        Shows when someone joined this server and Discord.

        If no arguments were passed, your information is shown.
        """
        if target is None:
            target = ctx.message.author

        def diff(date):
            now = datetime.datetime.utcnow()
            return utils.pretty_timedelta(now - date)

        embed = self._make_joined_embed(target)
        joined_dif = utils.pretty_timedelta(datetime.datetime.utcnow() - target.joined_at)
        embed.add_field(name='Joined this Server',
                        value=(f'{joined_dif} ago\n' +
                               utils.american_datetime(target.joined_at)),
                        inline=False)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Utility(bot))
