
import re
import pytest
from typing import List, Pattern
from _pytest.capture import CaptureFixture
from _pytest.fixtures import SubRequest

from colors import color, strip_color

class CapLines:
  # Utilities for accessing cap-fd
  stdout_lines: List[str]
  stderr_lines: List[str]
  capfd: CaptureFixture

  def __init__(self, capfd: CaptureFixture):
    self.capfd = capfd
    self.stdout_lines = []
    self.stderr_lines = []

  def read(self) -> 'CapLines':
    if self.stderr_lines or self.stdout_lines: return
    stdout, stderr = self.capfd.readouterr()
    self.stdout_lines = list(stdout.splitlines())
    self.stderr_lines = list(stderr.splitlines())
    return self

  def print_match(self, line: str):
    print(color(line, 'green'))

  def print_no_match(self, line: str):
    print(color(line, 'gray'))

  def stdout_expect(self, pattern: str):
    self.read()
    reg: Pattern = re.compile(pattern, re.I)
    while self.stdout_lines:
      line = self.stdout_lines.pop(0).rstrip()
      match = reg.match(line)
      if match:
        self.print_match(line)
        return True
      self.print_no_match(line)
    return False

  def stderr_expect(self, pattern: str):
    self.read()
    prefix = r'^\[\w+\] '
    reg: Pattern = re.compile(prefix + pattern, re.I)
    while self.stderr_lines:
      line = strip_color(self.stderr_lines.pop(0).rstrip())
      match = reg.match(line)
      if match:
        self.print_match(line)
        return True
      self.print_no_match(line)
    return False

  def cleanup(self):
    self.stderr_lines.clear()
    self.stdout_lines.clear()
    self.capfd.readouterr()

@pytest.fixture
def output(request: SubRequest, capfd: CaptureFixture):
  cap = CapLines(capfd)
  request.addfinalizer(cap.cleanup)
  return cap