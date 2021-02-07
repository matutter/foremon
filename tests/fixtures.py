import errno
import os
import os.path as op
import shutil
import sys
import tempfile
from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE, Process
from pathlib import Path
from secrets import token_hex
from typing import List, Optional

import pytest
from _pytest.fixtures import SubRequest

from .fixtures import *

pytestmark = getattr(pytest.mark, 'asyncio')


def get_project_root():
    return op.realpath(op.join(op.dirname(__file__), '..'))


def get_code_dir():
    return op.join(get_project_root(), 'runmon')


def get_version_file():
    return op.join(get_code_dir(), 'VERSION.txt')


def get_input_dir():
    return op.join(get_project_root(), 'tests/input')


class Runmon:

    p: Optional[Process]
    stdout: str
    stderr: str

    def __init__(self):
        self.p = None
        self.stdout = ''
        self.stderr = ''

    @property
    def returncode(self) -> int:
        return self.p.returncode

    async def stop(self):
        self.p.stdin.write_eof()
        stdout, stderr = await self.p.communicate()
        self.stdout = stdout.decode()
        self.stderr = stderr.decode()

    async def input(self, text: str):
        self.p.stdin.write((text+'\n').encode())

    async def spawn(self, *args) -> 'Runmon':
        project_root = get_project_root()
        cmd: str = ' '.join(
            [sys.executable, '-m', 'runmon'] + list(map(str, args)))
        self.p: Process = await create_subprocess_shell(
            cmd,
            stdin=PIPE, stderr=PIPE, stdout=PIPE,
            cwd=project_root,
            shell=True,
            encoding=None,
            env={'TERM': 'mono'})
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
def tempfiles(request: SubRequest) -> Tempfiles:
  t = Tempfiles()
  request.addfinalizer(t.cleanup)
  return t


__all__ = [
    'tempfiles',
    'Tempfiles',
    'Runmon',
    'mkdirp',
    'get_project_root',
    'get_code_dir',
    'get_version_file',
    'get_input_dir',
    'pytestmark'
]
