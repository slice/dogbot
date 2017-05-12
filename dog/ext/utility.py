"""
Contains utility commands that help you get stuff done.
"""

import asyncio
import datetime
import logging
import operator
import random
import re
from collections import namedtuple
from typing import Any, Dict, List

import aiohttp
import discord
from discord.ext import commands

from asteval import Interpreter
from bs4 import BeautifulSoup
from dog import Cog
from dog.core import utils
from dog.humantime import HumanTime

logger = logging.getLogger(__name__)


class GoogleResult(namedtuple('Google', 'title description url')):
    """ A result from Google. """


async def jisho(session: aiohttp.ClientSession, query: str) -> Dict[Any, Any]:
    """ Searches Jisho, and returns definition data as a `dict`. """
    query_url = utils.urlescape(query)
    JISHO_ENDPOINT = 'http://jisho.org/api/v1/search/words?keyword={}'
    async with session.get(JISHO_ENDPOINT.format(query_url)) as resp:
        data = await resp.json()

        # failed, or no data
        if data['meta']['status'] != 200 or not data['data']:
            return None

        return data['data']


async def google(session: aiohttp.ClientSession, query: str) -> List[GoogleResult]:
    """ Searches Google. """
    url = 'https://www.google.com/search?q={}&safe=on'.format(utils.urlescape(query))
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrom'
                      'e/57.0.2987.133 Safari/537.36'
    }
    async with session.get(url, headers=headers) as resp:
        soup = BeautifulSoup(await resp.text(), 'html.parser')

        def inflate_node(node):
            a_tag = node.select('h3.r a')
            if not a_tag:
                return None
            a_tag = a_tag[0]

            # the url to the result and the title
            link, link_text = a_tag['href'], a_tag.string

            description = node.select('.rc .s div .st')
            if not description:
                description = None
            else:
                description = description[0].text
            return GoogleResult(url=link, title=link_text, description=description)
        return list(map(inflate_node, soup.find_all('div', {'class': 'g'})))


class Utility(Cog):
    @commands.command()
    @commands.is_owner()
    async def exception(self, ctx, message: str = 'Test exception'):
        """ Creates an exception. """
        raise RuntimeError(message)

    @commands.command()
    async def poll(self, ctx, conclude_on_votes: int, title: str, *choices: str):
        """
        Creates a poll.

        `conclude_on_votes` specifies how many votes are required in order to end the poll. Users
        vote on the poll with reactions.
        """

        if conclude_on_votes < 1:
            raise commands.errors.BadArgument('Invalid `conclude_on_votes` parameter. It must be '
                                              'greater than zero.')

        if not choices:
            # XXX: Can't use commands.errors.MissingRequiredArgument because we need to specify an
            #      object that Discord.py can `.name`.
            raise commands.errors.BadArgument('You need to specify some choices.')

        member_count = len(ctx.guild.members)
        if conclude_on_votes > member_count:
            raise commands.errors.BadArgument('There aren\'t that many people on the server. '
                                              f'({conclude_on_votes} > {member_count})')

        embed = discord.Embed(title=f'Poll by {ctx.author}: {title}',
                              description=utils.format_list(choices))

        poll_msg = await ctx.send(embed=embed)

        for i in range(len(choices)):
            await poll_msg.add_reaction(f'{i + 1}\u20e3')

        poll_results = {index: 0 for index, _ in enumerate(choices)}
        has_voted = []

        while True:
            total_votes = sum(votes for votes in poll_results.values())
            if total_votes == conclude_on_votes:
                break

            def message_check(reaction, adder):
                has_not_voted = adder.id not in has_voted
                is_poll_message = reaction.message.id == poll_msg.id
                not_bot = not adder.bot
                return has_not_voted and is_poll_message and not_bot

            reaction, adder = await self.bot.wait_for('reaction_add', check=message_check)

            # check if it was a number emoji
            if len(reaction.emoji) != 2 or reaction.emoji[1] != '\u20e3':
                logger.info('Ignoring invalid poll reaction -- reaction=%s, len(reaction)=%d',
                            reaction.emoji, len(reaction.emoji))
                continue

            poll_results[int(reaction.emoji[0]) - 1] += 1
            has_voted.append(adder)

        winning_choice = choices[max(poll_results.items(), key=operator.itemgetter(1))[0]]
        poll_summary = '\n'.join(f'{choices[index]} \N{EM DASH} **{votes}** vote(s)'
                                 for index, votes in poll_results.items())
        fmt = 'The poll has concluded. Result: **{}**\n\n{}'
        embed.description = fmt.format(winning_choice, poll_summary)
        try:
            await poll_msg.clear_reactions()
        except discord.Forbidden:
            pass
        await poll_msg.edit(embed=embed)

    @commands.command(aliases=['goog', 'g'])
    async def google(self, ctx, *, query: str):
        """ Searches on Google. """
        async with ctx.channel.typing():
            try:
                results = (await google(self.bot.session, query))[:3]

                if not results:
                    return await ctx.send('\N{PENSIVE FACE} Google gave me nothing.')

                def formatter(result):
                    if result is None:
                        return ''
                    desc = f' - {result.description}' if result.description else ''
                    return f'\N{BULLET} **{result.title}**{desc} ({result.url})'
                results_text = '\n'.join(map(formatter, results))
                await ctx.send(results_text)
            except aiohttp.ClientError:
                await ctx.send('\N{PENSIVE FACE} I couldn\'t contact Google.')

    @commands.command()
    async def jisho(self, ctx, *, query: str):
        """ Looks up Jisho definitions. """
        result = await jisho(self.bot.session, query)
        if not result:
            await ctx.send('No results found.')
            return
        result = result[0]

        embed = discord.Embed(title=query, description='')
        for j in result['japanese']:
            word = j['word'] if 'word' in j else query
            only_word = str(word) + '\n'
            embed.description += f'{word}: {j["reading"]}\n' if 'reading' in j else only_word
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
                        value=(f'{joined_dif}\n' +
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
        if not args:
            return await ctx.send('\N{CONFUSED FACE} I can\'t choose from an empty list!')
        await ctx.send(random.choice(args))

    @commands.command(aliases=['timer'])
    async def remind(self, ctx, time: HumanTime, *, reminder: str):
        """ Reminds you in a certain amount of time. """
        if time.seconds >= 604800:
            return await ctx.send('That time is too long. One week maximum.')
        await ctx.send('Got your reminder. I\'ll remind you in {0.raw} ({0.seconds} second(s)).'
                       .format(time))
        await asyncio.sleep(time.seconds)
        await ctx.author.send('**Ring!** {}'.format(reminder))

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
                        value=(f'{joined_dif}\n' +
                               utils.american_datetime(target.joined_at)),
                        inline=False)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Utility(bot))
