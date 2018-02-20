import aiohttp
import discord
from discord.ext.commands import is_owner
from lifesaver.bot import Bot, command, Context
from lifesaver.bot.storage import AsyncJSONStorage


class Dogbot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.load_all()
        self.add_command(self.blacklist)
        self.add_command(self.unblacklist)
        self.blocked = AsyncJSONStorage('blacklisted_users.json', loop=self.loop)

    async def on_message(self, message: discord.Message):
        if str(message.author.id) in self.blocked.all():
            return
        await super().on_message(message)

    @command(hidden=True)
    @is_owner()
    async def blacklist(self, ctx: Context, user: discord.User, *, reason=None):
        """Blacklist someone from using the bot."""
        await self.blocked.put(user.id, reason)
        await ctx.ok()

    @command(hidden=True)
    @is_owner()
    async def unblacklist(self, ctx: Context, user: discord.User):
        """Unblacklist someone from using the bot."""
        try:
            await self.blocked.delete(user.id)
        except KeyError:
            pass
        await ctx.ok()
