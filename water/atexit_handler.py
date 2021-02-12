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

@atexit.register
def cleanup_pids():
    global CHILD_PIDS
    sig = 'SIGTERM'
    for pid in CHILD_PIDS:
      try:
        pgid = os.getpgid(pid)
        display_debug('sending', sig, f'{getattr(signal, sig)}', f'pgid={pgid}', f'pid={pid}')
        os.killpg(os.getpgid(pid), getattr(signal, sig))
        os.kill(pid, getattr(signal, sig))
      except:
        pass

__all__ = ['add_pid', 'remove_pid']
