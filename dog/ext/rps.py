"""
A rock, paper, scissors extension.
"""

import logging
import discord
from discord.ext import commands
from dog import Cog

log = logging.getLogger(__name__)


class RPS(Cog):
    async def rps_is_being_excluded(self, who: discord.Member) -> bool:
        """ Returns whether a person is being excluded from RPS. """
        async with self.bot.pgpool.acquire() as conn:
            return await conn.fetchrow('SELECT * FROM rps_exclusions WHERE user_id = $1', who.id) is not None

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def rps(self, ctx, opponent: discord.Member):
        """ Fights someone in rock, paper, scissors! """
        if await self.rps_is_being_excluded(opponent):
            return await ctx.send('That person chose to be excluded from RPS.')

        progress_message = await ctx.send('Waiting for {} to choose...'.format(ctx.author))

        def rps_check(who: discord.Member):
            """ Returns a check that checks for a DM from a person. """

            def rps_predicate(reaction, adder):
                is_original_person = adder == who
                is_in_dm = isinstance(reaction.message.channel, discord.DMChannel)
                return is_original_person and is_in_dm

            return rps_predicate

        async def rps_get_choice(who: discord.Member) -> str:
            """ Sends someone the instructional message, then waits for a choice. """
            desc = ('React with what you want to play. If you don\'t wish to be challenged to RPS, '
                    'type `d?rps exclude` to exclude yourself from being challenged.')
            desc_prefix = ('You have been challenged by {}!\n\n'.format(ctx.author.mention)
                if who == opponent else 'Because you initiated the game, you go first.\n\n')
            embed = discord.Embed(title='Rock, paper, scissors!',
                                  description=desc_prefix + desc)
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
        try:
            initiator_choice = await rps_get_choice(ctx.author)
            await progress_message.edit(content='Waiting for the opponent ({}) to choose...'.format(
                opponent))
            opponent_choice = await rps_get_choice(opponent)
        except discord.Forbidden:
            return await progress_message.edit(content='I failed to DM the initiator or the opponent.')

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

        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('INSERT INTO rps_exclusions VALUES ($1)', ctx.author.id)
        await self.bot.ok(ctx)

    @rps.command(name='include')
    async def rps_include(self, ctx):
        """ Includes yourself in being challenged. """
        if not await self.rps_is_being_excluded(ctx.author):
            return await ctx.send('You are not being excluded from RPS.')

        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM rps_exclusions WHERE user_id = $1', ctx.author.id)
        await self.bot.ok(ctx)


def setup(bot):
    bot.add_cog(RPS(bot))
