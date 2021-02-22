import asyncio
from foremon.task import ForemonTask
from typing import Callable

from foremon.debounce import Debounce, EventContainer
from pytest_mock.plugin import MockerFixture
from itertools import count
from .fixtures import *


@pytest.fixture
def MockTask(mocker: MockerFixture):
    incr = count(start=0)
    def MockFactory(name: str, order = None):
        inc = next(incr)
        if order is None:
            order = inc

        c = mocker.MagicMock()
        mocker.patch.object(c, 'order', order)

        o = mocker.MagicMock()
        mocker.patch.object(o, 'name', name)
        mocker.patch.object(o, 'config', c)

        return o

    return MockFactory

async def test_debounce_dwell_submit(MockTask:Callable[[str], ForemonTask]):
    result = []
    dwell = 0.1
    d = Debounce(dwell, lambda *args: result.append(args[1]))
    d.submit(MockTask('x'), 'x')
    d.submit(MockTask('y'), 'y')
    assert not result
    await asyncio.sleep(dwell)
    assert 'x' in result
    assert 'y' in result


async def test_debounce_no_dwell_submit(MockTask):
    result = []
    dwell = -0.1
    d = Debounce(dwell, lambda *args: result.append(args[1]))
    d.submit(MockTask('x'), 'x')
    d.submit(MockTask('y'), 'y')
    assert 'x' in result
    assert 'y' in result


async def test_debounce_no_dwell_submit_threadsafe(MockTask):
    result = []
    dwell = -0.1
    d = Debounce(dwell, lambda *args: result.append(args[1]))
    d.submit_threadsafe(MockTask('x'), 'x')
    d.submit_threadsafe(MockTask('y'), 'y')
    assert 'x' not in result
    assert 'y' not in result
    await asyncio.sleep(0.1)
    assert 'x' in result
    assert 'y' in result


async def test_debounce_submit_throws(output: CapLines, MockTask):
    def thrower(*args):
        raise Exception('test')
    d = Debounce(0.1, thrower)
    d.submit(MockTask('a'), 'a')
    await asyncio.sleep(0.1)
    assert output.stderr_expect('drain callback error.*')


async def test_debounce_no_dwell_submit_throws(output: CapLines, MockTask):
    def thrower(*args):
        raise Exception('test')
    d = Debounce(0.0, thrower)
    with pytest.raises(Exception):
        d.submit(MockTask('a'), 'a')


async def test_debounce_dwell_high_volume_submit(output: CapLines, MockTask):
    result = []
    dwell = 0.1
    d = Debounce(dwell, lambda *args: result.append(args[1]))
    for i in range(0, 400):
        d.submit(MockTask('x'), 'x')
        d.submit(MockTask('y'), 'y')
    assert not result
    await asyncio.sleep(dwell)
    assert 'x' in result
    assert 'y' in result

    assert output.stderr_expect('detected high event volume.*')
