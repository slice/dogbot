import discord
from discord.ext import commands

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
