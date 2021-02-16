import os
import sys
import traceback
from typing import Any, Callable, Optional
from colors import color as Color256

DISPLAY_NAME = ''
DISPAY_VERBOSE = False
DISPLAY_WRITER = None
USE_COLORS = '256' in os.environ.get('TERM', '')

def display_verbose() -> bool:
  global DISPAY_VERBOSE
  return DISPAY_VERBOSE

def set_display_verbose(val: bool):
  global DISPAY_VERBOSE
  DISPAY_VERBOSE = val

def get_display_name():
    global DISPLAY_NAME
    return DISPLAY_NAME


def set_display_name(name: str):
    global DISPLAY_NAME
    DISPLAY_NAME = name

def default_write(text: str):
    sys.stderr.write(text)
    sys.stderr.flush()

def display_get_writer() -> Callable[[str], None]:
  global DISPLAY_WRITER
  if DISPLAY_WRITER is None:
    return default_write
  return DISPLAY_WRITER


def display_set_writer(writer: Callable[[str], None]) -> None:
  global DISPLAY_WRITER
  DISPLAY_WRITER = writer


def colored(*args: str, color: Optional[str] = None):
    msg = ' '.join(filter(lambda f: f, map(str, args)))
    if color and USE_COLORS:
        return Color256(msg, color)
    return msg


def display(msg: str, color: Optional[str] = None):
    prefix = get_display_name()
    if prefix:
        prefix = '[' + prefix + ']'
    text = colored(prefix, msg, color=color) + "\n"
    display_get_writer()(text)


def display_warning(msg: str):
    display(msg, color='yellow')


def display_info(msg: str):
    display(msg, color='cyan')


def display_error(msg: str, e: Exception = None):
    if e:
      ex = traceback.format_exception(type(e), e, e.__traceback__)
      ex.insert(0, msg)
      msg = "\n".join(ex)

    display(msg, color='red')

def display_success(*msg: Any):
  display(' '.join(map(str, msg)), 'green')

def display_debug(*msg: Any):
  if display_verbose():
    display(' '.join(map(str, msg)), 'blue')
