import asyncio
import signal
from typing import Awaitable, List, Optional, Tuple
from asyncio.subprocess import Process, create_subprocess_shell

from asyncio.base_events import BaseEventLoop

from .display import *
from .config import ForemonConfig

class ForemonTask:
    """
    Container for a script. This container maintains all executions of the script
    and does not support execution multiple instances of the same script in
    parallel.
    """

    _awaitable: Optional[Awaitable]
    alias: str
    pending_signals: List[int]
    process: Optional[Process]
    config: ForemonConfig

    def __init__(self, config: ForemonConfig, loop: Optional[BaseEventLoop] = None):
        self._awaitable = None
        self.config = config
        self.loop = loop or asyncio.get_event_loop()
        self.pending_signals = []
        self.process = None

    @property
    def name(self) -> str:
        alias = self.config.alias
        return alias if alias else 'default'

    @property
    def running(self) -> bool:
        return bool(self.process is not None)

    def send_signal(self, sig: int) -> None:
        if not self.process:
            return
        self.pending_signals.append(sig)
        self.process.send_signal(sig)

    def terminate(self) -> None:
        self.send_signal(self.config.term_signal)

    def process_returncode(self, returncode: int) -> Tuple[bool,bool]:
      if self.config.returncode == returncode:
        return True, True

      # signals are returned as -SIGNAL
      if returncode < 0:
        sig = abs(returncode)
        is_pending = sig in self.pending_signals

        if is_pending and sig == self.config.term_signal:
          # good exit, but do not continue
          return True, False
        elif is_pending:
          # good exit, may contine
          return True, True

      # An unexpected signal or exit occurred, this indicates a script failure
      # and the batch processing should not continue
      return False, False


    async def run(self):
        self._check_loop()

        if self.running:
            return

        self.pending_signals.clear()
        # Execute the batch of scripts serially. If any script exists with
        # an abnormal exit code or encounters an unexpected signal than
        # then processing is stopped
        for script in self.config.scripts:

            display_success(f'starting `{script}`')

            returncode: Optional[int] = None

            try:
                self.process = await create_subprocess_shell(
                  script, stdout=sys.stdout, stderr=sys.stderr, shell=True)

                self._awaitable = self.loop.create_task(self.process.communicate())
                await self._awaitable

                returncode = self.process.returncode
            finally:
                self.process = None
                self._awaitable = None

            exit_ok, should_continue = self.process_returncode(returncode)
            if exit_ok and should_continue:
              continue

            if not exit_ok:
              display_error(
                f'app crashed {returncode} - waiting for file changes before restart')
            else:
              display_warning('cancelled')

            break
        else:
            display_success(
                'clean exit - waiting for changes before restart')
        return

    def _check_loop(self):
        loop = asyncio.get_running_loop()
        if loop != self.loop:
          raise RuntimeError(f'Trying to run {self.name} tasks on wrong loop')


__all__ = ['ForemonTask']
