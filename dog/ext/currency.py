import random
from itertools import islice
from typing import Dict, Any, Tuple, List

import discord
import time
from discord import User
from discord.ext.commands import is_owner, BadArgument
from lifesaver.bot import Cog, command, Context
from lifesaver.bot.storage import AsyncJSONStorage
from lifesaver.utils.formatting import Table, codeblock

CURRENCY_NAME = 'cookie'
CURRENCY_NAME_PLURAL = 'cookies'
CURRENCY_SYMBOL = '\N{COOKIE}'


# https://stackoverflow.com/a/783927/2491753
def truncate_float(f: float, n: int = 2) -> str:
    """Truncates/pads a float f to n decimal places without rounding."""
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return '.'.join([i, (d+'0'*n)[:n]])


def format(amount: float, *, symbol: bool = False) -> str:
    amount = truncate_float(amount)
    if symbol:
        return f'{amount} {CURRENCY_SYMBOL}'
    return f'{amount} {CURRENCY_NAME}' if amount == 1.0 else f'{amount} {CURRENCY_NAME_PLURAL}'


def currency(string: str) -> float:
    try:
        result = float(string)
        if result == float('inf') or result <= 0:
            raise BadArgument('Invalid amount.')
        return result
    except ValueError:
        raise BadArgument('Invalid number.')


Wallet = Dict[str, Any]


class CurrencyManager:
    def __init__(self, file, *, loop):
        self.storage = AsyncJSONStorage(file, loop=loop)

    def has_wallet(self, user: User) -> bool:
        return self.storage.get(user.id) is not None

    def get_wallet(self, user: User) -> Wallet:
        return self.storage.get(user.id)

    async def set_wallet(self, user: User, wallet: Wallet):
        await self.storage.put(user.id, wallet)

    ###

    def bal(self, user: User) -> float:
        return self.get_wallet(user)['balance']

    async def write(self, user: User, amount: float):
        wallet = self.get_wallet(user)
        wallet['balance'] = amount
        await self.set_wallet(user, wallet)

    async def register(self, user: User):
        """Creates a wallet for a user."""
        await self.set_wallet(user, {
            'balance': 0.0,
            'passive_chance': 0.3,
            'passive_cooldown': None
        })

    ###

    async def add(self, user: User, amount: float):
        bal = self.bal(user)
        await self.write(user, bal + amount)

    async def add_passive(self, user: User, amount: float):
        wallet = self.get_wallet(user)
        if wallet['passive_cooldown'] and (time.time() - wallet['passive_cooldown']) < 60 * 2:
            return False
        wallet['passive_cooldown'] = time.time()
        wallet['balance'] += amount
        await self.set_wallet(user, wallet)
        return True

    async def sub(self, user: User, amount: float):
        return await self.add(user, -amount)

    def top(self, *, descending: bool = True) -> List[Tuple[int, Wallet]]:
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
            await self.manager.add_passive(msg.author, 0.3)

    @command(hidden=True)
    @is_owner()
    async def write(self, ctx: Context, target: discord.Member, amount: float):
        """Sets someone's balance."""
        if not self.manager.has_wallet(target):
            await ctx.send(f"{target} does not have a wallet.")
            return
        await self.manager.write(target, amount)
        await ctx.ok()

    @command(aliases=['transfer'])
    async def send(self, ctx: Context, target: discord.Member, amount: currency):
        """Sends currency to someone else."""
        if target == ctx.author:
            await ctx.send("You cannot send money to yourself.")
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
    async def donate(self, ctx: Context, amount: currency):
        """
        Donates some currency.

        This will increase the chance of you passively gaining currency, to a maximum of 50%.
        """
        if not self.manager.has_wallet(ctx.author):
            await ctx.send("You don't have a wallet.")
            return

        wallet = self.manager.get_wallet(ctx.author)
        if wallet['passive_chance'] >= 0.5:
            await ctx.send("Your chance is at max! (50%)")
            return

        if wallet['balance'] < amount:
            await ctx.send("Not enough funds.")
            return

        percent_increase = min((amount / 100) * 0.5, 0.5 - wallet['passive_chance'])
        wallet['passive_chance'] += percent_increase
        now = wallet['passive_chance'] * 100

        await self.manager.set_wallet(ctx.author, wallet)
        await self.manager.sub(ctx.author, amount)
        await ctx.send(f'Your chance of gaining {CURRENCY_NAME_PLURAL} is now {now}% (up by {percent_increase * 100}%).')

    @command()
    async def delete(self, ctx: Context):
        """Deletes your wallet."""
        if not await ctx.confirm(title='Are you sure?', message=f'All {CURRENCY_NAME_PLURAL} will be lost forever.',
                                 delete_after=True, cancellation_message='Cancelled.'):
            return

        # TODO: abstract
        await self.manager.storage.delete(ctx.author.id)
        await ctx.ok()

    @command()
    async def top(self, ctx: Context):
        """Views the top users."""
        table = Table('User', 'Balance', 'Chance')
        for (user_id, wallet) in islice(self.manager.top(), 10):
            balance = wallet['balance']
            chance = f"{wallet['passive_chance'] * 100}%"
            user = self.bot.get_user(int(user_id))
            table.add_row(str(user) if user else user_id, truncate_float(balance), chance)
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
        chance = f"{self.manager.get_wallet(target)['passive_chance'] * 100}%"
        await ctx.send(f'{target} > {format(bal, symbol=True)} ({chance} chance)')


def setup(bot):
    bot.add_cog(Currency(bot))
