import random

import aiohttp
import discord
import time
from discord.ext import commands
from discord.ext.commands import bot_has_permissions, has_permissions, guild_only, is_owner
from lifesaver.bot import Cog, group, command, Context
from lifesaver.bot.storage import AsyncJSONStorage

from dog.converters import EmojiStealer, UserIDs

AUTORETURN_AVOIDERS = ["[no-return]", "[noreturn]", "[no-unafk]", "[nounafk]", "[no-back]", "[noback]"]


class Utility(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.afk_persistent = AsyncJSONStorage('afk.json', loop=bot.loop)
        self.session = aiohttp.ClientSession(loop=bot.loop)

    def __unload(self):
        self.session.close()

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.author.id in self.afk_persistent:
            time_difference = time.time() - self.afk_persistent[message.author.id]['time']
            if time_difference < 5.0:
                # ignore any messages sent within 5s of going away
                return

            aborted = any(avoider in message.content.lower() for avoider in AUTORETURN_AVOIDERS)
            if aborted:
                return

            await self.afk_persistent.delete(message.author.id)
            try:
                await message.add_reaction('\N{WAVING HAND SIGN}')
            except discord.Forbidden:
                pass

        mentioned_afk = [user for user in message.mentions if user.id in self.afk_persistent]
        mentioned_self = any(user == message.author for user in message.mentions)

        if not mentioned_afk or mentioned_self:
            return

        if len(mentioned_afk) == 1:
            reason = self.afk_persistent[mentioned_afk[0].id]['reason'] or 'No reason provided.'
            notice = f'{message.author.mention}: {mentioned_afk[0]} is away. ({reason})'
        else:
            users = ', '.join(str(user) for user in mentioned_afk)
            notice = f'{message.author.mention}: {users} are away.'

        try:
            await message.channel.send(notice)
        except discord.Forbidden:
            try:
                await message.author.send(notice)
            except discord.Forbidden:
                pass

    @command(aliases=['ginv'])
    async def inv(self, ctx: Context, *ids: UserIDs):
        """Generates bot invites."""
        if not ids:
            await ctx.send('Provide mentions or IDs!')
            return
        urls = '\n'.join('<' + discord.utils.oauth_url(bot_id) + '>' for bot_id in ids)
        await ctx.send(urls)

    @command(aliases=['shiba', 'dog'], typing=True)
    async def shibe(self, ctx: Context):
        """Sends a random shibe picture."""
        try:
            async with self.session.get('http://shibe.online/api/shibes?count=1&urls=true') as resp:
                data = await resp.json()
                await ctx.send(data[0])
        except aiohttp.ClientError:
            await ctx.send('Failed to grab a shibe. \N{DOG FACE}')

    @command(aliases=['choose'])
    async def pick(self, ctx: Context, *choices: commands.clean_content):
        """Pick from a list of choices."""
        if not choices:
            await ctx.send('Send some choices.')
            return

        if len(set(choices)) == 1:
            await ctx.send('Invalid choices.')
            return

        result = random.choice(choices)
        await ctx.send(result)

    @group(aliases=['afk'], invoke_without_command=True)
    async def away(self, ctx: Context, *, reason: commands.clean_content = None):
        """
        Marks yourself as away with a message.

        Anybody who mentions you will be shown the message you provided. Do not abuse this.
        To reset your away status, send any message or send d?back. To prevent automatic d?back,
        include "[noback]" (without quotes) in your message.
        """
        await self.afk_persistent.put(ctx.author.id, {'reason': reason, 'time': time.time()})
        await ctx.ok()

    @away.command(hidden=True)
    @is_owner()
    async def reset(self, ctx: Context, *, target: discord.User):
        """Forcibly removes someone's away status."""
        try:
            await self.afk_persistent.delete(target.id)
        except KeyError:
            pass
        await ctx.ok()

    @command()
    async def back(self, ctx: Context):
        """Returns from away status."""
        if ctx.author.id not in self.afk_persistent:
            await ctx.send("You aren't away.")
        else:
            await self.afk_persistent.delete(ctx.author.id)
            await ctx.ok()

    @command()
    @guild_only()
    @bot_has_permissions(manage_emojis=True, read_message_history=True)
    @has_permissions(manage_emojis=True)
    async def steal_emoji(self, ctx: Context, emoji: EmojiStealer, *, name=None):
        """Steals an emoji."""
        # the converter can return none when cancelled.
        if not emoji:
            return

        emoji_url = f'https://cdn.discordapp.com/emojis/{emoji.id}.png'

        if not emoji.name and not name:
            await ctx.send('No name was provided nor found.')
            return

        name = emoji.name or name.strip(':')
        msg = await ctx.send('Downloading...')

        try:
            async with ctx.bot.session.get(emoji_url) as resp:
                data = await resp.read()
                emoji = await ctx.guild.create_custom_emoji(name=name, image=data)

                try:
                    await msg.edit(content=str(emoji))
                    await msg.add_reaction(emoji)
                except discord.HTTPException:
                    await ctx.ok()
        except aiohttp.ClientError:
            await msg.edit(content='Failed to download the emoji.')
        except discord.HTTPException as exc:
            await msg.edit(content=f'Failed to upload the emoji: {exc}')


def setup(bot):
    bot.add_cog(Utility(bot))
