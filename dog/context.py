__all__ = ['Context']

from lifesaver import bot


class Context(bot.Context):
    @property
    def pool(self):
        return self.pg_pool
