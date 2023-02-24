from .cog import Gatekeeper


async def setup(bot):
    await bot.add_cog(Gatekeeper(bot))
