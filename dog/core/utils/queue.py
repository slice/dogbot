import logging
import asyncio

from abc import ABC, abstractmethod

from dog import DogBot

logger = logging.getLogger(__name__)


class AsyncQueue(ABC):
    """
    An arbitrary queue that consumes items asynchronously. All items are processed in a background task.
    """
    def __init__(self, bot: DogBot, name: str):
        #: The name of this :class:`AsyncQueue`.
        self.name = name

        #: The bot instance to use.
        self.bot = bot

        #: The current item being processed, if any.
        self.current_item = None

        #: The :class:`asyncio.Task` that handles items.
        self.handler = bot.loop.create_task(self.handle())

        #: A :class:`asyncio.Event` that is set as long as we have an item.
        self.has_item = asyncio.Event()

        self._log('debug', 'Created!')

    def reboot(self):
        self.handler.cancel()
        self.handler = self.bot.loop.create_task(self.handle())

    def _log(self, level, msg, *args):
        # ugh
        logger.log(getattr(logging, level.upper(), logging.INFO), f'[Queue] {self.name}: {msg}', *args)

    @abstractmethod
    async def get_latest_item(self):
        raise NotImplementedError

    @abstractmethod
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
