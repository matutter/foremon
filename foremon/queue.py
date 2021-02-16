from asyncio import Queue
from typing import Any


class queueiter:

    def __init__(self, queue: Queue, stop_obj: Any = None):
        self.queue = queue
        self.stop_obj = stop_obj

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.queue.get()

        if item is self.stop_obj:
            raise StopAsyncIteration

        return item


__all__ = ['queueiter']
