import asyncio
import atexit
import weakref
from asyncio.base_events import BaseEventLoop
from asyncio.subprocess import Process, create_subprocess_shell
from typing import Awaitable, Callable, List, Optional, Set, Tuple

from .config import ForemonConfig
from .display import *

ACTIVE_TASKS: Set['weakref.ReferenceType["ForemonTask"]'] = set()


def track_ref(task: 'ForemonTask', _):
    global ACTIVE_TASKS
    ACTIVE_TASKS.add(weakref.ref(task))


def untrack_ref(task: 'ForemonTask', _):
    global ACTIVE_TASKS
    try:
        ACTIVE_TASKS.remove(weakref.ref(task))
    except KeyError:
        pass


@atexit.register
def terminate_active_tasks():
    global ACTIVE_TASKS
    for ref in ACTIVE_TASKS:
        try:
            task = ref()
            if task:
                task.terminate()
        except ProcessLookupError:
            pass  # Normal occurs
        except Exception:
            pass


class ForemonTask:
    """
    Container for a script. This container maintains all executions of the script
    and does not support execution multiple instances of the same script in
    parallel.
    """

    _awaitable: Optional[Awaitable]
    alias: str
    pending_signals: List[int]
    process: Optional[Process]
    config: ForemonConfig
    before_run_callbacks: List[Callable]
    after_run_callbacks: List[Callable]
    trigger: Optional[Any]

    def __init__(self, config: ForemonConfig, loop: Optional[BaseEventLoop] = None):
        self._awaitable = None
        self.config = config
        self.loop = loop or asyncio.get_event_loop()
        self.pending_signals = []
        self.process = None
        self.before_run_callbacks = [track_ref]
        self.after_run_callbacks = [untrack_ref]
        self.trigger = None

    @property
    def name(self) -> str:
        alias = self.config.alias
        return alias if alias else 'default'

    @property
    def running(self) -> bool:
        return bool(self.process is not None)

    def add_before_callback(self, callback: Callable) -> 'ForemonTask':
        self.before_run_callbacks.append(callback)
        return self

    def add_after_callback(self, callback: Callable) -> 'ForemonTask':
        self.after_run_callbacks.append(callback)
        return self

    def send_signal(self, sig: int) -> None:
        if not self.process:
            return
        self.pending_signals.append(sig)
        self.process.send_signal(sig)

    def terminate(self) -> None:
        self.send_signal(self.config.term_signal)

    def process_returncode(self, returncode: int) -> Tuple[bool, bool]:
        if self.config.returncode == returncode:
            return True, True

        # signals are returned as -SIGNAL
        if returncode < 0:
            sig = abs(returncode)
            is_pending = sig in self.pending_signals

            if is_pending and sig == self.config.term_signal:
                # good exit, but do not continue
                return True, False
            elif is_pending:
                # good exit, may contine
                return True, True

        # An unexpected signal or exit occurred, this indicates a script failure
        # and the batch processing should not continue
        return False, False

    async def before_run(self):
        for callback in self.before_run_callbacks[:]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self, self.trigger)
                else:
                    callback(self, self.trigger)
            except Exception as e:
                display_error('Error from callback', e)

    async def after_run(self):
        for callback in self.after_run_callbacks[:]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self, self.trigger)
                else:
                    callback(self, self.trigger)
            except Exception as e:
                display_error('Error from callback', e)

    async def run(self, trigger: Optional[Any] = None):
        self._check_loop()

        if self.running:
            return

        self.trigger = trigger

        await self.before_run()

        self.pending_signals.clear()
        # Execute the batch of scripts serially. If any script exists with
        # an abnormal exit code or encounters an unexpected signal than
        # then processing is stopped
        for script in self.config.scripts:

            display_success(f'starting `{script}`')

            returncode: Optional[int] = None
            last_pid: int = None

            try:
                self.process = await create_subprocess_shell(
                    script, stdout=sys.stdout, stderr=sys.stderr, shell=True)

                last_pid = self.process.pid

                self._awaitable = self.loop.create_task(
                    self.process.communicate())
                await self._awaitable

                returncode = self.process.returncode
            finally:
                self.process = None
                self._awaitable = None

            exit_ok, should_continue = self.process_returncode(returncode)
            if exit_ok and should_continue:
                continue

            if not exit_ok:
                display_error(
                    f'app crashed {returncode} - waiting for file changes before restart')
            else:
                display_warning(f'terminated {last_pid} - `{script}`')

            break
        else:
            display_success(
                'clean exit - waiting for changes before restart')

        await self.after_run()

        self.trigger = None

        return

    def _check_loop(self):
        loop = asyncio.get_event_loop()
        if loop is None: return
        if loop != self.loop:
            raise RuntimeError(
                f'Trying to run {self.name} tasks on wrong loop')


__all__ = ['ForemonTask']
