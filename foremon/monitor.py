import asyncio
import errno
import os.path as op
from asyncio import BaseEventLoop, Queue
from functools import partial
from typing import Any, List, Optional, Set, TextIO

from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

from foremon.config import ForemonConfig
from foremon.errors import ForemonError
from contextlib import contextmanager
from .config import *
from .display import *
from .queue import *
from .task import *


class Monitor:

    _loop: BaseEventLoop
    observer: Observer
    pipe: Optional[TextIO]
    queue: Queue
    stop_timeout: int
    # used to suppress duplicate events (like create+modify when file is touched)
    current_files: Set[str]
    active_tasks: Set[ForemonTask]
    all_tasks: Set[ForemonTask]
    is_terminating: bool
    is_paused: bool

    def __init__(self, pipe=None, loop: BaseEventLoop = None):

        if loop is None:
            loop = asyncio.get_event_loop()

        self.stop_timeout = 5
        self.observer = Observer()
        self.pipe = pipe
        self._loop = loop
        self.queue = Queue()
        self.current_files = set()
        self.active_tasks = set()
        self.all_tasks = set()
        self.is_terminating = False
        self.is_paused = False

    @property
    def loop(self):
        return self._loop

    def add_task(self, task: ForemonTask) -> 'Monitor':

        if task in self.all_tasks:
            raise ForemonError(
                f'cannot add duplicate task {task.name}', errno.EINVAL)

        conf: ForemonConfig = task.config

        if display_verbose():
            display_debug('alias', task.name)
            display_debug('paths', conf.paths)
            display_debug('patterns', conf.patterns)
            display_debug('ignore_defaults', conf.ignore_defaults)
            display_debug('ignore', conf.ignore)
            display_debug('ignore_dirs', conf.ignore_dirs)
            display_debug('ignore_case', conf.ignore_case)
            display_debug('events', list(map(lambda e: e.name, conf.events)))

        for path in list(conf.paths):
            if not op.exists(path):
                display_warning(f'cannot watch {path}, path does not exist')
                conf.paths.remove(path)

        if not conf.paths:
            raise ForemonError(
                'no valid paths specified, cannot add watch task', errno.ENOENT)

        callback = partial(self.queue_task_event, task)

        handler = PatternMatchingEventHandler(
            patterns=conf.patterns,
            ignore_patterns=conf.ignore_defaults + conf.ignore,
            ignore_directories=conf.ignore_dirs,
            case_sensitive=not conf.ignore_case)

        if Events.created in conf.events:
            handler.on_created = callback
        if Events.deleted in conf.events:
            handler.on_deleted = callback
        if Events.moved in conf.events:
            handler.on_moved = callback
        if Events.modified in conf.events:
            handler.on_modified = callback

        for path in conf.paths:
            self.observer.schedule(handler, path, recursive=conf.recursive)

        self.all_tasks.add(task)

        return self

    def reset(self):
        self.observer.unschedule_all()
        self.all_tasks.clear()

    def set_pipe(self, pipe: TextIO):
        # Pipe is usually only set None in testing due to a conflict with
        # Click.testing.CliRunner's implementation.
        try:
            if self.pipe is not None:
                self.loop.remove_reader(self.pipe)
        except:
            pass

        self.pipe = pipe
        if self.pipe is not None:
            self.loop.add_reader(self.pipe, self._repl)

    def queue_all_tasks(self):
        for task in list(self.all_tasks):
            self.queue_task_event(task, None)

    def queue_task_event(self, task: ForemonTask, ev: Optional[FileSystemEvent] = None) -> None:
        if self.is_terminating or self.is_paused:
            return

        task = self.loop.create_task(self.run_task(task, ev))
        self.loop.call_soon_threadsafe(self.queue.put_nowait, task)

    async def run_task(self, task: ForemonTask, trigger: Any) -> None:
        if self.is_terminating or self.is_paused:
            return

        if not self.observer.is_alive():
            return

        # bounce until task is done
        if task in self.active_tasks:
            return

        if task.running:
            return

        self.active_tasks.add(task)
        try:
            await task.run(trigger)
        except Exception as e:
            display_error(f'error from {task.name} task', e)
        finally:
            self.active_tasks.remove(task)

    def restart_tasks(self):
        self.terminate_tasks()
        for task in list(self.all_tasks):
            self.loop.call_later(0.1, self.queue_task_event, task)

    @contextmanager
    def paused(self):
        """
        Stop running tasks while the monitor is paused
        """
        try:
            self.is_paused = True
            yield
        finally:
            self.is_paused = False

    def terminate_tasks(self):
        for task in list(self.all_tasks):
            task.terminate()

    def clear(self):
        self.observer.unschedule_all()
        self.stop()

    def stop(self):
        self.is_terminating = True
        self.terminate_tasks()
        self.observer.stop()
        if self.observer.is_alive():
            self.observer.join(self.stop_timeout)
        self.is_terminating = False

    def start(self, run_on_start: bool = True) -> bool:
        if self.is_terminating:
            return False

        if not self.all_tasks:
            return False

        if self.observer.is_alive():
            return False

        if run_on_start:
            self.queue_all_tasks()

        self.observer.start()
        return True

    async def start_interactive(self, run_on_start: bool = True):
        if not self.start(run_on_start=run_on_start):
            return False

        async def cradle():
            async for task in queueiter(self.queue):
                try:
                    await task
                except Exception as e:
                    display_error('fatal error, shutting down ...', e)
                    break

        try:
            await cradle()
        except (KeyboardInterrupt, EOFError):
            display_debug('stopping ...')
        except Exception as e:
            display_error('fatal error, shutting down ...', e)

        self.stop()

    def handle_input(self, line: str) -> None:
        restart = ['rs', 'restart']
        quit = ['\\q', 'quit', 'exit']
        def startswith(s, l): return any([s.startswith(i) for i in l])

        if startswith(line, restart):
            self.restart_tasks()
            return

        if startswith(line, quit):
            display_debug('stopping ...')
            # stops the cradle
            self.loop.call_soon_threadsafe(self.queue.put_nowait, None)
            if self.pipe is not None:
                self.loop.remove_reader(self.pipe)
            self.stop()
            return

    def _repl(self):
        line = self.pipe.readline().lower()
        self.handle_input(line)
