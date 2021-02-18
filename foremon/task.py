import asyncio
import atexit
import weakref
from asyncio.base_events import BaseEventLoop
from asyncio.subprocess import Process, create_subprocess_shell
from typing import Awaitable, Callable, Coroutine, List, MutableMapping, Optional, Set, Tuple

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
    Container for a script. This class maintains the state of executing scripts.
    Different instances may run in parallel and a single instance can not be run
    concurrently.
    """

    _awaitable: Optional[Awaitable]
    config: ForemonConfig
    before_run_callbacks: List[Callable]
    after_run_callbacks: List[Callable]
    loop: BaseEventLoop
    run_count: int

    def __init__(self, config: ForemonConfig, loop: Optional[BaseEventLoop] = None):
        self._awaitable = None
        self.config = config
        self.loop = loop or asyncio.get_event_loop()
        self.before_run_callbacks = [track_ref]
        self.after_run_callbacks = [untrack_ref]
        self.run_count = 0

    @property
    def name(self) -> str:
        alias = self.config.alias
        return alias if alias else 'default'

    @property
    def running(self) -> bool:
        return bool(self._awaitable is not None)

    def add_before_callback(self, callback: Callable) -> 'ForemonTask':
        if callback not in self.before_run_callbacks:
            self.before_run_callbacks.append(callback)
        return self

    def add_after_callback(self, callback: Callable) -> 'ForemonTask':
        if callback not in self.after_run_callbacks:
            self.after_run_callbacks.append(callback)
        return self

    def terminate(self) -> None:
        pass

    async def _run_callbacks(self, callbacks: List, context: Any, trigger: Any):
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self, trigger)
                else:
                    callback(self, trigger)
            except Exception as e:
                display_error('Error from callback', e)

    def before_run(self, trigger: Any) -> Coroutine:
        return self._run_callbacks(self.before_run_callbacks[:], self, trigger)

    def after_run(self, trigger: Any) -> Coroutine:
        return self._run_callbacks(self.after_run_callbacks[:], self, trigger)

    async def run(self, trigger: Optional[Any] = None) -> None:
        if self.running:
            return

        # self.running will return True at this point
        self._awaitable = self.loop.create_future()
        self.run_count += 1
        try:
            await self._run(trigger)
        except Exception as e:
            display_error(f'fatal error from task {self.name}', e)
        finally:
            self._awaitable.set_result(None)
            self._awaitable = None
        return

    async def _run(self, trigger: Optional[Any] = None) -> None:
        pass


class ScriptTask(ForemonTask):

    process: Optional[Process]
    pending_signals: List[int]

    def __init__(self, config: ForemonConfig, loop: BaseEventLoop = None):
        super().__init__(config, loop)
        self.process = None
        self.pending_signals = []

    def terminate(self) -> None:
        self.send_signal(self.config.term_signal)

    async def _run(self, trigger: Optional[Any] = None) -> None:
        await self.before_run(trigger)

        self.pending_signals.clear()
        # Execute script batch serially. If any script exits with an abnormal
        # exit code or encounters an unexpected signal then processing is
        # stopped.
        for script in self.config.scripts:

            display_success(f'starting `{script}`')

            returncode: Optional[int] = None
            last_pid: int = None

            try:
                self.process = await create_subprocess_shell(
                    script, stdout=sys.stdout, stderr=sys.stderr,
                    shell=True, env=self.config.get_env())

                last_pid = self.process.pid

                await self.process.communicate()

                returncode = self.process.returncode
            finally:
                self.process = None

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

        await self.after_run(trigger)

        return

    def send_signal(self, sig: int) -> None:
        if not self.process:
            return
        self.pending_signals.append(sig)
        try:
            self.process.send_signal(sig)
        except ProcessLookupError as e:
            # He's dead, Jim
            pass

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

        # An unexpected signal or exit occurred, this usually means a script
        # failed (or stopped externally) and that batch processing should stop.
        return False, False


__all__ = ['ForemonTask', 'ScriptTask']
