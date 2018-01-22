import asyncio
import logging
from typing import Optional

from collections import defaultdict

import enum
from random import randint, choice

import discord
from discord.ext.commands import guild_only
from lifesaver.bot import Cog, Context, command


class MafiaGameState(enum.Enum):
    WAITING = enum.auto()
    STARTED = enum.auto()


class MafiaGame:
    def __init__(self, bot, *, master: discord.Member, channel: discord.TextChannel):
        self.bot = bot
        # the person who started the game
        self.master = master
        # the channel the lobby started in
        self.channel = channel
        # the main game channel where both mafia and town can talk
        self.game_channel: Optional[discord.TextChannel] = None
        # guild where the game started
        self.guild: discord.Guild = channel.guild
        # set of alive players
        self.players = {master}
        # set of all players who joined at the beginning
        self.participants = set()
        # set of alive mafia
        self.mafia = set()
        # mafia text channel
        self.mafia_chat: Optional[discord.TextChannel] = None
        # current game state (unused)
        self.state = MafiaGameState.WAITING
        # day counter
        self.day = 1
        # currently in daytime?
        self.daytime = True
        # dict of hanging votes during the daytime:
        # key: user id of person to hang - value: list of user ids who voted to hang that person
        # 1: [2, 3] - users 2 and 3 are voting for 1 to be hanged
        self.hanging_votes = defaultdict(list)
        # victim that will be killed tonight, decided by mafia. can be none if they decide to spare.
        self.victim_tonight: Optional[discord.Member] = None
        self.log = logging.getLogger(__name__)

    # number of players required before game autostarts
    REQUIRED_PLAYERS = 6
    # debug mode: arbitrarily shorten some wait times
    DEBUG = False

    async def gather_players(self):
        m = await self.channel.send('Created a lobby. Join by clicking \N{RAISED HAND}!')
        await m.add_reaction('\N{RAISED HAND}')

        def reaction_check(r, u):
            return r.message.id == m.id and not u.bot

        while True:
            reaction, user = await self.bot.wait_for('reaction_add', check=reaction_check)

            # ignore custom emoji reactions
            if not isinstance(reaction.emoji, str):
                continue

            if reaction.emoji == '\N{RAISED HAND}':
                self.players.add(user)

                # send notice that someone has joined
                await self.channel.send(
                    f'**{user}** has joined the lobby. There are now {len(self.players)} player(s) in the lobby.'
                    f' {self.REQUIRED_PLAYERS - len(self.players)} more player(s) are/is required for the game to start.'
                )

                # update lobby message with list of active players
                players_formatted = ', '.join(str(player) for player in self.players)
                await m.edit(
                    content='Join by clicking \N{RAISED HAND}! Current players: ' + players_formatted
                )

            if len(self.players) == self.REQUIRED_PLAYERS or (reaction.emoji == '\N{OK HAND SIGN}' and user == self.master):
                if len(self.players) < 3:
                    await self.channel.send("Override failed. At least 3 players are required for a game.")
                    continue
                await m.edit(content='Game started!')
                try:
                    await m.clear_reactions()
                except discord.HTTPException:
                    pass
                await self.channel.send('Okay, game starting!')
                break

        # players set will be modified as the game goes on, so let's keep a set of participants
        # when we alltalk later
        self.participants = self.players.copy()
        overwrites = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for player in self.players:
            overwrites[player] = discord.PermissionOverwrite(read_messages=True)
        self.game_channel = await self.guild.create_text_channel(
            f'd-mafia-game-{randint(0, 10000) + 10000}', overwrites=overwrites
        )

    async def pick_mafia(self):
        first_mafia = choice(list(self.players))
        second_mafia = choice(list(self.players.difference({first_mafia})))
        self.log.info('Picked 2 mafia. %s, %s', first_mafia, second_mafia)
        self.mafia = {first_mafia, second_mafia}

        rid = randint(0, 10000) + 10000
        self.mafia_chat = await self.guild.create_text_channel(f'd-mafia-chat-{rid}', overwrites={
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            first_mafia: discord.PermissionOverwrite(read_messages=True),
            second_mafia: discord.PermissionOverwrite(read_messages=True),
            self.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        })
        await self.mafia_chat.send(
            f'{first_mafia.mention}, {second_mafia.mention}: Greet each other, mafia! Here you may coordinate with '
            'your evil partner.'
        )

    async def notify_roles(self):
        for player in self.players:
            # mafia are notified when they are picked <3
            if player not in self.mafia:
                await player.send(
                    f'**You are innocent!** Your goal is to hang the mafia. Now go to: {self.game_channel.mention}, '
                    "that's where the game will unfold."
                )

    async def pick_victim(self):
        while True:
            message = await self.bot.wait_for(
                'message',
                check=lambda m: m.channel == self.mafia_chat and m.author in self.mafia and m.author in self.players
            )
            if message.content.startswith('!kill '):
                target_name = message.content[len('!kill '):]
                target = discord.utils.find(lambda player: player.name.lower() == target_name.lower() or player.mention == target_name, self.players)
                if not target or target in self.mafia:
                    await self.mafia_chat.send(f'{message.author.mention}: Invalid choice.')
                    continue
                self.victim_tonight = target
                await self.mafia_chat.send(
                    f"Okay, **{target}** will be killed tonight."
                )

    async def alltalk(self):
        # let all people who joined speak again at the end because we're nice <3
        for participant in self.participants:
            self.log.info('Alltalk: Allowing %s to speak in #%s.', participant, self.game_channel.name)
            await self.game_channel.set_permissions(participant, read_messages=True, send_messages=True)

    async def gather_hanging_votes(self):
        # TODO: these are bad
        def has_voted(voter):
            for target_id, voter_ids in self.hanging_votes.items():
                if voter.id in voter_ids:
                    return True
            return False

        def get_vote(voter):
            for target_id, voter_ids in self.hanging_votes.items():
                if voter.id in voter_ids:
                    return target_id

        while True:
            message = await self.bot.wait_for(
                'message',
                check=lambda m: m.channel == self.game_channel and m.author in self.players
            )

            if not message.content.startswith('!vote '):
                continue

            try:
                target_name = message.content[len('!vote '):]
                target = discord.utils.find(lambda player: player.name.lower() == target_name.lower() or player.mention == target_name, self.players)
                if not target:
                    await self.game_channel.send(f'{message.author.mention}: Invalid choice.')
                    continue
                if target == message.author:
                    await self.game_channel.send(f'{message.author.mention}: Are you trying to commit suicide? No.')
                    continue
                self.log.info('Received VALID !vote command: %s wants to hang %s.', message.author, target)
                if has_voted(message.author):
                    previous_target = get_vote(message.author)
                    if previous_target == target.id:
                        # voting for same person?
                        self.log.info('Detected duplicate vote (%s to %s), discarding.', message.author, target)
                        await self.game_channel.send(f'{message.author.mention}: You already voted for that person.')
                        continue
                    self.log.info('%s has already voted for %d, removing their vote.', message.author, previous_target)
                    self.hanging_votes[previous_target].remove(message.author.id)
                self.log.info("Registering %s's vote to hang %s.", message.author, target)
                # because this defaultdict gave me a keyerror.
                self.log.info('hanging_votes: (%s): %s', type(self.hanging_votes).__name__, repr(self.hanging_votes))
                self.hanging_votes[target.id].append(message.author.id)
                await self.game_channel.send(
                    f'{message.author} has voted for {target} to be hanged.\n\n' +
                    '\n'.join(f'<@{key}>: {len(value)} vote(s)' for key, value in self.hanging_votes.items() if len(value) != 0)
                )
            except Exception:
                self.log.exception('Error has occurred while processing votes:')

    async def lock(self):
        await self.game_channel.set_permissions(self.guild.default_role, send_messages=False)

    async def unlock(self):
        await self.game_channel.set_permissions(self.guild.default_role, send_messages=None)

    async def game_over(self, *, mafia_won: bool):
        if mafia_won:
            mafia_alive = ', '.join(mafia.mention for mafia in self.mafia)
            await self.game_channel.send(f'**Currently Alive Mafia:** {mafia_alive}')
        else:
            townies_alive = ', '.join(player.mention for player in self.players if player not in self.mafia)
            await self.game_channel.send(f'**Currently Alive Town:** {townies_alive}')

        await asyncio.sleep(2.0)
        await self.alltalk()
        await asyncio.sleep(8.0)

    async def game_loop(self):
        mentions = ', '.join(player.mention for player in self.players)
        await self.game_channel.send(f'{mentions}: The main game will be conducted here! Make sure to have fun!')
        await asyncio.sleep(5.0)

        while True:
            # send current day/daytime state to players
            emoji = '\N{BLACK SUN WITH RAYS}' if self.daytime else '\N{NIGHT WITH STARS}'
            await self.game_channel.send(f'{emoji} **{"Day" if self.daytime else "Night"} {self.day}** {emoji}')
            self.log.info('>> Time progression. Day %d, %s.', self.day, 'day' if self.daytime else 'night')

            # if we are on D1, send some directions and just move onto N1.
            if self.daytime and self.day == 1:
                self.log.info('Tutorial section, this will take a bit.')
                await self.game_channel.send(
                    '**Welcome to the game!**\n\n'
                    f'There are {len(self.mafia)} mafia hiding within a town of innocents. '
                    'If you are an innocent, your goal is to lynch the mafia. '
                    'If you are a mafia, your goal is to work with your partner to wipe out the innocents before '
                    'they find out about you!'
                )
                await asyncio.sleep(3 if self.DEBUG else 15)
                self.daytime = False
                continue

            if self.daytime:
                if self.victim_tonight:
                    self.players.remove(self.victim_tonight)
                    await self.game_channel.set_permissions(self.victim_tonight, read_messages=True, send_messages=False)
                    await self.game_channel.send(
                        f'**{self.victim_tonight}** was unfortunately found dead in their home last night.'
                    )
                    await asyncio.sleep(3.0)
                    await self.game_channel.send('They were **innocent.**')
                    await asyncio.sleep(5.0)
                    self.victim_tonight = None

                    if all(player in self.mafia for player in self.players):
                        await self.game_channel.send('\U0001f52a **Mafia win!** \U0001f52a')
                        await self.game_over(mafia_won=True)
                        break

                votes_required = round(len(self.players) / 3)
                self.log.info('It is now discussion time. (%d votes required for hanging.)', votes_required)
                await self.game_channel.send(
                    'Discussion time! Alive town members can now vote who to hang. To vote, type `!vote <username>` in '
                    f'chat. You have 30 seconds, and {votes_required} vote(s) are required to hang someone.'

                    '\n\n**Alive Players:**\n' +
                    '\n'.join(f'- {user.name}' for user in self.players)
                )

                # gather hanging votes.
                task = self.bot.loop.create_task(self.gather_hanging_votes())
                await asyncio.sleep(20.0)
                await self.game_channel.send('**10 seconds of voting remaining!**')
                await asyncio.sleep(5.0)
                await self.game_channel.send('**5 seconds of voting remaining!**')
                await asyncio.sleep(5.0)
                task.cancel()

                self.hanging_votes = {target_id: len(votes) for target_id, votes in self.hanging_votes.items()}
                self.log.info('Hanging votes (postprocessed): %s', self.hanging_votes)
                sorted_votes = sorted(list(self.hanging_votes.items()), key=lambda e: e[1], reverse=True)
                vote_board = list(filter(
                    lambda e: e[1] >= votes_required, sorted_votes
                ))
                self.log.info('Final voting board: %s', vote_board)
                if not vote_board:
                    await self.game_channel.send('A verdict was not reached in time. Oh well!')
                else:
                    hanged = discord.utils.get(self.players, id=vote_board[0][0])
                    await self.lock()
                    await self.game_channel.set_permissions(hanged, read_messages=True, send_messages=True)
                    await self.game_channel.send(
                        f'\N{SKULL} {hanged.mention}, you have been voted to be hanged. Do you have any last words '
                        'before your death? You have 15 seconds.'
                    )
                    await asyncio.sleep(3.0 if self.DEBUG else 15.0)
                    await self.game_channel.set_permissions(hanged, read_messages=True, send_messages=False)
                    await self.unlock()
                    await self.game_channel.send(f'\N{SKULL} **Rest in peace, {hanged}. You will be missed.** \N{SKULL}')
                    self.players.remove(hanged)
                    await asyncio.sleep(3)
                    was_mafia = hanged in self.mafia
                    if was_mafia:
                        self.mafia.remove(hanged)
                        await self.mafia_chat.set_permissions(hanged, read_messages=True, send_messages=False)
                    await self.game_channel.send(f'{hanged} was **{"mafia" if was_mafia else "innocent"}.**')
                    await asyncio.sleep(5)

                # reset
                self.hanging_votes = defaultdict(list)
            else:
                await self.game_channel.send(
                    "Night time! Sleep tight, and don't let the bed bugs bite!"
                )
                await self.lock()
                alive_mafia = ', '.join(mafia.mention for mafia in self.mafia)
                await self.mafia_chat.send(
                    f"{alive_mafia}: It's time to kill! \N{HOCHO} Discuss someone to kill, then type "
                    "`!kill <username>` in chat when you have decided on someone to stab. You have 30 seconds! "
                    "Alternatively, you can do nothing to stay low. "
                    "Once you choose someone to kill, you can't go back to killing nobody!\n\n" +
                    '\n'.join(f'- {player.name}' for player in self.players if player not in self.mafia)
                )
                task = self.bot.loop.create_task(self.pick_victim())
                await asyncio.sleep(2.0 if self.DEBUG else 30.0)
                task.cancel()
                await self.unlock()

            if len(self.mafia) == 0:
                await self.game_channel.send('\U0001f64f **Innocents win!** \U0001f64f')
                await self.game_over(mafia_won=False)
                break
            elif all(player in self.mafia for player in self.players):
                await self.game_channel.send('\U0001f52a **Mafia win!** \U0001f52a')
                await self.game_over(mafia_won=True)
                break

            if not self.daytime:
                # it's night, so move onto next
                self.day += 1
                self.daytime = True
            else:
                # it's day, so move onto night
                self.daytime = False

    async def start(self):
        self.log.info('Game started. Now gathering players (minimum of %d).', self.REQUIRED_PLAYERS)
        await self.gather_players()
        await self.pick_mafia()
        await self.notify_roles()
        await asyncio.sleep(5.0)
        self.state = MafiaGameState.STARTED
        await self.game_loop()

        await self.game_channel.send('Did you have fun? This channel will self destruct in **10 seconds.**')
        await asyncio.sleep(10.0)

        await self.mafia_chat.delete()
        await self.game_channel.delete()
        await self.channel.send('Game over!')


class Mafia(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessions = set()

    @command()
    @guild_only()
    async def mafia(self, ctx: Context):
        if ctx.channel.id in self.sessions:
            await ctx.send('Game already started here.')
            return
        self.sessions.add(ctx.channel.id)
        game = MafiaGame(ctx.bot, master=ctx.author, channel=ctx.channel)
        await game.start()
        self.sessions.remove(ctx.channel.id)


def setup(bot):
    bot.add_cog(Mafia(bot))
