"""
Contains utility commands that help you get stuff done.
"""

import datetime
import logging
import operator
import random
from collections import namedtuple
from typing import Any, Dict, List

import aiohttp
import discord
import dog_config
import pyowm
from asteval import Interpreter
from bs4 import BeautifulSoup
from discord.ext import commands
from dog import Cog
from dog.core import utils, converters

logger = logging.getLogger(__name__)


async def jisho(session: aiohttp.ClientSession, query: str) -> Dict[Any, Any]:
    """ Searches Jisho, and returns definition data as a `dict`. """
    query_url = utils.urlescape(query)
    jisho_endpoint = 'http://jisho.org/api/v1/search/words?keyword={}'
    async with session.get(jisho_endpoint.format(query_url)) as resp:
        data = await resp.json()

        # failed, or no data
        if data['meta']['status'] != 200 or not data['data']:
            return None

        return data['data']


class Utility(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        if hasattr(dog_config, 'owm_key'):
            self.owm = pyowm.OWM(dog_config.owm_key)
        else:
            self.owm = None

    @commands.command()
    @commands.is_owner()
    async def exception(self, ctx, message: str = 'Test exception'):
        """ Creates an exception. """
        raise RuntimeError(message)

    @commands.command()
    async def define(self, ctx, *, word: str):
        """ Defines a word. """
        api_base = 'https://od-api.oxforddictionaries.com/api/v1'

        # request headers
        headers = {
            'app_id': dog_config.oxford_creds['application_id'],
            'app_key': dog_config.oxford_creds['application_key']
        }

        search_params = {
            'q': word,
            'limit': 3
        }

        # search word
        async with ctx.bot.session.get(api_base + '/search/en', params=search_params, headers=headers) as resp:
            results = (await resp.json())['results']
            if not results:
                # empty
                return await ctx.send('Word not found.')
            word_id = results[0]['id']

        # get word definition
        async with ctx.bot.session.get(api_base + f'/entries/en/{utils.urlescape(word_id)}', headers=headers) as resp:
            # grab results
            try:
                results = (await resp.json())['results']
            except aiohttp.ClientError:
                return await ctx.send('Hmm, I couldn\'t decode the results from Oxford.')
            lexical = results[0]['lexicalEntries'][0]

            if 'pronunciations' in lexical:
                pronun = ','.join([p['phoneticSpelling'] for p in lexical['pronunciations'] if 'phoneticSpelling' in p])
            else:
                pronun = ''

        # combine senses
        definitions = []
        examples = []
        def add_sense(sense):
            nonlocal definitions, examples
            if not 'definitions' in sense:
                return  # don't bother
            if 'definitions' in sense:
                definitions += sense['definitions']
            if 'examples' in sense:
                examples += sense['examples']

        for entry in lexical['entries']:
            if 'senses' not in entry:
                continue
            for sense in entry['senses']:
                add_sense(sense)
                if 'subsenses' in sense:
                    for subsense in sense['subsenses']:
                        add_sense(subsense)

        def_text = '\n'.join([f'\N{BULLET} {defn}' for defn in definitions])
        embed = discord.Embed(title=utils.truncate(lexical['text'], 256), description=utils.truncate(def_text, 2048))
        if examples:
            examples_text = '\n'.join([f'\N{BULLET} {example["text"]}' for example in examples])
            embed.add_field(name='Examples', value=utils.truncate(examples_text, 1024))
        embed.set_footer(text=pronun)
        await ctx.send(embed=embed)

    @define.error
    async def define_error(self, ctx, err):
        if isinstance(err, commands.DisabledCommand) or isinstance(err, commands.CheckFailure):
            return
        await ctx.send('An error has occurred.')

    @commands.command()
    async def weather(self, ctx, *, place: str):
        """ Checks the weather for some place. """
        if not self.owm:
            return

        try:
            obv = await ctx.bot.loop.run_in_executor(None, self.owm.weather_at_place, place)
        except pyowm.exceptions.not_found_error.NotFoundError:
            return await ctx.send('Place not found.')
        except TypeError:
            return await ctx.send('OpenWeatherMap gave me bogus information.')
        weather = await ctx.bot.loop.run_in_executor(None, obv.get_weather)

        embed = discord.Embed(title=weather.get_status())

        c = weather.get_temperature('celsius')
        f = weather.get_temperature('fahrenheit')
        temp = (f'{c["temp"]}°C ({c["temp_min"]}°C \N{EM DASH} {c["temp_max"]}°C)\n'
                f'{f["temp"]}°F ({f["temp_min"]}°F \N{EM DASH} {f["temp_max"]}°F)')
        embed.add_field(name='Temperature', value=temp)

        embed.add_field(name='Sunset', value=weather.get_sunset_time('iso'))
        embed.add_field(name='Cloud Coverage', value=f'{weather.get_clouds()}%', inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def poll(self, ctx, conclude_on_votes: int, title: str, *choices: str):
        """
        Creates a poll.

        `conclude_on_votes` specifies how many votes are required in order to end the poll. Users
        vote on the poll with reactions.
        """

        if not ctx.guild:
            return

        if len(choices) > 9:
            raise commands.errors.BadArgument('Too many choices! There is a maximum of nine.')

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

            if isinstance(reaction.emoji, discord.Emoji):
                # ignore custom emoji
                continue

            # check if it was a number emoji
            if len(reaction.emoji) != 2 or reaction.emoji[1] != '\u20e3':
                logger.debug('Ignoring invalid poll reaction -- reaction=%s, len(reaction)=%d',
                             reaction.emoji, len(reaction.emoji))
                continue

            result_index = int(reaction.emoji[0]) - 1
            if result_index < 0 or result_index > len(poll_results) - 1:
                logger.debug('Ignoring incorrect poll number reaction.')
                continue
            poll_results[result_index] += 1
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
            if 'english_definitions' in sense:
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

    @commands.command()
    async def jumbo(self, ctx, emoji: converters.FormattedCustomEmoji):
        """
        Views a custom emoji at 100% resolution.

        This command ONLY supports custom emojis.
        """

        # get emoji id
        emoji_cdn = 'https://cdn.discordapp.com/emojis/{}.png'.format(emoji.id)

        # create wrapping embed
        wrapper_embed = discord.Embed(title=f':{emoji.name}: \N{EM DASH} `{emoji.id}`')
        wrapper_embed.set_image(url=emoji_cdn)

        # send
        await ctx.send(embed=wrapper_embed)

    @commands.command()
    @commands.guild_only()
    async def default_channel(self, ctx):
        """ Shows you the default channel. """
        await ctx.send(ctx.guild.default_channel.mention)

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


def setup(bot):
    bot.add_cog(Utility(bot))
