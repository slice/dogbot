import random
from itertools import islice

import discord
from discord.ext.commands import is_owner
from lifesaver.bot import Cog, command, group, Context
from lifesaver.bot.storage import AsyncJSONStorage
from lifesaver.utils.formatting import Table, codeblock

CURRENCY_NAME = 'cookie'
CURRENCY_NAME_PLURAL = 'cookies'
CURRENCY_SYMBOL = '\N{COOKIE}'


# https://stackoverflow.com/a/783927/2491753
def truncate_float(f: float, n: int) -> str:
    """Truncates/pads a float f to n decimal places without rounding."""
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return '.'.join([i, (d+'0'*n)[:n]])


def format(amount: float, *, symbol: bool = False) -> str:
    amount = truncate_float(amount, 2)
    if symbol:
        return f'{amount} {CURRENCY_SYMBOL}'
    return f'{amount} {CURRENCY_NAME}' if amount == 1.0 else f'{amount} {CURRENCY_NAME_PLURAL}'


class CurrencyManager:
    def __init__(self, file, *, loop):
        self.storage = AsyncJSONStorage(file, loop=loop)

    def has_wallet(self, user):
        return self.storage.get(user.id) is not None

    def get_wallet(self, user):
        return self.storage.get(user.id)

    async def set_wallet(self, user, wallet):
        await self.storage.put(user.id, wallet)

    ###

    def bal(self, user):
        return self.get_wallet(user)['balance']

    async def write(self, user, amount):
        wallet = self.get_wallet(user)
        wallet['balance'] = amount
        await self.set_wallet(user, wallet)

    async def register(self, user):
        await self.set_wallet(user, {
            'balance': 0.0,
            'passive_chance': 0.3
        })

    ###

    async def add(self, user, amount):
        bal = self.bal(user)
        await self.write(user, bal + amount)

    async def sub(self, user, amount):
        return await self.add(user, -amount)

    def top(self, *, descending: bool = True):
        def key(entry):
            user_id, wallet = entry
            return wallet['balance']
        wallets = self.storage.all()
        return sorted(wallets.items(), key=key, reverse=descending)


class Currency(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.manager = CurrencyManager('currency.json', loop=bot.loop)

    async def on_message(self, msg: discord.Message):
        if not msg.guild or msg.author.bot or self.bot.is_blacklisted(msg.author):
            return

        if not self.manager.has_wallet(msg.author):
            return

        wallet = self.manager.get_wallet(msg.author)
        if random.random() > (1.0 - wallet['passive_chance']):
            await self.manager.add(msg.author, 0.3)

    @command(hidden=True)
    @is_owner()
    async def write(self, ctx: Context, target: discord.Member, amount: float):
        """Sets someone's balance."""
        if not self.manager.has_wallet(target):
            await ctx.send(f"{target} does not have a wallet.")
            return
        await self.manager.write(target, amount)
        await ctx.ok()

    @command()
    async def send(self, ctx: Context, target: discord.Member, amount: float):
        """Sends currency to someone else."""
        if target == ctx.author:
            await ctx.send("You cannot send money to yourself.")
            return

        if amount <= 0:
            await ctx.send("Invalid amount.")
            return

        if not self.manager.has_wallet(ctx.author) or not self.manager.has_wallet(target):
            await ctx.send("One of you don't have a wallet!")
            return

        if amount > self.manager.bal(ctx.author):
            await ctx.send(f"You don't have that much money, {ctx.author.mention}.")
            return

        await self.manager.sub(ctx.author, amount)
        await self.manager.add(target, amount)

        await ctx.send("Transaction completed.")

    @command()
    async def register(self, ctx: Context):
        """Creates a wallet."""
        if self.manager.has_wallet(ctx.author):
            await ctx.send("You already have a wallet.")
            return
        await self.manager.register(ctx.author)
        await ctx.ok()

    @command()
    async def top(self, ctx: Context):
        """Views the top users."""
        table = Table('User', 'Balance')
        for (user_id, wallet) in islice(self.manager.top(), 10):
            balance = wallet['balance']
            user = self.bot.get_user(int(user_id))
            table.add_row(str(user) if user else user_id, truncate_float(balance, 2))
        table = await table.render(loop=self.bot.loop)
        await ctx.send(codeblock(table))

    @command()
    async def wallet(self, ctx: Context, *, target: discord.Member = None):
        """Views your current wallet balance."""
        target = target or ctx.author
        if not self.manager.has_wallet(target):
            subject = 'You' if target == ctx.author else ctx.author
            verb = 'You can send' if target == ctx.author else 'Ask them to send'
            await ctx.send(f"{subject} don't have a wallet. {verb} `{ctx.prefix}register` to make one.")
            return

        bal = self.manager.bal(target)
        await ctx.send(f'{target} > {format(bal, symbol=True)}')


def setup(bot):
    bot.add_cog(Currency(bot))
