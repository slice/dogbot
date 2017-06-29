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

            # don't choke when using a selfbot
            if msg.author == self.bot.user and msg.content.startswith('Pick one, or send'):
                continue

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

