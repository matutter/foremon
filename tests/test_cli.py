import errno
from foremon.display import set_display_verbose
import os.path as op
import sys
from unittest.mock import MagicMock
from foremon import monitor
from foremon.task import ForemonTask
from foremon.config import PyProjectConfig
from foremon.monitor import Monitor
from pytest_mock.plugin import MockerFixture

from .cli_fixtures import *
from .fixtures import *


def test_help(cli: CliProg, output: CapLines):
    assert cli('--help').exit_code == 0
    assert output.stdout_expect('Usage: foremon.*')


def test_version(cli, output: CapLines):
    from foremon import __version__
    result: Result = cli('--version')
    assert result.exit_code == 0
    assert output.stdout_expect(__version__)


def test_paths_do_not_exist(cli, output: CapLines):
    from foremon import __version__
    result: Result = cli('-w this/does/not/exist -- true')
    assert result.exit_code == errno.ENOENT


def test_cli_dry_run(cli, output: CapLines):
    result: Result = cli('-V --dry-run -- true')
    assert output.stderr_expect('dry run complete')


def test_cli_config_file(cli, output: CapLines, tempfiles: Tempfiles):
    conf = tempfiles.make_file("config")

    with open(conf, 'w') as fd:
        fd.write("""
        [tool.foremon]
        scripts = ["echo ok"]

            [tool.foremon.test1]
            scripts = ["echo ok"]

            [tool.foremon.test2]
            scripts = ["echo ok"]
        """)

    result: Result = cli('-V --dry-run --all -f', conf)
    assert output.stderr_expect(f'loaded.*config from {conf}')
    assert output.stderr_expect('task default ready.*')
    assert output.stderr_expect('task test1 ready.*')
    assert output.stderr_expect('task test2 ready.*')


def test_cli_chdir(mocker, cli):
    mock: MagicMock = mocker.MagicMock(name='start_monitor')
    mocker.patch('foremon.cli.Util.start_monitor', new=mock)

    result: Result = cli('-V --dry-run --chdir /tmp -- true')

    m: Monitor = mock.call_args[0][0]
    t: ForemonTask = m.all_tasks.pop()
    assert t
    assert t.config.cwd == '/tmp'


def test_cli_unsafe(mocker, cli):
    mock: MagicMock = mocker.MagicMock(name='start_monitor')
    mocker.patch('foremon.cli.Util.start_monitor', new=mock)

    result: Result = cli('-V --dry-run --unsafe -- true')

    m: Monitor = mock.call_args[0][0]
    t: ForemonTask = m.all_tasks.pop()
    assert t
    assert t.config.ignore_defaults == []


def test_cli_ignore(mocker, cli):
    mock: MagicMock = mocker.MagicMock(name='start_monitor')
    mocker.patch('foremon.cli.Util.start_monitor', new=mock)

    result: Result = cli('-V --dry-run -i "*.test1" -i "*.test2" -- true')

    m: Monitor = mock.call_args[0][0]
    t: ForemonTask = m.all_tasks.pop()
    assert t
    assert "*.test1" in t.config.ignore
    assert "*.test2" in t.config.ignore


def test_cli_scripts(mocker, cli):
    mock: MagicMock = mocker.MagicMock(name='start_monitor')
    mocker.patch('foremon.cli.Util.start_monitor', new=mock)

    result: Result = cli('-V --dry-run -x "echo 1" -x "echo 2" -- echo 3')

    m: Monitor = mock.call_args[0][0]
    t: ForemonTask = m.all_tasks.pop()
    assert t
    assert "echo 1" in t.config.scripts
    assert "echo 2" in t.config.scripts
    assert "echo 3" in t.config.scripts

def test_cli_guess_script(mocker, cli):
    mock: MagicMock = mocker.MagicMock(name='start_monitor')
    mocker.patch('foremon.cli.Util.start_monitor', new=mock)

    script = get_sample_file('script1.py')
    result: Result = cli(script)

    m: Monitor = mock.call_args[0][0]
    t: ForemonTask = m.all_tasks.pop()
    assert t
    guess = t.config.scripts[0]
    assert op.basename(sys.executable) in guess

def test_cli_guess_module(mocker, cli):
    mock: MagicMock = mocker.MagicMock(name='start_monitor')
    mocker.patch('foremon.cli.Util.start_monitor', new=mock)

    script = get_sample_file('module1')
    result: Result = cli(script)

    m: Monitor = mock.call_args[0][0]
    t: ForemonTask = m.all_tasks.pop()
    assert t
    guess = t.config.scripts[0]
    assert op.basename(sys.executable) + ' -m' in guess

def monitor_from_toml(toml: str) -> Monitor:
    conf = PyProjectConfig.parse_toml(toml).tool.foremon
    task = ForemonTask(conf)
    monitor = Monitor(pipe=None)
    monitor.add_task(task)
    return monitor


async def test_interactive_exit(output: CapLines, tempfiles: Tempfiles):

    trigger = tempfiles.make_file('trigger')

    monitor = monitor_from_toml(f"""
        [tool.foremon]
        paths = ["{trigger}"]
        scripts = ["echo please exit"]
        """)

    def do_exit():
        monitor.handle_input('exit')

    monitor.loop.call_later(1.0, do_exit)
    await monitor.start_interactive()
    assert output.stderr_expect('starting.*')
    assert output.stderr_expect('clean exit.*')
    assert output.stderr_expect('stopping.*')

async def test_interactive_restart(output: CapLines, tempfiles: Tempfiles):

    trigger = tempfiles.make_file('trigger')

    monitor = monitor_from_toml(f"""
        [tool.foremon]
        paths = ["{trigger}"]
        scripts = ["echo ok"]
        """)

    def do_exit():
        monitor.handle_input('exit')

    def do_restart():
        monitor.handle_input('rs')
        monitor.loop.call_later(1.0, do_exit)

    monitor.loop.call_soon(do_restart)

    await monitor.start_interactive()
    assert output.stdout_expect('ok')
    assert output.stdout_expect('ok')

async def test_interactive_restart_long_running(output: CapLines, tempfiles: Tempfiles):

    trigger = tempfiles.make_file('trigger')

    monitor = monitor_from_toml(f"""
        [tool.foremon]
        paths = ["{trigger}"]
        scripts = ["echo ok", "sleep 5", "echo done"]
        """)

    def do_exit():
        monitor.handle_input('exit')

    def do_restart():
        monitor.handle_input('rs')
        monitor.loop.call_later(1.0, do_exit)

    monitor.loop.call_later(1.0, do_restart)

    await monitor.start_interactive()
    assert output.stderr_expect('starting.*')
    assert output.stderr_expect('terminated.*')
    assert output.stderr_expect('starting.*')

def test_cli_skip_tasks(output: CapLines):
    from foremon.cli import Util

    conf = PyProjectConfig.parse_toml("""
    [tool.foremon]
    scripts = ["true"]

        [tool.foremon.other1]

        [tool.foremon.other2]
        scripts = ["true"]
        skip = true
    """).tool.foremon

    m: Monitor = Monitor()

    tasks = Util.get_active_tasks(conf, [], use_all=True)
    Util.add_tasks(m, tasks)
    assert len(m.all_tasks) == 1

    assert output.stderr_expect('task other1.*skipped.*scripts.*empty')
    assert output.stderr_expect('task other2.*skipped')
    assert output.stderr_expect('task default ready.*')


def test_cli_skip_tasks2(cli, output: CapLines, tempfiles: Tempfiles):
    conf = tempfiles.make_file("config")

    with open(conf, 'w') as fd:
        fd.write("""
        [tool.foremon]
        scripts = ["true"]

            [tool.foremon.other1]

            [tool.foremon.other2]
            scripts = ["true"]
            skip = true
        """)

    result: Result = cli('-V --dry-run -f', conf)
    assert output.stderr_expect('task other1.*skipped.*scripts.*empty')
    assert output.stderr_expect('task other2.*skipped')
    assert output.stderr_expect('task default ready.*')
