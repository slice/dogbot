"""
Extension that implements tags, a way to store pieces of useful text for later.
"""

import datetime
import re
from collections import namedtuple
import datetime

import discord
from discord.ext import commands

from dog import Cog
from dog.core import checks, utils

Tag = namedtuple('Tag', 'name value creator created_at uses')


class Tagging(Cog):
    async def create_tag(self, ctx: commands.Context, name: str, value: str):
        insert = 'INSERT INTO tags VALUES ($1, $2, $3, $4, 0, $5)'
        await self.bot.pg.execute(insert, name, ctx.guild.id, ctx.author.id, value,
                                  datetime.datetime.utcnow())

    async def get_tag(self, ctx: commands.Context, name: str) -> Tag:
        """ Finds a tag, and returns it as a ``Tag`` object. """
        select = 'SELECT * FROM tags WHERE guild_id = $1 AND name = $2'
        record = await self.bot.pg.fetchrow(select, ctx.guild.id, name)

        if not record:
            return None

        creator = ctx.guild.get_member(record['creator_id']) or record['creator_id']
        return Tag(value=record['value'], creator=creator, uses=record['uses'], name=name,
                   created_at=record['created_at'])

    async def delete_tag(self, ctx: commands.Context, name: str):
        """ Deletes a tag. """
        await self.bot.pg.execute('DELETE FROM tags WHERE guild_id = $1 AND name = $2', ctx.guild.id,
                                  name)

    def can_touch_tag(self, ctx: commands.Context, tag: str) -> bool:
        """ Returns whether someone can touch a tag (modify, delete, or edit it). """
        perms = ctx.author.guild_permissions

        # they can manage the server
        if perms.manage_guild:
            return True

        # they own the server
        if ctx.author.guild.owner == ctx.author:
            return True

        # they created the tag
        if tag.creator == ctx.author:
            return True

        # is dogbot moderator
        if checks.is_dogbot_moderator(ctx):
            return True

        return False

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def tag(self, ctx, name: str, *, value: str=None):
        """
        Tag related operations.

        If you provide a value, a tag is created if it doesn't exist. If it
        does exist, it will be overwritten provided that you can touch that
        tag.

        If you don't provide a value, the tag's contents are sent.

        You may only touch a tag if one of the following conditions are met:
            1) You have the "Manage Server" permission.
            2) You are the owner of the server.
            3) You have created that tag.
            4) You are a Dogbot Moderator.
        """
        if value:
            # a value was provided, create or overwrite
            tag = await self.get_tag(ctx, name)

            # tag already exists, check if we can touch it
            if tag and not self.can_touch_tag(ctx, tag):
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
                await self.bot.pg.execute('UPDATE tags SET uses = uses + 1 WHERE name = $1 AND'
                                          ' guild_id = $2', name, ctx.guild.id)
            else:
                await ctx.send('\N{CONFUSED FACE} Not found.')

    @tag.command(name='list', aliases=['ls'])
    @commands.guild_only()
    async def tag_list(self, ctx):
        """ Lists tags in this server. """
        tags = [record['name'] for record in
                await self.bot.pg.fetch('SELECT * FROM tags WHERE guild_id = $1', ctx.guild.id)]
        try:
            await ctx.send(f'**{len(tags)} tag(s):** ' + ', '.join(tags))
        except discord.HTTPException:
            await ctx.send('\N{PENSIVE FACE} Too many tags to display!')

    @tag.command(name='delete', aliases=['rm', 'remove', 'del'])
    @commands.guild_only()
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

    @tag.command(name='markdown', aliases=['raw'])
    @commands.guild_only()
    async def tag_markdown(self, ctx, name: str):
        """
        Views the markdown of a tag.
        """
        tag = await self.get_tag(ctx, name)

        if not tag:
            await ctx.send('\N{CONFUSED FACE} Not found.')

        content = tag.value
        escape_regex = r'(`|\*|~|_|<|\\)'
        # no, those two strings can't be together
        content = re.sub(escape_regex, r'\\' + '\\1', content)

        await ctx.send(content)

    @tag.command(name='info', aliases=['about'])
    @commands.guild_only()
    async def tag_info(self, ctx, name: str):
        """ Shows you information about a certain tag. """
        tag = await self.get_tag(ctx, name)

        if tag:
            embed = discord.Embed(title=tag.name, description=tag.value)
            embed.add_field(name='Created', value=utils.american_datetime(tag.created_at) + ' UTC')
            embed.add_field(name='Created by', value=tag.creator.mention, inline=False)
            embed.add_field(name='Uses', value=tag.uses)
            await ctx.send(embed=embed)
        else:
            await ctx.send('\N{CONFUSED FACE} Not found.')


def setup(bot):
    bot.add_cog(Tagging(bot))
