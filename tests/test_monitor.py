from foremon.display import display_debug
from foremon.config import PyProjectConfig
from foremon.monitor import Monitor
from foremon.task import ScriptTask
from pytest_mock.plugin import MockerFixture

from .cli_fixtures import *
from .fixtures import *


def monitor_from_toml(toml: str) -> Monitor:
    conf = PyProjectConfig.parse_toml(toml).tool.foremon
    task = ScriptTask(conf)
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

    monitor.loop.call_later(0.2, do_exit)
    await monitor.start_interactive()
    assert output.stderr_expect('starting.*')
    assert output.stdout_expect('please exit')
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
        monitor.loop.call_later(0.2, do_exit)

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
        monitor.loop.call_later(0.2, do_exit)

    monitor.loop.call_later(0.2, do_restart)

    await monitor.start_interactive()
    assert output.stderr_expect('starting.*')
    assert output.stderr_expect('terminated.*')
    assert output.stderr_expect('starting.*')


@pytest.fixture
def amonitor():
    return monitor_from_toml(f"""
    [tool.foremon]
    scripts = ["echo test"]
    """)

async def test_monitor_start_no_tasks(amonitor: Monitor, mocker: MockerFixture):
    amonitor.all_tasks.clear()
    ret = await amonitor.start_interactive()
    assert ret == False

async def test_monitor_start_observer_running(amonitor: Monitor, mocker: MockerFixture):
    mocker.patch.object(amonitor.observer,'is_alive', lambda *_: True)
    ret = await amonitor.start_interactive()
    assert ret == False

async def test_monitor_start_terminating(amonitor: Monitor, mocker: MockerFixture):
    mocker.patch.object(amonitor,'is_terminating', True)
    ret = await amonitor.start_interactive()
    assert ret == False

async def test_monitor_task_throws(output: CapLines, amonitor: Monitor, mocker: MockerFixture):

    async def crasher():
        raise Exception('test error')

    amonitor.queue.put_nowait(crasher())
    await amonitor.start_interactive()
    display_debug('monitor returns ...')
    assert output.stderr_expect('fatal error.*')


@pytest.mark.parametrize('exc_class, text', [
    (KeyboardInterrupt, 'stopping.*'),
    (EOFError, 'stopping.*'),
    (Exception, 'fatal error.*'),
])
async def test_monitor_signaled(output: CapLines, amonitor: Monitor, mocker: MockerFixture, exc_class, text: str):

    def raiser(*args):
        raise exc_class('test')

    mocker.patch('foremon.queue.queueiter.__init__', raiser)
    await amonitor.start_interactive()
    assert output.stderr_expect(text)
