import asyncio
import time
from asyncio import BaseEventLoop
from asyncio.events import TimerHandle
from collections import defaultdict
from typing import Any, Callable, DefaultDict, List, Optional

from foremon.display import display_warning


class EventContainer:
    set_at: int
    args: List[Any]
    reset_count: int
    warn_after: int

    def __init__(self) -> None:
        self.set_at = -1
        self.args = []
        self.reset_count = 0
        self.warn_after = 100

    def set(self, args: List[Any]):
        if self.set_at != -1:
            self.reset_count += 1

        self.set_at = time.time_ns()
        self.args = args

        if self.reset_count < self.warn_after:
            return

        display_warning('detected high events volume - suppressed',
                        self.reset_count, 'events')
        self.warn_after += 100


class Debounce:
    callback: Callable
    dwell = float
    pending_events: DefaultDict
    _scheduled: Optional[TimerHandle]

    def __init__(self, dwell: float, callback: Callable, loop: Optional[BaseEventLoop] = None):
        self.loop = loop or asyncio.get_event_loop()
        self.callback = callback
        self.dwell = dwell
        self.pending_events = defaultdict(EventContainer)
        self._scheduled = None

    def submit(self, key: str, *args: List[Any]):
        if self.dwell <= 0.0:
            try:
                self.callback(*args)
            except:
                pass
        else:
            self.pending_events[key].set(args)
            if self._scheduled:
                self._scheduled.cancel()
            self._scheduled = self.loop.call_later(
                self.dwell, self.drain_events)

    def submit_threadsafe(self, key: str, *args: List[Any]):
        self.loop.call_soon_threadsafe(self.submit, key, *args)

    def drain_events(self):
        self._scheduled = None
        containers = list(self.pending_events.values())
        self.pending_events.clear()

        for cont in containers:
            try:
                self.callback(*cont.args)
            except Exception as e:
                print('drain_events', e)
                pass
