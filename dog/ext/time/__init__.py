from .cog import Time


async def setup(bot):
    await bot.add_cog(Time(bot))
