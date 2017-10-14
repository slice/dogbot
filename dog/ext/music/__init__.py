from dog import Dogbot

from .cog import Music


def setup(bot: Dogbot):
    bot.add_cog(Music(bot))
