import asyncio
from foremon.errors import ForemonError
from foremon.queue import queueiter
import os
import signal

from foremon.config import *
from foremon.display import display_info
from foremon.task import ForemonTask
from pydantic.error_wrappers import ValidationError

from .fixtures import *


async def test_task_run_one_script(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tool.foremon]
    patterns = ["*"]
    scripts = ["echo Hello World!"]
    """).tool.foremon

    task = ForemonTask(conf)
    await task.run()
    assert output.stderr_expect('starting.*')
    assert output.stdout_expect('Hello World!')
    assert output.stderr_expect('clean exit.*')


async def test_task_run_multiple_sripts(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
  [tool.foremon]
  patterns = ["*"]
  scripts = ["echo Hello", "echo World!"]
  """).tool.foremon

    task = ForemonTask(conf)
    await task.run()
    assert output.stderr_expect('starting.*')
    assert output.stdout_expect('Hello')
    assert output.stdout_expect('World!')
    assert output.stderr_expect('clean exit.*')


async def test_task_unexpected_returncode(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tool.foremon]
    patterns = ["*"]
    returncode = 1
    scripts = ["true"]
    """).tool.foremon

    task = ForemonTask(conf)
    await task.run()
    assert output.stderr_expect('starting.*')
    assert output.stderr_expect('app crashed.*')


async def test_task_expected_non_standard_returncode(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tool.foremon]
    patterns = ["*"]
    returncode = 1
    scripts = ["false"]
    """).tool.foremon

    await ForemonTask(conf).run()
    assert output.stderr_expect('starting.*')
    assert output.stderr_expect('clean exit.*')


async def test_task_is_killed(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tool.foremon]
    patterns = ["*"]
    returncode = 0
    scripts = ["sleep 10"]
    """).tool.foremon

    task = ForemonTask(conf)

    def do_later():
        if task.running:
            display_info("about to send kill")
            os.kill(task.process.pid, signal.SIGKILL)
        else:
            task.loop.call_later(0.1, do_later)

    do_later()
    await task.run()
    display_info("about to send kill")
    assert output.stderr_expect('app crashed -9.*')


async def test_task_terminate(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tool.foremon]
    patterns = ["*"]
    returncode = 0
    term_signal = "SIGTERM"
    scripts = ["sleep 10"]
    """).tool.foremon

    task = ForemonTask(conf)

    def do_later():
        if task.running:
            task.terminate()
        else:
            task.loop.call_later(0.1, do_later)

    do_later()
    await task.run()
    assert output.stderr_expect('terminated.*')

async def test_task_before_after_callbacks(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tool.foremon]
    scripts = ["true"]
    """).tool.foremon

    async def async_before(task, trigger):
        print("BEFORE ASYNC")

    def before(task, trigger):
        print("BEFORE NORMAL")

    async def async_after(task, trigger):
        print("AFTER ASYNC")

    def after(task, trigger):
        print("AFTER NORMAL")

    await (ForemonTask(conf)
        .add_before_callback(async_before)
        .add_before_callback(before)
        .add_after_callback(async_after)
        .add_after_callback(after)
        .run())

    assert output.stdout_expect('BEFORE ASYNC')
    assert output.stdout_expect('BEFORE NORMAL')
    assert output.stdout_expect('AFTER ASYNC')
    assert output.stdout_expect('AFTER NORMAL')

async def test_task_run_from_queue(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tool.foremon]
    scripts = ["echo ok"]
    """).tool.foremon

    task = ForemonTask(conf)
    queue = asyncio.Queue()

    queue.put_nowait(task.run())
    queue.put_nowait(task.run())
    queue.put_nowait(None)

    # Serial exec
    while True:
        task = await queue.get()
        if task == None: break
        await task

    assert output.stderr_expect('starting.*')
    assert output.stdout_expect('ok')
    assert output.stderr_expect('starting.*')
    assert output.stdout_expect('ok')

async def test_task_run_from_queueiter(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tool.foremon]
    scripts = ["echo START 1", "sleep 0.2", "echo END 1"]

        [tool.foremon.test]
        scripts = ["echo START 2", "sleep 0.2", "echo END 2"]
    """).tool.foremon

    queue = asyncio.Queue()

    queue.put_nowait(ForemonTask(conf).run())
    queue.put_nowait(ForemonTask(conf.configs[0]).run())
    queue.put_nowait(None)

    async for coro in queueiter(queue):
        await coro

    assert output.stdout_expect('START 1')
    assert output.stdout_expect('END 1')
    assert output.stdout_expect('START 2')
    assert output.stdout_expect('END 2')

def test_task_add_monitor_duplicate():

    conf = PyProjectConfig.parse_toml(f"""
    [tool.foremon]
    scripts = ["echo START 1", "sleep 0.2", "echo END 1"]

        [tool.foremon.test]
        scripts = ["echo START 2", "sleep 0.2", "echo END 2"]
    """).tool.foremon


    from foremon.monitor import Monitor

    task = ForemonTask(conf)
    mon = Monitor()

    mon.add_task(task)

    with pytest.raises(ForemonError):
        mon.add_task(task)


async def test_task_passes_environment(output: CapLines):

    conf = PyProjectConfig.parse_toml("""
    [tool.foremon]
    scripts = ["echo DATA=$MYVAR"]
    [tool.foremon.environment]
    MYVAR = "test123"
    """).tool.foremon

    await ForemonTask(conf).run()

    output.stdout_expect("DATA=test123")