"""
Handy exec (eval, debug) cog. Allows you to run code on the bot during runtime. This cog is a combination of the
exec commands of other bot authors, allowing for maximum efficiency:

Credit:
    - Rapptz (Danny)
        - https://github.com/Rapptz/RoboDanny/blob/master/cogs/repl.py#L31-L75
    - b1naryth1ef (Andrei)
        - https://github.com/b1naryth1ef/b1nb0t/blob/master/b1nb0t/plugins/util.py#L229-L266

Features:
    - Strips code markup (code blocks, inline code markup)
    - Access to last result with _
    - _get and _find instantly available without having to import discord
    - Redirects stdout so you can print()
    - Sane syntax error reporting
    - Quickly retry evaluations
    - Implicit return
"""

import io
import logging
import textwrap
import traceback
from contextlib import redirect_stdout

import aiohttp
import discord
from discord.ext import commands

from dog import Cog
from dog.core.context import DogbotContext
from dog.core.utils import codeblock
from dog.haste import haste

log = logging.getLogger(__name__)


class Code(commands.Converter):
    def __init__(self, *, wrap_code=False, strip_ticks=True, indent_width=4, implicit_return=False):
        """
        Code converter.

        Args:
            wrap_code: Specifies whether to wrap the resulting code in a function.
            strip_ticks: Specifies whether to strip the code of formatting-related backticks.
            indent_width: Specifies the indent width, if wrapping.
            implicit_return: Automatically adds a return statement, when wrapping code.
        """
        self.wrap_code = wrap_code
        self.strip_ticks = strip_ticks
        self.indent_width = indent_width
        self.implicit_return = implicit_return

    async def convert(self, ctx: DogbotContext, arg: str) -> str:
        result = arg

        if self.strip_ticks:
            # remove codeblock ticks
            if result.startswith('```') and result.endswith('```'):
                result = '\n'.join(result.split('\n')[1:-1])

            # remove inline code ticks
            result = result.strip('` \n')

        if self.wrap_code:
            # wrap in a coroutine and indent
            result = 'async def func():\n' + textwrap.indent(result, ' ' * self.indent_width)

        if self.wrap_code and self.implicit_return:
            last_line = result.splitlines()[-1]

            # if the last line isn't indented and not returning, add it
            if not last_line[4:].startswith(' ') and 'return' not in last_line:
                last_line = (' ' * self.indent_width) + 'return ' + last_line[4:]

            result = '\n'.join(result.splitlines()[:-1] + [last_line])

        return result


def format_syntax_error(e: SyntaxError) -> str:
    """ Formats a SyntaxError. """
    if e.text is None:
        return '```py\n{0.__class__.__name__}: {0}\n```'.format(e)
    # display a nice arrow
    return '```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```'.format(e, '^', type(e).__name__)


class Exec(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.last_result = None
        self.previous_code = None

    async def execute(self, ctx, code):
        log.info('Eval: %s', code)

        async def upload(file_name: str) -> discord.Message:
            with open(file_name, 'rb') as fp:
                return await ctx.send(file=discord.File(fp))

        async def send(*args, **kwargs) -> discord.Message:
            return await ctx.send(*args, **kwargs)

        env = {
            'bot': ctx.bot,
            'ctx': ctx,
            'msg': ctx.message,
            'guild': ctx.guild,
            'channel': ctx.channel,
            'me': ctx.message.author,

            # modules
            'discord': discord,
            'commands': commands,

            # utilities
            '_get': discord.utils.get,
            '_find': discord.utils.find,
            '_upload': upload,
            '_send': send,

            # last result
            '_': self.last_result,
            '_p': self.previous_code
        }

        env.update(globals())

        # simulated stdout
        stdout = io.StringIO()

        # define the wrapped function
        try:
            exec(compile(code, '<exec>', 'exec'), env)
        except SyntaxError as e:
            # send pretty syntax errors
            return await ctx.send(format_syntax_error(e))

        # grab the defined function
        func = env['func']

        try:
            # execute the code
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            # something went wrong :(
            try:
                await ctx.message.add_reaction(ctx.tick('red', raw=True))
            except (discord.HTTPException, discord.Forbidden):
                # failed to add failure tick, hmm.
                pass

            # send stream and what we have
            return await ctx.send(codeblock(traceback.format_exc(limit=7), lang='py'))

        # code was good, grab stdout
        stream = stdout.getvalue()

        try:
            await ctx.message.add_reaction(ctx.tick('green', raw=True))
        except (discord.HTTPException, discord.Forbidden):
            # couldn't add the reaction, ignore
            pass

        # set the last result, but only if it's not none
        if ret is not None:
            self.last_result = ret

        # form simulated stdout and repr of return value
        meat = stream + repr(ret)
        message = codeblock(meat, lang='py')

        if len(message) > 2000:
            # too long
            try:
                # send meat to hastebin
                url = await haste(ctx.bot.session, meat)
                await ctx.send(await ctx._('cmd.eval.long', url))
            except KeyError:
                # failed to upload, probably too big.
                await ctx.send(await ctx._('cmd.eval.huge'))
            except aiohttp.ClientError:
                # pastebin is probably down.
                await ctx.send(await ctx._('cmd.eval.pastebin_down'))
        else:
            # message was under 2k chars, just send!
            await ctx.send(message)

    @commands.command(name='retry', hidden=True)
    @commands.is_owner()
    async def retry(self, ctx):
        """ Retries the previously executed Python code. """
        if not self.previous_code:
            return await ctx.send('No previous code.')

        await self.execute(ctx, self.previous_code)

    @commands.command(name='eval', aliases=['exec', 'debug'])
    @commands.is_owner()
    async def _eval(self, ctx, *, code: Code(wrap_code=True, implicit_return=True)):
        """ Executes Python code. """

        # store previous code
        self.previous_code = code

        await self.execute(ctx, code)


def setup(bot):
    bot.add_cog(Exec(bot))
