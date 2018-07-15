"""Thank you to SnowyLuma#0001 (69198249432449024) for helping me with this."""
import discord
from discord.ext import commands
from discord.ext.commands.view import quoted_word
from lifesaver.utils import clean_mentions


class QuoteNotFound(Exception):
    pass


class QuoteCommand(commands.Group):
    """
    A custom command class that allows us to pull off read_rest shenanigans.

    Basically, this custom subclass allows the following behavior to be pulled
    off:

        ?tag my tag

        ?tag "my tag" tag contents

    With the first command acting as a read operation, and the second acting as
    a write operation. Under normal circumstances, the first command would be
    parsed as ("my", "tag"), but this subclass lets a converter signal to the
    transformer that a read_rest should be always be performed. This read_rest
    is resettable, which replicates a customizable "*, " behavior.
    """
    async def transform(self, ctx, param):
        required = param.default is param.empty
        converter = self._get_converter(param)
        consume_rest_is_special = param.kind == param.KEYWORD_ONLY and not self.rest_is_raw
        view = ctx.view
        view.skip_ws()

        if view.eof:
            if param.kind == param.VAR_POSITIONAL:
                raise RuntimeError()  # break the loop
            if required:
                raise commands.MissingRequiredArgument(param)
            return param.default

        old_index = view.index

        # special converters! consume the rest of the view unless we throw the
        # magic exception that does a reset.
        if consume_rest_is_special or getattr(converter, 'force_consume', False):
            argument = view.read_rest().strip()
        else:
            argument = quoted_word(view)

        try:
            return await self.do_conversion(ctx, converter, argument)
        except QuoteNotFound:
            # the quote doesn't exist, so let's not use the rest of the view
            # for the name. reset!
            view.index = old_index

            # parse the name as a quoted word just like normal, so we can parse
            # the rest instead of eating it all.
            argument = quoted_word(view)
            if ctx.guild:
                argument = clean_mentions(ctx.channel, argument)

            return await self.do_conversion(ctx, str, argument)
        except commands.CommandError as e:
            raise e
        except Exception as e:
            try:
                name = converter.__name__
            except AttributeError:
                name = converter.__class__.__name__

            raise commands.BadArgument('Converting to "{}" failed for parameter "{}".'.format(name, param.name)) from e

    async def _parse_arguments(self, ctx):
        ctx.args = [ctx] if self.instance is None else [self.instance, ctx]
        ctx.kwargs = {}
        args = ctx.args
        kwargs = ctx.kwargs

        view = ctx.view
        iterator = iter(self.params.items())

        if self.instance is not None:
            # we have 'self' as the first parameter so just advance
            # the iterator and resume parsing
            try:
                next(iterator)
            except StopIteration:
                fmt = 'Callback for {0.name} command is missing "self" parameter.'
                raise discord.ClientException(fmt.format(self))

        # next we have the 'ctx' as the next parameter
        try:
            next(iterator)
        except StopIteration:
            fmt = 'Callback for {0.name} command is missing "ctx" parameter.'
            raise discord.ClientException(fmt.format(self))

        for name, param in iterator:
            if param.kind == param.POSITIONAL_OR_KEYWORD:
                transformed = await self.transform(ctx, param)
                args.append(transformed)
            elif param.kind == param.KEYWORD_ONLY:
                # kwarg only param denotes "consume rest" semantics
                if self.rest_is_raw:
                    converter = self._get_converter(param)
                    argument = view.read_rest()
                    kwargs[name] = await self.do_conversion(ctx, converter, argument)
                else:
                    kwargs[name] = await self.transform(ctx, param)
                continue
            elif param.kind == param.VAR_POSITIONAL:
                while not view.eof:
                    try:
                        transformed = await self.transform(ctx, param)
                        args.append(transformed)
                    except RuntimeError:
                        break

        if not self.ignore_extra:
            if not view.eof:
                raise commands.TooManyArguments('Too many arguments passed to ' + self.qualified_name)
