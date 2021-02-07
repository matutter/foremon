import sys
from functools import partial
from typing import Any, Callable, Coroutine, List, Optional
from subprocess import run as subprocess_run
from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer
import signal

from .display import *

def want_list(l: Any, default: List[str]) -> List[str]:
    if not l:
        return default[:]
    if not isinstance(l, list):
        l = [l]
    return list(map(str, l))


class Monitor:

    before_run_callbacks: Callable[['Monitor', FileSystemEvent, List[str]], None]
    handlers: List[PatternMatchingEventHandler]
    scripts: List[List[str]]
    exec_queue: List[List[str]]
    stop_timeout: int
    observer: Observer

    def __init__(self):
        self.before_run_callbacks = []
        self.handlers = []
        self.scripts = []
        self.stop_timeout = 5
        self.observer = Observer()
        self.exec_queue = []

    def exec_queue_process(self):
        try:
            while self.exec_queue:
                batch = self.exec_queue.pop(0)
                self.run_batch(batch)
        except Exception as e:
            display_error('an exec error occurred', e)


    def run_batch(self, batch: List[str]):
        for script in batch:
            try:
                display_info('exec: ' + script)
                p = subprocess_run(script, stdout=sys.stdout, stderr=sys.stderr, shell=True)
                if p.returncode != 0:
                    display_error(f'script returned {p.returncode}, exec stopped')
                    break
            except Exception as e:
                display_error(f'Error in script: {script}', e)

    def before_run(self, callback:Callable[['Monitor', FileSystemEvent, List[str]], None]):
        self.before_run_callbacks.append(callback)

    def add_runner(self,
                   scripts: List[str],
                   paths: Optional[List[str]] = None,
                   patterns: Optional[List[str]] = None,
                   default_pattern: str = '*',
                   ignore: Optional[List[str]] = None,
                   ignore_hidden: bool = True,
                   ignore_dirs: bool = True,
                   ignore_case: bool = True,
                   recursive: bool = True):

        paths = want_list(paths, ['.'])
        patterns = want_list(patterns, [default_pattern])
        ignore = want_list(ignore, [])
        if ignore_hidden:
            ignore.insert(0, '.*')

        handler = PatternMatchingEventHandler(
            patterns, ignore, ignore_dirs, not ignore_case)
        self.handlers.append(handler)
        self.scripts.append(scripts)
        handler.on_any_event = partial(self.on_event, scripts)

        for path in paths:
            self.observer.schedule(handler, path, recursive=recursive)

    def clear(self):
        self.observer.unschedule_all()
        self.handlers.clear()
        self.scripts.clear()
        self.stop()

    def on_event(self, scripts: List[str], ev: FileSystemEvent):
        for cb in self.before_run_callbacks:
            try:
                cb(self, ev, scripts)
            except Exception as e:
                display_error('encountered pre run error', e)
        self.queue_script(scripts)

    def queue_script(self, scripts: List[str]):
        scripts = want_list(scripts, [])
        if scripts:
            self.exec_queue.append(scripts[:])
        self.start_queue_worker()

    def queue_all_scripts(self):
        list(map(self.queue_script, self.scripts[:]))
        self.start_queue_worker()

    def start_queue_worker(self):
        self.exec_queue_process()

    def stop(self):
        self.clear_queue()
        self.observer.stop()
        self.observer.join(self.stop_timeout)

    def start(self, run_on_start: bool = True) -> bool:
        if not self.scripts:
            return False

        if self.observer.isAlive():
            return False

        if run_on_start:
            self.queue_all_scripts()

        self.observer.start()
        return True

    def start_interactive(self, run_on_start: bool = True):
        if not self.start(run_on_start=run_on_start):
            return False

        try:
            self._repl()
        except KeyboardInterrupt:
            pass
        except EOFError:
            pass
        except Exception as e:
            display_error('an unhandled error occurred', e)

        self.stop()

    def clear_queue(self):
        self.exec_queue.clear()

    def _repl(self):
        restart = ['rs', 'restart']
        quit = ['\q', 'quit', 'exit']
        def startswith(s, l): return any([s.startswith(i) for i in l])

        for line in sys.stdin.readlines():
            line = line.lower()

            if startswith(line, restart):
                self.clear_queue()
                self.queue_all_scripts()
                continue

            if startswith(line, quit):
                break

