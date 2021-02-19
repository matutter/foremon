import errno
from foremon.display import get_display_name
import os.path as op
import sys
from unittest.mock import MagicMock
import asyncio

from foremon.app import Foremon
from pytest_mock.plugin import MockerFixture

from .cli_fixtures import *
from .fixtures import *


@pytest.fixture
def noninteractive(mocker: MockerFixture) -> MagicMock:
    loop = asyncio.get_event_loop()
    # The Click.testing.CliRunner replaces `sys.stdin` with something that is
    # notcompatible with `add_reader` so we just mock the call.
    mocker.patch.object(loop, 'add_reader', lambda *_: None)
    mocker.patch.object(loop, 'remove_reader', lambda *_: None)
    mock: MagicMock = mocker.MagicMock(name='Foremon._run')
    mocker.patch('foremon.app.Foremon._run', new=mock)
    spy = mocker.spy(Foremon, 'run_forever')
    return spy


def test_help(cli: CliProg, output: CapLines):
    assert cli('--help').exit_code == 0
    assert output.stdout_expect('Usage: foremon.*')


def test_version(cli, output: CapLines):
    from foremon import __version__
    result: Result = cli('--version')
    assert result.exit_code == 0
    assert output.stdout_expect(__version__)


def test_paths_do_not_exist(noninteractive, cli, output: CapLines):
    result: Result = cli('-w this/does/not/exist -- true')
    assert result.exit_code == errno.ENOENT


def test_cli_dry_run(noninteractive, cli, output: CapLines):
    result: Result = cli('--dry-run -- true')
    assert output.stderr_expect('dry run complete')
    assert result.exit_code == 0


def test_cli_config_file(noninteractive, cli, output: CapLines, tempfiles: Tempfiles):

    conf = tempfiles.make_file("config", content="""
        [tool.foremon]
        scripts = ["echo ok"]

            [tool.foremon.test1]
            scripts = ["echo ok"]

            [tool.foremon.test2]
            scripts = ["echo ok"]
        """)

    cli('-V --dry-run --all -f', conf)

    assert output.stderr_expect(f'loaded.*config from {conf}')
    assert output.stderr_expect('task default ready.*')
    assert output.stderr_expect('task test1 ready.*')
    assert output.stderr_expect('task test2 ready.*')


def test_cli_chdir(noninteractive: MagicMock, cli):

    cli('-V --dry-run --chdir /tmp -- true')

    f: Foremon = noninteractive.call_args[0][0]
    assert f
    assert isinstance(f, Foremon)
    assert f.options.cwd == '/tmp'
    assert f.config.cwd == '/tmp'


def test_cli_unsafe(noninteractive: MagicMock, cli):

    cli('-V --dry-run --unsafe -- true')

    f: Foremon = noninteractive.call_args[0][0]
    assert f
    assert isinstance(f, Foremon)
    t = f.get_task('default')
    assert t.config.ignore_defaults == []
    assert f.config == t.config


def test_cli_ignore(noninteractive: MagicMock, cli):

    cli('-V --dry-run -i "*.test1" -i "*.test2" -- true')

    f: Foremon = noninteractive.call_args[0][0]
    assert f
    assert isinstance(f, Foremon)
    assert f.tasks
    t: Foremon = f.get_task('default')
    assert t
    assert "*.test1" in t.config.ignore
    assert "*.test2" in t.config.ignore


def test_cli_scripts(noninteractive: MagicMock, cli):

    cli('-V --dry-run -x "echo 1" -x "echo 2" -- echo 3')

    f: Foremon = noninteractive.call_args[0][0]
    assert f
    assert isinstance(f, Foremon)
    assert f.tasks
    assert f.get_task('default').config == f.config
    assert "echo 1" in f.config.scripts
    assert "echo 2" in f.config.scripts
    assert "echo 3" in f.config.scripts


def test_cli_guess_script(noninteractive: MagicMock, cli):

    cli(get_sample_file('script1.py'))

    f: Foremon = noninteractive.call_args[0][0]
    assert f
    guess = f.config.scripts[0]
    assert op.basename(sys.executable) in guess


def test_cli_guess_module(noninteractive: MagicMock, cli):

    cli(get_sample_file('module1'))

    f: Foremon = noninteractive.call_args[0][0]
    assert f
    guess = f.config.scripts[0]
    assert op.basename(sys.executable) + ' -m' in guess

def test_cli_guess_modules_in_env(noninteractive: MagicMock, cli):

    cli('pytest --markers')

    f: Foremon = noninteractive.call_args[0][0]
    assert f
    guess = f.config.scripts[0]
    assert op.basename(sys.executable) + ' -m' in guess

def test_cli_config_bad_path(noninteractive, cli, output: CapLines, tempfiles: Tempfiles):

    config = tempfiles.make_file("config.toml")

    cli('-V --dry-run -f', config + "_oops")

    assert output.stderr_expect('cannot find config file.*')
    assert output.stderr_expect('no scripts.*nothing to do.*')


def test_cli_skip_tasks(noninteractive, cli, output: CapLines, tempfiles: Tempfiles):
    config = tempfiles.make_file("config.toml", content="""
    [tool.foremon]
    scripts = ["true"]

        [tool.foremon.other1]

        [tool.foremon.other2]
        scripts = ["true"]
        skip = true
    """)

    cli('-V --dry-run -f', config)
    assert output.stderr_expect('task default ready.*')
    assert output.stderr_expect('task other1.*skipped.*scripts.*empty')
    assert output.stderr_expect('task other2.*skipped')


def test_cli_empty_config(noninteractive, cli, output: CapLines, tempfiles: Tempfiles):
    config = tempfiles.make_file("config.toml", content="""
    # For building this project
    [build-system]
    requires = [ "setuptools>=42", "wheel" ]
    build-backend = "setuptools.build_meta"
    """)

    cli('-V --dry-run -f', config)
    assert output.stderr_expect(r'no .tool.foremon. section specified in.*')
    assert output.stderr_expect('no scripts.* nothing to do.*')


def test_cli_invoke_as_module(mocker: MagicMock):
    mocked_main: MagicMock = mocker.MagicMock(name='main')
    mocker.patch('foremon.cli.foremon.main', mocked_main)

    name: MagicMock = mocker.MagicMock(name='set_display_name')
    mocker.patch('foremon.display.set_display_name', name, lambda _: None)

    old_name =  get_display_name()
    from foremon.cli import main
    main()

    # Should be mocked and not changed
    assert old_name == get_display_name()
    assert mocked_main.call_count == 1
    assert name.call_args[0][0] == 'foremon'
