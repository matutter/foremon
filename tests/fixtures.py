from water.display import *
from water.atexit_handler import *
import asyncio
from asyncio.tasks import ALL_COMPLETED, FIRST_COMPLETED, Task
import errno
import os
import os.path as op
import re
import shutil
import sys
import time
from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE, Process
from secrets import token_hex
from typing import Coroutine, List, Optional, Set, Tuple, Pattern
import pytest
from _pytest.fixtures import SubRequest

from .fixtures import *

pytestmark = getattr(pytest.mark, 'asyncio')

EXPECT_TIMEOUT = float(os.environ.get('EXPECT_TIMEOUT', '5.0'))

set_display_verbose(True)
set_display_name('pytest')


def get_project_root():
    return op.realpath(op.join(op.dirname(__file__), '..'))


def get_code_dir():
    return op.join(get_project_root(), 'water')


def get_version_file():
    return op.join(get_code_dir(), 'VERSION.txt')


def get_input_dir():
    return op.join(get_project_root(), 'tests/input')


class WaterBootstrap:

    p: Optional[Process]
    stdout: str
    stderr: str
    _stdout_awaiter: Task
    _stderr_awaiter: Task
    coverage: bool

    def __init__(self, coverage: bool = False):
        self.p = None
        self.stdout = ''
        self.stderr = ''
        self._stdout_awaiter = None
        self._stderr_awaiter = None
        self.coverage = coverage

    @property
    def returncode(self) -> int:
        if self.p.returncode < 0:
            if -self.p.returncode == self.expected_signal:
                return 0
        return self.p.returncode

    def signal(self, sig: int):
        self.expected_signal = sig
        if self.p:
            self.p.send_signal(signal=sig)

    async def _write_stdin(self, s: str, eof: bool = False):
        if not self.p:
            return
        print(s)
        data = (s+"\n").encode()
        self.p.stdin.write(data)
        await self.p.stdin.drain()
        if eof:
            self.p.stdin.write_eof()

    def _read_stdout(self):
        if self._stdout_awaiter is None:
            async def read():
                if not self.p:
                    return
                data: bytes = await self.p.stdout.readline()
                line = data.decode()
                self.stdout += line
                self._stdout_awaiter = None
                line = line.rstrip()
                print(line)
                self._stdout_awaiter = None
                return line
            self._stdout_awaiter = asyncio.ensure_future(read())
        return self._stdout_awaiter

    def _read_stderr(self):
        if self._stderr_awaiter is None:
            async def read():
                if not self.p:
                    return
                data: bytes = await self.p.stderr.readline()
                line = data.decode()
                self.stderr += line
                self._stderr_awaiter = None
                line = line.rstrip()
                print(line)
                self._stderr_awaiter = None
                return line
            self._stderr_awaiter = asyncio.ensure_future(read())
        return self._stderr_awaiter

    async def expect(self, pattern: str, timeout: float = EXPECT_TIMEOUT) -> bool:
        """
        Expect matching text on stderr or stdout within a given timeframe. If
        the timeframe is exceeded without the expected output matching False is
        returned.
        """

        if not self.p:
            raise Exception('Invalid state, the process is not started')

        prefix = r'^\[water\] '
        pattern: Pattern = re.compile(prefix + pattern, re.IGNORECASE)
        remaining_timeout: float = float(timeout)
        p: Process = self.p
        while 1:

            if remaining_timeout < 0:
                return False

            start = time.time()

            complete: Set[Task]
            pending: Set[Task]
            task: Task
            complete, pending = await asyncio.wait([
                self._read_stderr(),
                self._read_stdout()
            ], timeout=remaining_timeout, return_when=FIRST_COMPLETED)

            # decrease timeout for next loop
            end = time.time()
            remaining_timeout -= (end-start)

            for task in complete:
                line: str = task.result()
                match = pattern.match(line)

                #display_debug('TEST', pattern.pattern, line)
                if match is not None:
                    display_success('matched ' + match.string)
                    return True
        return False

    async def stop(self):
        await self._write_stdin('exit', True)

        p: Process = self.p

        stderr = self._read_stderr()
        stdout = self._read_stdout()
        wait: Coroutine = p.wait()
        pending = []

        while p.returncode is None:

            complete, pending = await asyncio.wait([wait, stderr, stdout], timeout=EXPECT_TIMEOUT, return_when=FIRST_COMPLETED)

            if wait in complete:
                break
            if stderr in complete:
                stderr = self._read_stderr()
            if stdout in complete:
                stdout = self._read_stdout()

        # no effect if done or program exit
        if pending:
            await asyncio.wait(pending, return_when=ALL_COMPLETED)

        stdout, stderr = await p.communicate()
        stdout = stdout.decode()
        stderr = stderr.decode()
        self.stdout += stdout
        self.stderr += stderr
        remove_pid(p.pid)

    async def input(self, text: str):
        self.p.stdin.write((text+'\n').encode())

    def reset(self):
        self.p = None
        self.stdout = ''
        self.stderr = ''
        self._stdout_awaiter = None
        self._stderr_awaiter = None

    async def spawn(self, *args) -> 'WaterBootstrap':
        self.reset()
        project_root = get_project_root()

        if self.coverage:
            # append coverage to .coverage every time this executes
            executable = [sys.executable, '-m', 'coverage', 'run', '-a', '--include="water/*"']
        else:
            executable = [sys.executable]

        args = list(map(str, args))
        cmd: str = ' '.join(executable + ['-m', 'water'] + args)

        display_debug('SPAWN', cmd)

        self.p: Process = await create_subprocess_shell(
            cmd,
            stdin=PIPE, stderr=PIPE, stdout=PIPE,
            cwd=project_root,
            shell=True,
            encoding=None,
            env={'TERM': 'mono'})

        add_pid(self.p.pid)

        return self


def mkdirp(path: str) -> None:
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


class Tempfiles:

    root: str
    files: List[str]
    dirs: List[str]

    def __init__(self):
        self.root = op.join(get_input_dir(), token_hex(8))
        self.files = []
        self.dirs = []

    def make_dir(self, path: str) -> str:
        if not path.startswith(self.root):
            path = op.join(self.root, path)
        mkdirp(path)
        self.dirs.append(path)
        return path

    def make_file(self, path: str) -> str:
        if not path.startswith(self.root):
            path = op.join(self.root, path)
        self.make_dir(op.dirname(path))
        with open(path, 'wb') as fd:
            fd.write(b'\000\000\000\000')
        self.files.append(path)
        return path

    def make_files(self, files: List[str]) -> List[str]:
        paths = [op.join(self.root, f) for f in files]

        for p in sorted(paths[:]):
            if p.endswith('/'):
                self.make_dir(p)
            else:
                self.make_file(p)

        self._fix_files()

        return paths

    def cleanup(self):
        try:
            shutil.rmtree(self.root)
        except FileNotFoundError:
            pass

    def _fix_files(self):
        self.files = sorted(list(set(self.files[:])))
        self.dirs = sorted(list(set(self.dirs[:])))


@pytest.fixture
async def bootstrap(request: SubRequest) -> WaterBootstrap:
    coverage = request.config.getoption('--coverage')
    bs = WaterBootstrap(coverage=coverage)
    return bs


@pytest.fixture
def tempfiles(request: SubRequest) -> Tempfiles:
    t = Tempfiles()
    request.addfinalizer(t.cleanup)
    return t


@pytest.fixture
def sampledir():
    return op.join(op.dirname(__file__), 'samples')

@pytest.fixture(scope='session', autouse=True)
def cleanup_old_coverage(request: SubRequest):
    if request.config.getoption('--coverage'):
        try:
            coverage_file = op.join(get_project_root(), '.coverage')
            os.remove(coverage_file)
        except:
            pass

__all__ = [
    'tempfiles',
    'Tempfiles',
    'WaterBootstrap',
    'mkdirp',
    'get_project_root',
    'get_code_dir',
    'get_version_file',
    'get_input_dir',
    'pytestmark',
    'pytest',
    'sampledir',
    'SubRequest',
    'bootstrap'
]
