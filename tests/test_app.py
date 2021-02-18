import os
import os.path as op
from typing import Optional
from unittest.mock import MagicMock

from foremon.app import Foremon
from foremon.config import ForemonOptions
from foremon.display import *
from foremon.task import ScriptTask
from pytest_mock.plugin import MockerFixture
from watchdog.events import FileSystemEvent

from .cli_fixtures import *
from .fixtures import *


@pytest.fixture
def norun(mocker: MockerFixture) -> MagicMock:
    mocker.patch('foremon.app.Foremon.get_pipe', lambda _: None)
    mock: MagicMock = mocker.MagicMock(name='Foremon._run')
    mocker.patch('foremon.app.Foremon._run', new=mock)
    spy = mocker.spy(Foremon, 'run_forever')
    return spy


def test_app_skip_tasks(norun, output: CapLines, tempfiles: Tempfiles):

    config = tempfiles.make_file("config.toml", content="""
    [tool.foremon]
    scripts = ["true"]

        [tool.foremon.other1]

        [tool.foremon.other2]
        scripts = ["true"]
        skip = true
    """)

    options = ForemonOptions(config_file=config, use_all=True, verbose=False)
    Foremon(options).run_forever()
    assert output.stderr_expect('task default ready.*')
    assert output.stderr_expect('task other1.*skipped.*scripts.*empty')
    assert output.stderr_expect('task other2.*skipped')


async def test_app_log_event_type(norun, output: CapLines, tempfiles: Tempfiles):

    trigger = tempfiles.make_file('trigger')

    config = tempfiles.make_file("config.toml", content=f"""
    [tool.foremon]
    paths = ["{op.dirname(trigger)}"]
    scripts = ["echo test123"]
    """)

    failed: bool = False
    options = ForemonOptions(config_file=config, verbose=True)
    f = Foremon(options)

    def do_modify():
        display_debug('triggering modify')
        with open(trigger, 'ab') as fd:
            fd.write(b'\000')

    def do_delete():
        display_debug('triggering delete')
        os.unlink(trigger)

    def do_exit():
        f.monitor.handle_input('exit')

    def do_fail():
        failed = True
        do_exit()

    actions = {
        None: [do_modify],
        'modified': [do_delete, do_exit],
        # Sometimes deleting a file triggers a modifed event first
        # and the deleted event is suppressed.
        'deleted': [do_exit]
    }

    def trigger_events(task: ScriptTask, ev: Optional[FileSystemEvent]):

        ev = ev.event_type if ev else None
        callbacks = actions.get(ev)
        if not callbacks:
            do_fail()
            return

        f.monitor.loop.call_soon(callbacks.pop(0))

    # Monkey-patched so it doesn't run
    f.run_forever()

    assert f.tasks, 'no tasks'

    # Start the event-triggers after the script runs once
    f.tasks[0].add_after_callback(trigger_events)
    # Manually start the monitor
    await f.monitor.start_interactive()

    # assert output.stderr_expect('task default ready.*')
    # assert output.stderr_expect('task other1.*skipped.*scripts.*empty')
    # assert output.stderr_expect('task other2.*skipped')

    assert not failed
    output.dump()
