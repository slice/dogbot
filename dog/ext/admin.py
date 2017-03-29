import logging
import re
import discord
from time import monotonic
from discord.ext import commands
from dog import Cog
from dog import checks

logger = logging.getLogger(__name__)

class Admin(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eval_last_result = None

    @commands.command()
    async def ping(self):
        """ You know what this does. """
        begin = monotonic()
        msg = await self.bot.say('Pong!')
        end = monotonic()
        difference_ms = round((end - begin) * 1000, 2)
        await self.bot.edit_message(msg, f'Pong! Took `{difference_ms}ms`.')

    @commands.command()
    async def prefixes(self):
        """ Lists the bot's prefixes. """
        prefixes = ', '.join([f'`{p}`' for p in self.bot.command_prefix])
        await self.bot.say(f'My prefixes are: {prefixes}')

    @commands.command(pass_context=True, name='eval')
    @checks.is_owner()
    async def _eval(self, ctx, *, code: str):
        """ Evaluates a Python expression. """
        code_regex = re.compile(r'`(.+)`')
        match = code_regex.match(code)
        if match is None:
            logger.info('eval: tried to eval, no code (%s)', code)
            await self.bot.say('No code was found. Surround it in backticks (\\`code\\`).')
            return
        code = match.group(1)

        logger.info('eval: %s', code)

        env = {
            'bot': ctx.bot,
            'ctx': ctx,
            'msg': ctx.message,
            'server': ctx.message.server,
            'channel': ctx.message.channel,
            'me': ctx.message.author,

            'get': discord.utils.get,
            'find': discord.utils.find,

            '_': self.eval_last_result,
        }

        fmt_exception = '```py\n>>> {}\n\n{}: {}```'
        fmt_result = '```py\n>>> {}\n\n{}```'
        room = 2000 - (10 + len(code) + 6 + 3)

        env.update(globals())

        try:
            output = eval(code, env)
            self.eval_last_result = output
            output = str(output)
        except Exception as e:
            name = type(e).__name__
            await self.bot.say(fmt_exception.format(code, name, e))
            return

        if len(output) > room:
            output = output[:room] + '...'

        await self.bot.say(fmt_result.format(code, output or 'None'))

def setup(bot):
    bot.add_cog(Admin(bot))
