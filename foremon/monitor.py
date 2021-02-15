import asyncio
import signal
import sys
from asyncio import BaseEventLoop, Queue
from asyncio.subprocess import Process, create_subprocess_shell
from functools import partial
from typing import Any, Callable, List, Optional, Set, TextIO

from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

from .atexit_handler import *
from .display import *
from .queue import *
from .task import *


def want_list(l: Any, default: List[str], unique: bool = True) -> List[str]:
    if not l:
        l = default[:]
    if not isinstance(l, list):
        l = [l]
    if unique:
        return list(map(str, l))
    else:
        return list(set(map(str, l)))


class Monitor:

    before_run_callbacks: Callable[[
        'Monitor', FileSystemEvent, List[str]], None]
    current_process: Optional[Process]
    current_signal: int
    loop: BaseEventLoop
    observer: Observer
    pipe: TextIO
    queue: Queue
    scripts: List[List[str]]
    stop_timeout: int
    # used to suppress duplicate events (like create+modify when file is touched)
    current_files: Set[str]
    is_parallel: bool
    is_terminating: bool

    def __init__(self, parallel: bool = False, pipe=sys.stdin, loop: BaseEventLoop = None):
        self.before_run_callbacks = []
        self.scripts = []
        self.stop_timeout = 5
        self.observer = Observer()
        self.pipe = pipe
        self.current_signal = 0
        self.current_process = None
        self.loop = loop if loop else asyncio.get_event_loop()
        self.queue = Queue(loop=self.loop)
        self.current_files = set()
        self.is_parallel = parallel
        self.is_terminating = False

    def add_runner(self,
                   scripts: List[str],
                   paths: Optional[List[str]] = None,
                   patterns: Optional[List[str]] = None,
                   default_pattern: str = '*',
                   ignore: Optional[List[str]] = None,
                   ignore_hidden: bool = True,
                   ignore_dirs: bool = True,
                   ignore_case: bool = True,
                   recursive: bool = True) -> bool:

        case_sensitive = not ignore_case
        paths = want_list(paths, ['.'], unique=True)
        patterns = want_list(patterns, [default_pattern], unique=True)
        ignore = want_list(ignore, [], unique=True)
        if ignore_hidden:
            ignore.insert(0, '.*')

        display_debug('paths', paths)
        display_debug('patterns', patterns)
        display_debug('ignore', ignore)
        display_debug('ignore_dirs', ignore_dirs)
        display_debug('case_sensitive', case_sensitive)

        handler = PatternMatchingEventHandler(
            patterns, ignore, ignore_dirs, case_sensitive)
        self.scripts.append(scripts)
        cb = partial(self.on_event, scripts)
        handler.on_created = cb
        handler.on_deleted = cb
        handler.on_modified = cb
        handler.on_moved = cb

        missing_paths: List[str] = []
        for path in paths:
            if not os.path.exists(path):
                missing_paths.append(path)
                continue
            self.observer.schedule(handler, path, recursive=recursive)

        if len(missing_paths) == len(paths):
            display_error('cannot find watch paths, nothing to do...')
            return False

        if missing_paths:
            display_warning('some paths cannot be watched -' +
                            " ".join(missing_paths))

        return True

    def get_exit_message(self, msg: str, extra: str):
        if self.is_terminating:
            return msg
        else:
            return ' - '.join([msg, extra])

    async def run_batch(self, batch: List[str]):
        for script in batch:
            try:
                # Reset signal
                self.current_signal = 0
                code = await self.run_one_script(script)
                if code == 0:
                    pass
                # The -(returncode) is the signal it received
                elif -code == self.current_signal:
                    pass
                else:
                    display_error(self.get_exit_message(
                        f'app crashed {code}', 'waiting for file changes before starting...'))
                    break
            except Exception as e:
                display_error(f'exec error', e)
                break
        else:
            display_success(self.get_exit_message(
                'clean exit', 'waiting for changes before restart'))

    async def exec_task(self, batch: List[str], ev: Optional[FileSystemEvent] = None):
        try:
            await self.run_batch(batch)
        except Exception as e:
            display_error('an exec error occurred', e)

        if ev is not None and ev.src_path in self.current_files:
            self.current_files.remove(ev.src_path)

    async def run_one_script(self, script: str) -> int:
        display_success(f'starting `{script}`')
        p: Process = await create_subprocess_shell(
            script, stdout=sys.stdout, stderr=sys.stderr, shell=True)
        self.set_current_process(p)
        try:
            await p.communicate()
        finally:
            self.set_current_process(None)
        return p.returncode

    def set_current_process(self, p: Optional[Process]):
        if p is None and self.current_process is not None:
            remove_pid(self.current_process.pid)
        if p is not None:
            add_pid(p.pid)
        self.current_process = p

    def signal_process(self, sig: int):
        if self.current_process:
            self.current_signal = sig
            self.current_process.send_signal(sig)

    def before_run(self, callback: Callable[['Monitor', FileSystemEvent, List[str]], None]):
        self.before_run_callbacks.append(callback)

    def clear(self):
        self.observer.unschedule_all()
        self.scripts.clear()
        self.stop()

    def start_all_tasks(self):
        list(map(self.queue_exec_task, self.scripts[:]))

    def on_event(self, batch: List[str], ev: FileSystemEvent):

        if ev.src_path in self.current_files:
            # Suppress - event being processed on this file
            display_debug(f'file busy - skipping {ev.event_type} {ev.src_path}')
            return

        self.current_files.add(ev.src_path)

        if not batch:
            return

        for cb in self.before_run_callbacks:
            try:
                cb(self, ev, batch)
            except Exception as e:
                display_error('encountered pre run error', e)

        display_success('restarting due to changes...')
        self.queue_exec_task(batch, ev)

    def queue_exec_task(self, batch: List[str], ev: Optional[FileSystemEvent] = None):
        batch = want_list(batch, [])
        if not batch:
            return

        task = self.loop.create_task(self.exec_task(batch, ev))
        self.loop.call_soon_threadsafe(self.queue.put_nowait, task)

    def stop(self):
        self.is_terminating = True
        self.observer.stop()
        if self.observer.is_alive():
            self.observer.join(self.stop_timeout)

        p = self.current_process
        if p:
            try:
                # BUG: This has no effect when run via py.test, but works from command-line.
                self.current_signal = signal.SIGKILL
                display_warning(f'terminating {p.pid}')
                p.kill()
            except Exception as e:
                pass

    def start(self, run_on_start: bool = True) -> bool:
        if not self.scripts:
            return False

        if self.observer.is_alive():
            return False

        if run_on_start:
            self.loop.call_soon(self.start_all_tasks)

        self.observer.start()
        return True

    def start_interactive(self, run_on_start: bool = True):
        if not self.start(run_on_start=run_on_start):
            return False

        async def serial_cradle():
            while True:
                try:
                    task = await self.queue.get()
                    if task == None: break
                    await task
                except Exception as e:
                    display_error('unhandled error', e)
                    break

        async def parallel_cradle():
            async for task in queueiter(self.queue):
                try:
                    await task
                except Exception as e:
                    display_error('unhandled error', e)
                    break

        cradle = parallel_cradle if self.is_parallel else serial_cradle

        try:
            self.loop.add_reader(self.pipe, self._repl)
            self.loop.run_until_complete(cradle())
        except KeyboardInterrupt:
            pass
        except EOFError:
            pass
        except Exception as e:
            display_error('an unhandled error occurred', e)

        self.stop()

    def _repl(self):
        restart = ['rs', 'restart']
        quit = ['\\q', 'quit', 'exit']
        def startswith(s, l): return any([s.startswith(i) for i in l])
        line = self.pipe.readline().lower()

        if startswith(line, restart):
            self.signal_process(signal.SIGTERM)
            self.start_all_tasks()
            return

        if startswith(line, quit):
            display_debug('stopping ...')
            # stops the cradle
            self.loop.call_soon_threadsafe(self.queue.put_nowait, None)
            self.loop.remove_reader(self.pipe)
            self.stop()
            return
