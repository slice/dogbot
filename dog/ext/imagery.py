import asyncio
import inspect
import logging
from functools import partial
from io import BytesIO

import aiohttp
import discord
import wand.font
from discord.ext.commands import BadArgument, MemberConverter, cooldown, BucketType
from lark import Lark, LexError, ParseError, Transformer
from lifesaver.bot import Cog, Context, command
from lifesaver.utils import escape_backticks
from wand.color import Color
from wand.image import Image as WandImage

log = logging.getLogger(__name__)
FONT = wand.font.Font('assets/SourceSansPro-Regular.otf')


class ProgramTransformer(Transformer):
    def string(self, values):
        [string_with_quotes] = values
        return string_with_quotes[1:-1]

    def number(self, values):
        [value] = values
        return float(value)

    def keyvalue(self, values):
        [key, value] = values
        return str(key), value

    def parameters(self, keyvalues):
        return dict(keyvalues)

    def manipulation(self, values):
        params = None if len(values) == 1 else values[1]
        return {'name': str(values[0]), 'params': params}

    program = list
    list = list
    pair = tuple
    dict = dict

    null = lambda self, _: None
    true = lambda self, _: True
    false = lambda self, _: False


manipulator_parser = Lark(r"""
    ?program: manipulation (_next manipulation)*

    manipulation: name ["(" parameters ")"]
    parameters: keyvalue (_sep keyvalue)*
    keyvalue: name ":" value

    ?value: dict
          | list
          | string
          | SIGNED_NUMBER  -> number
          | "true"         -> true
          | "false"        -> false
          | "null"         -> null

    list   : "[" [value ("," value)*] "]"
    dict   : "{" [pair ("," pair)*] "}"
    pair   : string ":" value
    ?name  : CNAME
    string : ESCAPED_STRING
    _sep   : "\n" | ","
    _next  : ">" | "|"

    %import common.ESCAPED_STRING
    %import common.SIGNED_NUMBER
    %import common.CNAME
    %import common.WS
    %ignore WS

    """, start='program')


class ProgramError(Exception):
    """A runtime error thrown by a running program."""


class Manipulations:
    @staticmethod
    def flip(image: WandImage):
        """Flips an image."""
        image.flip()

    @staticmethod
    def flop(image: WandImage):
        """Flop an image. (Opposite of flip.)"""
        image.flop()

    @staticmethod
    def resize(image: WandImage, width: int, height: int):
        """Resizes the image."""
        image.resize(width, height)

    @staticmethod
    def transform(image: WandImage, to: str):
        """Transforms an image with ImageMagick transform syntax."""
        image.transform(to)

    @staticmethod
    def rotate(image: WandImage, by: int):
        """Rotates the image by degrees."""
        image.rotate(by)

    @staticmethod
    def threshold(image: WandImage, threshold: float):
        """Performs a threshold dependent on pixel intensity."""
        image.threshold(threshold, None)

    @staticmethod
    def chroma(image: WandImage, color: str, fuzz: int, invert: bool = False):
        """Performs a chroma-key, turning one color into transparency."""
        with Color(color) as col:
            image.transparent_color(col, alpha=0.0, fuzz=fuzz, invert=invert)

    @staticmethod
    def composite(image: WandImage, other: WandImage, x: int = 0, y: int = 0, width: int = None, height: int = None):
        """Places another image on top of this image."""
        if width and height:
            other.resize(width, height)
        image.composite(other, left=x, top=y)

    @staticmethod
    def sharpen(image: WandImage, amount: int, threshold: int, sigma: int = 0, radius: int = 0):
        """Sharpens the image."""
        image.unsharp_mask(radius, sigma, amount, threshold)

    @staticmethod
    def gamma(image: WandImage, amount: float):
        """Modifies the gamma level of the image."""
        image.gamma(amount)

    @staticmethod
    def caption(image: WandImage, text: str, ox: int = 0, oy: int = 0, color: str = 'black', gravity: str = 'center'):
        """Adds some text to the image."""
        with Color(color) as col:
            font = wand.font.Font(FONT.path, color=col)
            image.caption(text, left=ox, top=oy, font=font, gravity=gravity)


class Program:
    def __init__(self, ctx, tree):
        self.ctx = ctx
        self.tree = tree

    async def run(self, image: 'Image', *, loop: asyncio.AbstractEventLoop):
        for manipulation in self.transformed:
            name, params = manipulation.values()
            func = getattr(Manipulations, name, None)
            if not func or not callable(func):
                raise ProgramError(f'No such manipulation: {name}')

            signature = inspect.signature(func)
            num_params = (0 if params is None else len(params))
            minimum_required = sum(1 for param in signature.parameters.values() if param.default is
                                   inspect.Parameter.empty) - 1
            if num_params < minimum_required:
                raise ProgramError(f'Invalid parameter list. Expected at least {minimum_required} parameters in call '
                                   f'to {name}, found {num_params} parameters instead.')

            for name, param in signature.parameters.items():
                # skip actual image that is passed by manipulate()
                if name == 'image':
                    continue

                required = param.default is inspect.Parameter.empty
                if required and name not in params:
                    raise ProgramError(f'{name} is a required parameter, but it was not found.')

                if not required and name not in params:
                    # skip type checking if it's optional and not specified
                    continue

                if param.annotation is not inspect.Parameter.empty:
                    # automatically convert to integer
                    if isinstance(params[name], float) and param.annotation is int:
                        params[name] = int(params[name])

                    # resolve images
                    if isinstance(params[name], str) and param.annotation is WandImage:
                        params[name] = await Image.convert(self.ctx, params[name])

                    if not isinstance(params[name], param.annotation):
                        raise ProgramError(f'Parameter {name} is a {type(params[name]).__name__} instead of a '
                                           f'`{param.annotation.__name__}`.')

            params_items = dict(params.items()) if params else {}
            await image.manipulate(func, **params_items, loop=loop)

    @property
    def pretty(self):
        return self.tree.pretty()

    @property
    def transformed(self):
        manips = ProgramTransformer().transform(self.tree)
        if not isinstance(manips, list):
            manips = [manips]
        return manips

    @classmethod
    def from_text(cls, ctx, text: str) -> 'Program':
        return cls(ctx, manipulator_parser.parse(text))

    @classmethod
    async def convert(cls, ctx: Context, code: str):
        try:
            tree = cls.from_text(ctx, code)
            return tree
        except (LexError, ParseError) as error:
            raise BadArgument(f'Parsing error. `{escape_backticks(str(error))}`')


class Image(WandImage):
    async def render(self, *, format: str = 'png', loop: asyncio.AbstractEventLoop):
        def renderer():
            buffer = BytesIO()
            with self as image:
                image.format = format
                image.save(file=buffer)
            buffer.seek(0)
            return buffer

        return await loop.run_in_executor(None, renderer)

    async def render_to_file(self, filename: str = 'image.png', *args, **kwargs):
        buffer = await self.render(*args, **kwargs)
        return discord.File(fp=buffer, filename=filename)

    async def manipulate(self, callable, *args, loop: asyncio.AbstractEventLoop, **kwargs):
        func = partial(callable, self, *args, **kwargs)
        await loop.run_in_executor(None, func)

    @classmethod
    async def from_user(cls, user: discord.User):
        avatar_url = user.avatar_url_as(format='png', static_format='png', size=1024)
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                return cls(blob=await resp.read())

    @classmethod
    async def convert(cls, ctx: Context, argument: str):
        user = await MemberConverter().convert(ctx, argument)
        return await cls.from_user(user)


class Imagery(Cog):
    @command()
    async def manipulations(self, ctx: Context):
        """Shows a list of available manipulations for use."""
        for (name, method) in inspect.getmembers(Manipulations):
            if not inspect.isfunction(method):
                continue
            signature = inspect.signature(method)
            params = list(signature.parameters.values())
            formatted = ', '.join(str(param) for param in params[1:])

            ctx += f'{name}({formatted})\n{method.__doc__}\n'
        await ctx.send_pages()

    @command(typing=True)
    @cooldown(1, 3, BucketType.user)
    async def manip(self, ctx: Context, target: Image, *, program: Program):
        """Runs an image manipulation program on someone's avatar."""
        log.debug('Tree: %s\nTransformed: %s', program.tree, program.transformed)
        if len(program.tree) > 20:
            await ctx.send("Slow down there. Maximum of 20 manipulations.")
            return
        try:
            coro = program.run(target, loop=ctx.bot.loop)
            await asyncio.wait_for(coro, timeout=10.0, loop=ctx.bot.loop)
            file = await target.render_to_file(loop=self.bot.loop)
            await ctx.send(file=file)
            file.close()
        except ProgramError as error:
            await ctx.send(f'Program runtime error. {error}')
            return
        except asyncio.TimeoutError:
            await ctx.send(f'{ctx.author.mention}, your program took too long to run. It has been killed.')
            return
        except Exception as error:
            await ctx.send(f'Program runtime error. `{escape_backticks(str(error))}`')
            return


def setup(bot):
    bot.add_cog(Imagery(bot))
