import asyncio
import time
from asyncio import BaseEventLoop
from asyncio.events import TimerHandle
from collections import defaultdict
from typing import Any, Callable, DefaultDict, List, Optional, Tuple

from foremon.display import display_error, display_warning
from foremon.task import ForemonTask


class EventContainer:
    args: Optional[Tuple[ForemonTask, Any]]
    reset_count: int
    set_at: int
    warn_after: int

    def __init__(self) -> None:
        self.set_at = -1
        self.args = None
        self.reset_count = 0
        self.warn_after = 100

    def set(self, task: ForemonTask, ev: Any):
        if self.set_at != -1:
            self.reset_count += 1

        self.set_at = time.time()
        self.args = (task, ev)

        if self.reset_count < self.warn_after:
            return

        self.warn_after += 100
        display_warning('detected high event volume - suppressed',
                        self.reset_count, 'events')


class Debounce:
    callback: Callable
    dwell = float
    pending_events: DefaultDict
    _scheduled: Optional[TimerHandle]

    def __init__(self,
                 dwell: float,
                 callback: Callable[[ForemonTask, Any], None],
                 loop: Optional[BaseEventLoop] = None):
        self.loop = loop or asyncio.get_event_loop()
        self.callback = callback
        self.dwell = dwell
        self.pending_events = defaultdict(EventContainer)
        self._scheduled = None

    def submit(self, task: ForemonTask, ev: Any):
        if self.dwell <= 0.0:
            self.callback(task, ev)
        else:
            self.pending_events[task.name].set(task, ev)
            if self._scheduled:
                self._scheduled.cancel()
            self._scheduled = self.loop.call_later(
                self.dwell, self.drain_events)

    def submit_threadsafe(self, task: ForemonTask, ev: Any):
        self.loop.call_soon_threadsafe(self.submit, task, ev)

    def drain_events(self):
        self._scheduled = None
        containers = list(self.pending_events.values())
        self.pending_events.clear()

        def get_order(cont: EventContainer):
            return cont.args[0].config.order

        cont: EventContainer
        for cont in sorted(containers, key=get_order):
            try:
                self.callback(*cont.args)
            except Exception as e:
                display_error('drain callback error', e)
