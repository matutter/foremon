import asyncio
import os
import signal

from foremon.config import *
from foremon.display import display_info
from foremon.task import ForemonTask
from pydantic.error_wrappers import ValidationError

from .fixtures import pytestmark
from .fixtures2 import *


async def test_task_run_one_script(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tools.foremon]
    patterns = ["*"]
    scripts = ["echo Hello World!"]
    """).tools.foremon

    task = ForemonTask(conf)
    await task.run()
    assert output.stderr_expect('starting.*')
    assert output.stdout_expect('Hello World!')
    assert output.stderr_expect('clean exit.*')


async def test_task_run_multiple_sripts(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
  [tools.foremon]
  patterns = ["*"]
  scripts = ["echo Hello", "echo World!"]
  """).tools.foremon

    task = ForemonTask(conf)
    await task.run()
    assert output.stderr_expect('starting.*')
    assert output.stdout_expect('Hello')
    assert output.stdout_expect('World!')
    assert output.stderr_expect('clean exit.*')


async def test_task_unexpected_returncode(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tools.foremon]
    patterns = ["*"]
    returncode = 1
    scripts = ["true"]
    """).tools.foremon

    task = ForemonTask(conf)
    await task.run()
    assert output.stderr_expect('starting.*')
    assert output.stderr_expect('app crashed.*')


async def test_task_expected_non_standard_returncode(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tools.foremon]
    patterns = ["*"]
    returncode = 1
    scripts = ["false"]
    """).tools.foremon

    await ForemonTask(conf).run()
    assert output.stderr_expect('starting.*')
    assert output.stderr_expect('clean exit.*')


async def test_task_is_killed(output: CapLines):
    conf = PyProjectConfig.parse_toml(f"""
    [tools.foremon]
    patterns = ["*"]
    returncode = 0
    scripts = ["sleep 10"]
    """).tools.foremon

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
    [tools.foremon]
    patterns = ["*"]
    returncode = 0
    term_signal = "SIGTERM"
    scripts = ["sleep 10"]
    """).tools.foremon

    task = ForemonTask(conf)

    def do_later():
        if task.running:
            task.terminate()
        else:
            task.loop.call_later(0.1, do_later)

    do_later()
    await task.run()
    assert output.stderr_expect('cancelled')
