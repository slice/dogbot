import discord
from discord.ext.commands import is_owner
from lifesaver.bot import Cog, Context, command, group


class Administration(Cog):
    @group(hidden=True, invoke_without_command=True)
    @is_owner()
    async def blacklist(self, ctx: Context, user: discord.User, *, reason=None):
        """Blacklist someone from using the bot."""
        await self.bot.blacklisted_storage.put(user.id, reason)
        await ctx.ok()

    @blacklist.command()
    @is_owner()
    async def stats(self, ctx: Context):
        """Views blacklist statistics."""
        amount = len(self.bot.blacklisted_storage.all())
        await ctx.send(f'User(s) blocked: **{amount}**')

    @blacklist.command()
    @is_owner()
    async def reason(self, ctx: Context, user: discord.User):
        """Views the reason for someone's blacklisting."""
        if user.id not in self.bot.blacklisted_storage:
            await ctx.send(f'{user} is not blacklisted.')
            return

        reason = self.bot.blacklisted_storage.get(user.id)
        if not reason:
            await ctx.send(f'{user} is blacklisted for no reason.')
        else:
            await ctx.send(f'{user} is blacklisted for reason: {reason}')

    @command(hidden=True)
    @is_owner()
    async def unblacklist(self, ctx: Context, user: discord.User):
        """Unblacklists someone from using the bot."""
        try:
            await self.bot.blacklisted_storage.delete(user.id)
        except KeyError:
            pass
        await ctx.ok()


def setup(bot):
    bot.add_cog(Administration(bot))
