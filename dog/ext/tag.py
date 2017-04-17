import datetime
import discord
from time import time as epoch
from collections import namedtuple
from discord.ext import commands
from dog import Cog, utils, checks

Tag = namedtuple('Tag', 'name value creator created_at uses')

class Tagging(Cog):
    async def create_tag(self, ctx, name, value):
        prefix = f'tags:{ctx.guild.id}:{name}'

        await self.bot.redis.set(f'{prefix}:value', value)
        await self.bot.redis.set(f'{prefix}:creator', ctx.author.id)
        await self.bot.redis.set(f'{prefix}:created_at', epoch())
        await self.bot.redis.set(f'{prefix}:uses', 0)

    async def get_tag(self, ctx, name):
        prefix = f'tags:{ctx.guild.id}:{name}'

        # check if the tag actually exists
        if not await self.bot.redis.exists(f'{prefix}:value'):
            return None

        tag_value = (await self.bot.redis.get(f'{prefix}:value')).decode()
        creator_id = int((await self.bot.redis.get(f'{prefix}:creator')).decode())
        created_at = float((await self.bot.redis.get(f'{prefix}:created_at')).decode())
        uses = int((await self.bot.redis.get(f'{prefix}:uses')).decode())

        creator = ctx.guild.get_member(creator_id) or creator_id

        return Tag(value=tag_value, creator=creator, uses=uses, name=name,
                   created_at=datetime.datetime.utcfromtimestamp(created_at))

    async def delete_tag(self, ctx, name):
        prefix = f'tags:{ctx.guild.id}:{name}'

        await self.bot.redis.delete(f'{prefix}:value')
        await self.bot.redis.delete(f'{prefix}:creator')
        await self.bot.redis.delete(f'{prefix}:created_at')
        await self.bot.redis.delete(f'{prefix}:uses')

    def can_touch_tag(self, ctx, tag):
        perms = ctx.author.guild_permissions

        # they can manage the server
        if perms.manage_guild:
            return True

        # they own the server
        if ctx.author.guild.owner.id == ctx.author.id:
            return True

        # they created the tag
        if tag.creator.id == ctx.author.id:
            return True

        # is dogbot moderator
        if checks.is_dogbot_moderator(ctx):
            return True

        return False

    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, name: str, value: str=None):
        """
        Tag related operations.

        If you provide a value, a tag is created if it doesn't exist. If it
        does exist, it will be overwritten provided that you can touch that
        tag.

        If you don't provide a value, the tag's contents are sent.

        You may only touch a tag if one of the following conditions are met:
            1) You have the "Manage Server" permission.
            2) You are the owner of the server.
            3) You created that tag.
            4) You are a Dogbot Moderator.
        """
        if value:
            tag = await self.get_tag(ctx, name)
            if tag:
                # tag already exists
                if not self.can_touch_tag(ctx, tag):
                    # cannot overwrite
                    await ctx.send('\N{NO PEDESTRIANS} You can\'t overwrite'
                                   ' that tag\'s contents.')
                    return

            # set a tag
            await self.create_tag(ctx, name, value)
            await self.bot.ok(ctx, '\N{MEMO}' if tag else '\N{DELIVERY TRUCK}')
        else:
            # get a tag
            tag = await self.get_tag(ctx, name)
            if tag:
                await ctx.send(tag.value)
                await self.bot.redis.incr(f'tags:{ctx.guild.id}:{name}:uses')
            else:
                await ctx.send('\N{CONFUSED FACE} Not found.')

    @tag.command(name='delete', aliases=['rm', 'remove', 'del'])
    async def tag_delete(self, ctx, name: str):
        """
        Deletes a tag.

        You may only do so if you can touch that tag. For more information,
        see d?help tag.
        """
        tag = await self.get_tag(ctx, name)

        if not tag:
            await ctx.send('\N{CONFUSED FACE} Not found.')
            return

        if not self.can_touch_tag(ctx, tag):
            await ctx.send('\N{NO PEDESTRIANS} You can\'t do that.')
            return

        await self.delete_tag(ctx, name)
        await self.bot.ok(ctx, '\N{PUT LITTER IN ITS PLACE SYMBOL}')

    @tag.command(name='info', aliases=['about'])
    async def tag_info(self, ctx, name: str):
        """ Shows you information about a certain tag. """
        tag = await self.get_tag(ctx, name)

        if tag:
            embed = discord.Embed(title=tag.name)
            embed.description = tag.value
            embed.add_field(name='Created',
                            value=utils.american_datetime(tag.created_at) + ' UTC')
            embed.add_field(name='Created by',
                            value=tag.creator.mention, inline=False)
            embed.add_field(name='Uses',
                            value=tag.uses)
            await ctx.send(embed=embed)
        else:
            await ctx.send('\N{CONFUSED FACE} Not found.')

def setup(bot):
    bot.add_cog(Tagging(bot))
