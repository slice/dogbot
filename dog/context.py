__all__ = ['Context']

from lifesaver import bot


class Context(bot.Context):
    @property
    def pool(self):
        return self.bot.pool

    def tick(self, variant: bool = True) -> str:
        if variant:
            return self.emoji('green_tick')
        else:
            return self.emoji('red_tick')

    def emoji(self, name: str) -> str:
        return self.bot.config.emoji[name]
