import asyncio

from foremon.debounce import Debounce, EventContainer

from .fixtures import *


async def test_debounce_dwell_submit():
    result = []
    dwell = 0.1
    d = Debounce(dwell, result.append)
    d.submit('x', 'x')
    d.submit('y', 'y')
    assert not result
    await asyncio.sleep(dwell)
    assert 'x' in result
    assert 'y' in result


async def test_debounce_no_dwell_submit():
    result = []
    dwell = -0.1
    d = Debounce(dwell, result.append)
    d.submit('x', 'x')
    d.submit('y', 'y')
    assert 'x' in result
    assert 'y' in result


async def test_debounce_no_dwell_submit_threadsafe():
    result = []
    dwell = -0.1
    d = Debounce(dwell, result.append)
    d.submit_threadsafe('x', 'x')
    d.submit_threadsafe('y', 'y')
    assert 'x' not in result
    assert 'y' not in result
    await asyncio.sleep(0.1)
    assert 'x' in result
    assert 'y' in result

async def test_debounce_submit_throws(output: CapLines):
    def thrower(*args):
        raise Exception('test')
    d = Debounce(0.1, thrower)
    d.submit('a', 'a')
    await asyncio.sleep(0.1)
    assert output.stderr_expect('drain callback error.*')


async def test_debounce_no_dwell_submit_throws(output: CapLines):
    def thrower(*args):
        raise Exception('test')
    d = Debounce(0.0, thrower)
    with pytest.raises(Exception):
        d.submit('a', 'a')


async def test_debounce_dwell_submit(output: CapLines):
    result = []
    dwell = 0.1
    d = Debounce(dwell, result.append)
    for i in range(0, 400):
        d.submit('x', 'x')
        d.submit('y', 'y')
    assert not result
    await asyncio.sleep(dwell)
    assert 'x' in result
    assert 'y' in result

    assert output.stderr_expect('detected high event volume.*')
