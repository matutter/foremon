import os
import os.path as op
import re
import shutil
from glob import glob
from secrets import token_hex
from typing import List, Pattern

import pytest
from _pytest.capture import CaptureFixture
from _pytest.fixtures import SubRequest
from colors import color, strip_color
from foremon.display import *

from .fixtures import *

pytestmark = getattr(pytest.mark, 'asyncio')

EXPECT_TIMEOUT = float(os.environ.get('EXPECT_TIMEOUT', '5.0'))

set_display_verbose(True)
set_display_name('pytest')


def get_project_root():
    return op.realpath(op.join(op.dirname(__file__), '..'))


def get_code_dir():
    return op.join(get_project_root(), 'foremon')


def get_version_file():
    return op.join(get_code_dir(), 'VERSION.txt')


def get_input_dir():
    return op.join(get_project_root(), 'tests/input')


def get_input_file(name: str) -> str:
    return op.join(get_input_dir(), name)


def get_sample_file(name: str) -> str:
    return op.join(get_project_root(), 'tests/samples', name)


def get_sample_files(pattern: str) -> List[str]:
    return glob(op.join(get_project_root(), 'tests/samples', pattern))


def mkdirp(path: str) -> None:
    try:
        os.makedirs(path)
    except Exception:
        pass


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
def tempfiles(request: SubRequest) -> Tempfiles:
    t = Tempfiles()
    request.addfinalizer(t.cleanup)
    return t


@pytest.fixture
def sampledir():
    return op.join(op.dirname(__file__), 'samples')


class CapLines:
    # Utilities for accessing cap-fd
    stdout_lines: List[str]
    stdout_prefix: str
    stderr_lines: List[str]
    stderr_prefix: str
    capfd: CaptureFixture

    def __init__(self, capfd: CaptureFixture):
        self.capfd = capfd
        self.stdout_lines = []
        self.stderr_lines = []
        self.stderr_prefix = r'^\[\w+\] '
        self.stdout_prefix = ''

    def stdout_append(self, text: str):
        self.stdout_lines.extend(map(strip_color, text.splitlines()))

    def stderr_append(self, text: str):
        self.stderr_lines.extend(map(strip_color, text.splitlines()))

    def read(self) -> 'CapLines':
        stdout, stderr = self.capfd.readouterr()
        self.stdout_append(stdout)
        self.stderr_append(stderr)
        return self

    def print_match(self, line: str):
        print(color(line, 'green'))

    def print_no_match(self, line: str):
        print(color(line, 'gray'))

    def expect(self, lines: List[str], pattern: str,  prefix: str = '') -> bool:
        reg: Pattern = re.compile(prefix + pattern, re.I)
        while lines:
            line = lines.pop(0).rstrip()
            match = reg.match(line)
            if match:
                self.print_match(line)
                return True
            self.print_no_match(line)
        return False

    def stdout_expect(self, pattern: str) -> bool:
        if not self.stdout_lines:
            self.read()
        return self.expect(self.stdout_lines, pattern, self.stdout_prefix)

    def stderr_expect(self, pattern: str) -> bool:
        if not self.stderr_lines:
            self.read()
        return self.expect(self.stderr_lines, pattern, self.stderr_prefix)

    def cleanup(self):
        self.stderr_lines.clear()
        self.stdout_lines.clear()
        self.capfd.readouterr()

    def dump(self):
        for line in self.stdout_lines + self.stderr_lines:
            print(line)


@pytest.fixture
def output(request: SubRequest, capfd: CaptureFixture):
    cap = CapLines(capfd)
    request.addfinalizer(cap.cleanup)
    return cap


__all__ = [
    'get_code_dir',
    'get_input_dir',
    'get_input_file',
    'get_project_root',
    'get_sample_file',
    'get_sample_files',
    'get_version_file',
    'mkdirp',
    'pytest',
    'pytestmark',
    'sampledir',
    'SubRequest',
    'tempfiles',
    'Tempfiles',
    'output',
    'CapLines'
]
