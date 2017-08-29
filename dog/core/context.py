import discord
from discord.ext import commands

from dog.core import utils


class DogbotContext(commands.Context):
    async def ok(self, emoji: str = '\N{SQUARED OK}'):
        """
        Adds a reaction to the command message, or sends it to the channel if
        we can't add reactions. This should be used as feedback to commands,
        just like how most bots send out `:ok_hand:` when a command completes
        successfully.
        """
        try:
            await self.message.add_reaction(emoji)
        except discord.Forbidden:
            # can't add reactions
            await self.send(emoji)
        except discord.NotFound:
            # the command message got deleted somehow
            pass

    def acquire(self):
        return self.bot.pgpool.acquire()

    @property
    def red_tick(self):
        """
        The same as DogBot.red_tick, but it automatically returns the Unicode equivalent if we can't use external
        emoji.
        """
        return self.bot.red_tick if self.guild.me.guild_permissions.external_emojis else '\N{CROSS MARK}'

    @property
    def green_tick(self):
        """
        The same as DogBot.green_tick, but it automatically returns the Unicode equivalent if we can't use external
        emoji.
        """
        return self.bot.green_tick if self.guild.me.guild_permissions.external_emojis else \
            '\N{WHITE HEAVY CHECK MARK}'

    def tick(self, *args, **kwargs) -> str:
        """
        The same as DogBot.tick, but the ``guild`` kwarg is automatically supplied.
        """
        return self.bot.tick(*args, **kwargs, guild=self.guild)

    async def preferred_lang(self) -> str:
        """
        Returns the preferred language for this command context.
        """

        # user-preferred lang takes precedence
        user_lang = await self.bot.redis.get(f'i18n:user:{self.author.id}:lang')
        if user_lang:
            return user_lang.decode()

        # guild lang then comes
        if self.guild:
            guild_lang = await self.bot.redis.get(f'i18n:guild:{self.guild.id}:lang')
            if guild_lang:
                return guild_lang.decode()

        # en-us by default
        return 'en-US'

    async def _(self, key: str, *args, **kwargs):
        val = self.bot.lang(key, await self.preferred_lang())
        return val if (not args and not kwargs) else val.format(*args, **kwargs)

    async def confirm(self, *, title: str, description: str, confirm_cancellation=False):
        """ Confirms something. """
        embed = discord.Embed(color=discord.Color.red(), title=title, description=description)
        confirmation = await self.send(embed=embed)

        for tick in (self.bot.tick(tick_type, raw=True, guild=self.guild) for tick_type in ('green', 'red')):
            await confirmation.add_reaction(tick)

        while True:
            def check(reaction: discord.Reaction, adder: discord.User) -> bool:
                return adder == self.message.author and reaction.message.id == confirmation.id

            # wait for a reaction
            reaction, adder = await self.bot.wait_for('reaction_add', check=check)

            # ignore regular emoji
            if isinstance(reaction.emoji, str):
                continue

            if reaction.emoji.id == 318595000311087105:
                await confirmation.delete()
                return True
            elif reaction.emoji.id == 318595010385674240:
                await confirmation.delete()
                if confirm_cancellation:
                    await self.send('Operation cancelled.')
                return False

    async def wait_for_response(self):
        """
        Waits for a message response from the message author, then returns the
        new message.

        The message we are waiting for will only be accepted if it was sent by
        the original command invoker, and it was sent in the same channel as
        the command message.
        """

        def check(m):
            if isinstance(m.channel, discord.DMChannel):
                # accept any message, because we are in a dm
                return True
            return m.channel.id == self.channel.id and m.author == self.author

        return await self.bot.wait_for('message', check=check)

    async def gatekeeper_enabled(self) -> bool:
        """ Returns whether Gatekeeper is enabled in this context. """

        # not in a guild
        if not self.guild:
            return

        return await self.bot.redis.exists(f'gatekeeper:{self.guild.id}:enabled')

    async def pick_from_list(self, choices: 'List[Any]', *, delete_after_choice=False) -> 'Any':
        """ Shows the user a list of items to pick from. Returns the picked item. """
        # format list of stuff
        choices_list = utils.format_list(choices)

        # send list of stuff
        choices_message = await self.send('Pick one, or send `cancel`.\n\n' + choices_list)
        remaining_tries = 3
        picked = None

        while True:
            if remaining_tries <= 0:
                await self.send('You ran out of tries, I give up!')
                return None

            # wait for a message
            msg = await self.wait_for_response()

            # user wants to cancel?
            if msg.content == 'cancel':
                await self.send('Canceled selection.')
                break

            try:
                chosen_index = int(msg.content) - 1
            except ValueError:
                # they didn't enter a valid number
                await self.send('That wasn\'t a number! Send a message that '
                                'solely contains the number of the item that '
                                'you want.')
                remaining_tries -= 1
                continue

            if chosen_index < 0 or chosen_index > len(choices) - 1:
                # out of range
                await self.send('Invalid choice! Send a message that solely '
                                'contains the number of the item that you '
                                'want.')
                remaining_tries -= 1
            else:
                # they chose correctly
                picked = choices[chosen_index]
                if delete_after_choice:
                    await choices_message.delete()
                    await msg.delete()
                break

        return picked
