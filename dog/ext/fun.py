"""
Contains fun commands that don't serve any purpose!
"""

import logging
import tempfile
from collections import namedtuple
from io import BytesIO
from typing import Any, Dict

import aiohttp
import discord
from discord.ext import commands
from PIL import Image, ImageEnhance

from dog import Cog
from dog.core import checks, utils

SHIBE_ENDPOINT = 'http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=true'
DOGFACTS_ENDPOINT = 'https://dog-api.kinduff.com/api/facts'

logger = logging.getLogger(__name__)


async def _get(session: aiohttp.ClientSession, url: str) -> aiohttp.ClientResponse:
    async with session.get(url) as response:
        return response


async def _get_bytesio(session: aiohttp.ClientSession, url: str) -> BytesIO:
    # can't use _get for some reason
    async with session.get(url) as resp:
        return BytesIO(await resp.read())


async def _get_json(session: aiohttp.ClientSession, url: str) -> Dict[Any, Any]:
    resp = await _get(session, url)
    return await resp.json()

UrbanDefinition = namedtuple('UrbanDefinition', [
    'word', 'definition', 'thumbs_up', 'thumbs_down', 'example',
    'permalink', 'author', 'defid', 'current_vote'
])


async def urban(session: aiohttp.ClientSession, word: str) -> UrbanDefinition:
    UD_ENDPOINT = 'http://api.urbandictionary.com/v0/define?term={}'
    async with session.get(UD_ENDPOINT.format(utils.urlescape(word))) as resp:
        json = await resp.json()
        if json['result_type'] == 'no_results':
            return None
        else:
            result = json['list'][0]
            return UrbanDefinition(**result)


class Fun(Cog):
    @commands.command()
    @commands.guild_only()
    @checks.config_is_set('woof_command_enabled')
    async def woof(self, ctx):
        """ Sample command. """
        await ctx.send('Woof!')

    def make_urban_embed(self, urban: UrbanDefinition) -> discord.Embed:
        embed = discord.Embed(title=urban.word, description=urban.definition)
        embed.add_field(name='Example', value=urban.example, inline=False)
        embed.add_field(name='\N{THUMBS UP SIGN}', value=utils.commas(urban.thumbs_up))
        embed.add_field(name='\N{THUMBS DOWN SIGN}', value=utils.commas(urban.thumbs_down))
        return embed

    async def rps_is_being_excluded(self, who: discord.User) -> bool:
        """ Returns whether a person is being excluded from RPS. """
        return await self.bot.pg.fetchrow('SELECT * FROM rps_exclusions WHERE user_id = $1',
                                          who.id) is not None

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def rps(self, ctx, opponent: discord.Member):
        """ Fights someone in rock, paper, scissors! """
        if await self.rps_is_being_excluded(opponent):
            return await ctx.send('That person chose to be excluded from RPS.')

        progress_message = await ctx.send('Waiting for {} to choose...'.format(ctx.author.mention))

        def rps_check(who: discord.Member):
            """ Returns a check that checks for a DM from a person. """
            def rps_predicate(reaction, adder):
                is_original_person = adder.id == who.id
                is_in_dm = isinstance(reaction.message.channel, discord.DMChannel)
                return is_original_person and is_in_dm
            return rps_predicate

        async def rps_get_choice(who: discord.Member) -> str:
            """ Sends someone the instructional message, then waits for a choice. """
            desc = ('React with what you want to play. If you don\'t wish to be challenged to RPS, '
                    'type `d?rps exclude` to exclude yourself from future games.')
            embed = discord.Embed(title='Rock, paper, scissors!',
                                  description=desc)
            msg = await who.send(embed=embed)
            translate = {
                '\N{NEW MOON SYMBOL}': 'rock',
                '\N{NEWSPAPER}': 'paper',
                '\N{BLACK SCISSORS}': 'scissors'
            }
            for emoji in translate:
                await msg.add_reaction(emoji)
            while True:
                reaction, _ = await self.bot.wait_for('reaction_add', check=rps_check(who))
                if reaction.emoji in translate:
                    return translate[reaction.emoji]

        # get their choices
        initiator_choice = await rps_get_choice(ctx.author)
        await progress_message.edit(content='Waiting for the opponent ({}) to choose...'.format(
            opponent))
        opponent_choice = await rps_get_choice(opponent)

        # delete the original message, because edited mentions do not notify
        # the user
        await progress_message.delete()

        # check if it was a tie
        if initiator_choice == opponent_choice:
            fmt = '{}, {}: It was a tie! You both chose {}.'
            return await ctx.send(fmt.format(ctx.author.mention, opponent.mention,
                                             initiator_choice))

        async def inform_winner(who: discord.Member, beats_left: str, beats_right: str):
            fmt = '{}, {}: :first_place: {} was the winner! {} beats {}.'
            return await ctx.send(fmt.format(ctx.author.mention, opponent.mention, who.mention,
                                             beats_left.title(), beats_right))

        def beats(weapon: str, target: str) -> bool:
            """ Rock, paper, scissors defeat checker. """
            if weapon == 'paper':
                return target == 'rock'
            elif weapon == 'rock':
                return target == 'scissors'
            elif weapon == 'scissors':
                return target == 'paper'

        if beats(initiator_choice, opponent_choice):
            await inform_winner(ctx.author, initiator_choice, opponent_choice)
        else:
            await inform_winner(opponent, opponent_choice, initiator_choice)

    @rps.command(name='exclude')
    async def rps_exclude(self, ctx):
        """ Excludes yourself from being challenged. """
        if await self.rps_is_being_excluded(ctx.author):
            return await ctx.send('You are already excluded from RPS.')

        await self.bot.pg.execute('INSERT INTO rps_exclusions VALUES ($1)', ctx.author.id)
        await self.bot.ok(ctx)

    @rps.command(name='include')
    async def rps_include(self, ctx):
        """ Includes yourself in being challenged. """
        if not await self.rps_is_being_excluded(ctx.author):
            return await ctx.send('You are not being excluded from RPS.')

        await self.bot.pg.execute('DELETE FROM rps_exclusions WHERE user_id = $1', ctx.author.id)
        await self.bot.ok(ctx)

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def urban(self, ctx, *, word: str):
        """ Finds UrbanDictionary definitions. """
        async with ctx.channel.typing():
            result = await urban(self.bot.session, word)
            if not result:
                await ctx.send('No results!')
            else:
                await ctx.send(embed=self.make_urban_embed(result))

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def shibe(self, ctx):
        """
        Woof!

        Grabs a random Shiba Inu picture from shibe.online.
        """
        async with ctx.channel.typing():
            try:
                resp = await _get_json(self.bot.session, SHIBE_ENDPOINT)
            except aiohttp.ClientError:
                return await ctx.send('\N{DISAPPOINTED FACE} Failed to contact the shibe API.')
            dog_url = resp[0]
            await ctx.send(embed=discord.Embed().set_image(url=dog_url))

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def wacky(self, ctx, who: discord.Member=None):
        """ Turns your avatar into... """
        if not who:
            who = ctx.message.author
        logger.info('wacky: get: %s', who.avatar_url)

        async with ctx.channel.typing():
            avatar_data = await _get_bytesio(self.bot.session, who.avatar_url_as(format='png'))

            logger.info('wacky: enhancing...')
            im = Image.open(avatar_data)
            converter = ImageEnhance.Color(im)
            im = converter.enhance(50)

            # ugh
            _temp = next(tempfile._get_candidate_names())
            _path = f'{tempfile._get_default_tempdir()}/{_temp}'

            logger.info('wacky: saving...')
            im.save(_path, format='jpeg', quality=0)
            logger.info('wacky: sending...')
            await ctx.send(file=discord.File(_path, 'result.jpg'))

            # close images
            avatar_data.close()

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def dogfact(self, ctx):
        """ Returns a random dog fact. """
        async with ctx.channel.typing():
            try:
                facts = await _get_json(self.bot.session, DOGFACTS_ENDPOINT)
            except aiohttp.ClientError:
                return await ctx.send('\N{DISAPPOINTED FACE} Failed to get a dog fact.')
            if not facts['success']:
                await ctx.send('I couldn\'t contact the Dog Facts API.')
                return
            await ctx.send(facts['facts'][0])


def setup(bot):
    bot.add_cog(Fun(bot))
