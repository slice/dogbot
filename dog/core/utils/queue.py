import logging
import asyncio

logger = logging.getLogger(__name__)


class AsyncQueue:
    def __init__(self, bot, name):
        self.name = name
        self.bot = bot

        self.current_item = None
        self.handler = bot.loop.create_task(self.handle())
        self.has_item = asyncio.Event()

        self._log('debug', 'Created!')

    def reboot(self):
        self.handler.cancel()
        self.handler = self.bot.loop.create_task(self.handle())

    def _log(self, level, msg, *args):
        # ugh
        logger.log(getattr(logging, level.upper(), logging.INFO), f'[Queue] {self.name}: {msg}', *args)

    async def get_latest_item(self):
        raise NotImplementedError

    async def fulfill_item(self, item):
        raise NotImplementedError

    async def handle(self):
        self._log('debug', 'Handler started.')

        await self.bot.wait_until_ready()

        if await self.get_latest_item():
            self.has_item.set()

        while not self.bot.is_closed():
            self._log('debug', 'Waiting for an item...')

            await self.has_item.wait()

            # get the current item to process
            item = self.current_item = await self.get_latest_item()
            self._log('debug', 'Fetched latest item. %s', item)

            # fulfill the item we got
            await self.fulfill_item(item)

            # clear has item event if there's no more items
            if not await self.get_latest_item():
                self._log('debug', 'No more items! Clearing event.')
                self.has_item.clear()

            self.current_item = None
            self._log('debug', 'Fulfilled item. %s', item)
