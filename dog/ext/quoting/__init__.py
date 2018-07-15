from .cog import Quoting


def setup(bot):
    bot.add_cog(Quoting(bot))
