from .cog import Quoting


async def setup(bot):
    await bot.add_cog(Quoting(bot))
