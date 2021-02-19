import os
import os.path as op
from typing import Optional
from unittest.mock import MagicMock

from foremon.app import AUTO_RELOAD_ALIAS, Foremon, ReloadTask
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
    f.get_task('default').add_after_callback(trigger_events)
    # Manually start the monitor
    await f.monitor.start_interactive()

    assert not failed
    assert output.stderr_expect('.*trigger was modified')
    assert output.stderr_expect('.*trigger was (deleted|modified)')
    assert output.stderr_expect('stopping.*')


async def test_app_auto_reload_config(norun, mocker:MockerFixture, output: CapLines, tempfiles: Tempfiles):
    """
    This test will with check config auto-reloading. Auto-reload destroyed
    (discards) ForemonTask objects so we can't reuse callbacks set on them to
    help instrument this test. Instead we're relying on `asyncio.call_later`.
    """

    # debug output is hard to parse through for this many events
    mocker.patch('foremon.display.display_verbose', lambda: False)

    failed = False
    trigger = tempfiles.make_file('ignored')

    config1 = f"""
    [tool.foremon]
    paths = ["{op.dirname(trigger)}"]
    patterns = ["{op.basename(trigger)}"]
    scripts = ["echo test123"]
    """

    config2 = f"""
    [tool.foremon]
    paths = ["{op.dirname(trigger)}"]
    patterns = ["{op.basename(trigger)}"]
    scripts = ["echo test456"]
    """

    config = tempfiles.make_file("config.toml", content=config1)
    options = ForemonOptions(config_file=config, verbose=True, scripts=['true'])
    f = Foremon(options)

    def do_modify():
        display_debug("Updating config file")
        with open(config, 'w') as fd:
            fd.write(config2)

    def do_delete():
        os.unlink(config)

    def do_exit():
        display_info("sending 'exit'")
        f.monitor.handle_input('exit')

    def do_fail():
        failed = True
        do_exit()

    actions = {
        None: [
            # After initial start, 'true' and 'echo test123' run
            do_modify,
            # After modify 'true' and 'echo test456' run
            do_delete,
            # After delete 'true' runs
            do_exit],
    }

    def trigger_events(task: ScriptTask, ev: Optional[FileSystemEvent]):
        ev = ev.event_type if ev else None
        callbacks = actions.get(ev)
        display_info(f"+++++ got hook `{ev}`, callback {callbacks[0] if callbacks else None}")
        if not callbacks:
            display_error(f"+++++ got hook `{ev}`, but missing callback")
            do_fail()
            return
        # Trigger an event 1s after reload
        # f.monitor.loop.call_later(0.2, callbacks.pop(0))
        f.monitor.loop.call_soon_threadsafe(callbacks.pop(0))


    # reload tasks are always added after all other tasks are constructed. We
    # can inject our trigger handler by patching the `new_reload_task` method
    def my_new_reload_task(config_file: str) -> ReloadTask:
        display_info(f"+++++ new reload task created")
        task = ReloadTask(f, config_file)
        default = f.get_task('default')
        if default:
            default.add_after_callback(trigger_events)
        else:
            display_warning('+++++ no default task - cannot set event hook')
        return task

    mocker.patch.object(f, '_new_reload_task', my_new_reload_task)

    f.monitor.loop.call_later(10.0, do_fail)

    # Monkey-patched so it doesn't run
    f.run_forever()

    assert f.tasks, 'no tasks'

    # Start the event-triggers after the script runs once
    # Manually start the monitor
    await f.monitor.start_interactive()
    #assert not failed
    # initial run with config1
    assert output.stderr_expect('starting.*')
    assert output.stdout_expect('test123')
    assert output.stderr_expect('clean exit.*')

    # config file is update to config2
    assert output.stderr_expect('config.*was modified, reloading.*')
    assert output.stderr_expect('starting.*')
    assert output.stdout_expect('test456')
    assert output.stderr_expect('clean exit.*')
