from discord.ext.commands import command

from dog import Cog
from dog.core.checks import is_bot_admin


class State(Cog):
    @command(hidden=True)
    @is_bot_admin()
    async def sync(self, ctx):
        """Syncs the bot's state."""
        async with ctx.acquire() as conn:
            msg = await ctx.send('Syncing...')

            user_sql = 'INSERT INTO users (id, is_global_admin) VALUES ($1, $2) ON CONFLICT DO NOTHING'
            guild_sql = 'INSERT INTO guilds (id, owner) VALUES ($1, $2) ON CONFLICT DO NOTHING'

            for user in ctx.bot.users:
                await conn.execute(user_sql, user.id, False)

            for guild in ctx.bot.guilds:
                await conn.execute(guild_sql, guild.id, guild.owner.id)

            await msg.edit(content='Finished. Synced {} guilds and {} users.'.format(len(ctx.bot.guilds),
                                                                                     len(ctx.bot.users)))


def setup(bot):
    bot.add_cog(State(bot))
