import os
import os.path as op
from typing import Optional
from unittest.mock import MagicMock

from foremon.app import AUTO_RELOAD_ALIAS, Foremon, ReloadTask
from foremon.config import Events, ForemonOptions
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


@pytest.mark.parametrize('src_path, event_type', [
    ('ev1', Events.modified),
    ('ev2', Events.deleted),
    ('ev3', Events.moved),
    ('ev4', Events.created),
])
async def test_app_log_event_type(output: CapLines, src_path, event_type):
    foremon = Foremon(ForemonOptions(scripts=['true'], verbose=True))
    task = foremon.get_task('default')
    ev = FileSystemEvent(src_path)
    ev.event_type = event_type

    # Should log one time
    foremon._before_task_runs(task, ev)

    # Nothing logs when there is no FS event
    foremon._before_task_runs(task, None)

    # Nothing logs when verbose is off
    foremon.options.verbose = False
    foremon._before_task_runs(task, ev)

    assert output.stderr_expect(f'triggered because {src_path} was {event_type}')
    assert not output.stderr_lines


async def test_app_auto_reload_config(norun, mocker:MockerFixture, output: CapLines, tempfiles: Tempfiles):

    config_file = tempfiles.make_file("config.toml", content="""
    [tool.foremon]
    scripts = ["true"]
    """)

    options = ForemonOptions(config_file=config_file)
    foremon = Foremon(options)

    # Mocked to not start - just setup program state
    foremon.run_forever()

    task = foremon.get_task(AUTO_RELOAD_ALIAS)
    assert isinstance(task, ReloadTask)
    default = foremon.get_task('default')
    assert isinstance(default, ScriptTask)
    assert default.config.scripts[0] == 'true'

    config_file = tempfiles.make_file("config.toml", content="""
    [tool.foremon]
    scripts = ["false"]
    """)

    event = FileSystemEvent(config_file)
    event.event_type = Events.modified

    await task.run(event)
    # A new instance is created on reload
    task2 = foremon.get_task(AUTO_RELOAD_ALIAS)
    assert task != task2

    # Checks that the reload took effect
    default = foremon.get_task('default')
    assert isinstance(default, ScriptTask)
    assert default.config.scripts[0] == 'false'

    # Nothing happens on non-filesystem events
    await task.run(None)
    task3 = foremon.get_task(AUTO_RELOAD_ALIAS)
    assert task2 == task3

    assert output.stderr_expect('config.*was modified.*')
    assert output.stderr_expect('loaded.*from.*')

