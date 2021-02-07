import os
import sys
import traceback
from typing import Optional
from colors import color as Color256

DISPLAY_NAME = ''

USE_COLORS = '256' in os.environ.get('TERM', '')


def get_display_name():
    global DISPLAY_NAME
    return DISPLAY_NAME


def set_display_name(name: str):
    global DISPLAY_NAME
    DISPLAY_NAME = name


def colored(*args: str, color: Optional[str] = None):
    msg = ' '.join(filter(lambda f: f, map(str, args)))
    if color and USE_COLORS:
        return Color256(msg, color)
    return msg


def display(msg: str, color: Optional[str] = None):
    prefix = get_display_name()
    if prefix:
        prefix = '[' + prefix + ']'
    sys.stderr.write(colored(prefix, msg, color=color) + "\n")


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
