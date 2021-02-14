import atexit
import signal
import os

from .display import display_debug

CHILD_PIDS = set()


def add_pid(pid: int):
    global CHILD_PIDS
    CHILD_PIDS.add(pid)


def remove_pid(pid: int):
    global CHILD_PIDS
    if pid in CHILD_PIDS:
        CHILD_PIDS.remove(pid)


def kill_pid(pid: int, sig: str = None, group: bool = False) -> None:
    try:
        pgid = os.getpgid(pid)
        display_debug('sending', sig,
                      f'{getattr(signal, sig)}', f'pgid={pgid}', f'pid={pid}')
        if group:
            os.killpg(os.getpgid(pid), getattr(signal, sig))
        os.kill(pid, getattr(signal, sig))
    except:
        pass


@atexit.register
def cleanup_pids():
    global CHILD_PIDS
    for pid in CHILD_PIDS:
        kill_pid(pid, sig='SIGTERM')


__all__ = ['add_pid', 'remove_pid', 'kill_pid']
