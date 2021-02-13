import asyncio
import json
import os
import os.path as op
import shutil
import signal
import sys
from water.display import display_debug

from .fixtures import *

CLEAN_EXIT = r'clean exit.*'
ANY_EXIT   = r'(app crashed|clean exit).*'

async def test_help(bootstrap: WaterBootstrap):
    p = await bootstrap.spawn('--help')
    await p.stop()
    assert '--help' in p.stdout
    assert p.returncode == 0


async def test_version(bootstrap: WaterBootstrap):
    p = await bootstrap.spawn('--version')
    await p.stop()
    from water import __version__
    assert p.stdout.strip() == __version__


async def test_watch_one_file(bootstrap: WaterBootstrap, tempfiles: Tempfiles):

    f1, = tempfiles.make_files([
        'test/a.txt',
    ])

    p = await bootstrap.spawn('-n -w', f1, '-e "*"', '-V', '-- test -f', f1)
    assert await p.expect(r'starting.*')
    assert await p.expect(r'clean exit.*')
    with open(f1, 'w') as fd:
        fd.write('modify')
    assert await p.expect(r'trigger.*modified')
    assert await p.expect(r'clean exit.*')
    await p.stop()


async def test_watch_one_dir(bootstrap: WaterBootstrap, tempfiles: Tempfiles):

    f1, f2, f3 = tempfiles.make_files([
        'test/a.txt',
        'test/b.txt',
        'test/c.txt'
    ])

    p = await bootstrap.spawn('-n -w', tempfiles.root, '-e "*"', '-V', '-- test -f', f3)
    assert await p.expect(r'starting.*')
    assert await p.expect(r'clean exit.*')

    display_debug('modifying a file')
    with open(f1, 'w') as fd:
        fd.write('modify')

    assert await p.expect(r'trigger.*modified')
    assert await p.expect(r'clean exit.*')

    display_debug('deleting a file')
    os.unlink(f3)
    assert await p.expect(r'trigger.*deleted')
    assert await p.expect(r'app crashed.*')

    display_debug('moving a file')
    shutil.move(f1, f2)
    assert await p.expect(r'trigger.*moved')
    assert await p.expect(r'(app crashed|clean exit).*')

    await p.stop()


async def test_chdir_guess_insert_interpreter(bootstrap: WaterBootstrap, sampledir: str):
    """
    Test guessing when to insert the python interpreter in the path when the
    `--chdir` option is used.
    """

    p = await bootstrap.spawn('-V', '-C', sampledir, 'script1.py')
    await p.stop()

    d = json.loads(p.stdout)

    assert d['executable'] == sys.executable
    assert d['argv'] == ['script1.py']


async def test_guess_insert_interpreter(bootstrap: WaterBootstrap, sampledir: str):
    """
    Test guessing when to insert the python interpreter in the path.
    """

    script = op.join(sampledir, 'script1.py')
    p = await bootstrap.spawn('-V', script)
    await p.stop()

    d = json.loads(p.stdout)

    assert d['executable'] == sys.executable
    assert d['argv'] == [script]


async def test_guess_script_is_executable(bootstrap: WaterBootstrap, sampledir: str):
    """
    Check that the interpreter is not inserted if the python script is
    executable.
    """

    script = op.join(sampledir, 'script2.py')

    p = await bootstrap.spawn(script)
    await p.stop()

    d = json.loads(p.stdout)
    assert d['executable'] == ""
    assert d['argv'] == [script]


async def test_guess_insert_module(bootstrap: WaterBootstrap, sampledir: str):
    """
    Check that `python -m` is inserted into the command when a python module is detected.
    """

    p = await bootstrap.spawn('-V', '-C', sampledir, 'module1')

    python = op.basename(sys.executable)
    assert await p.expect(f'starting.*{python} -m module1')
    assert await p.expect(r'clean exit.*')
    await p.stop()

    d = json.loads(p.stdout)

    assert d['executable'] == sys.executable
    assert d['argv'] == [op.join(sampledir, 'module1/__main__.py')]


async def test_no_guess(bootstrap: WaterBootstrap, sampledir: str):
    """
    Check that command guessing is turned off then `-n, --no-guess` is used.
    """

    # Module is ambiguous with `echo` command so the module will run
    p = await bootstrap.spawn('-V', '-C', sampledir, 'echo')
    assert await p.expect(f'starting.*-m echo')
    assert await p.expect(r'clean exit.*')
    await p.stop()

    # If this does not throw then it is our module
    d = json.loads(p.stdout)
    assert d

    # Using -n disables guessing
    p = await bootstrap.spawn('-Vn', '-C', sampledir, 'echo Hello World!')
    await p.stop()
    assert p.stdout == 'Hello World!\n'


# This test hangs for 30 seconds, sleep doesn't get killed for some reason
@pytest.mark.skip(reason='BUG - monitor:stop works from command-line but not from py.test')
async def test_exit_when_task_hung(bootstrap: WaterBootstrap, sampledir: str):
    """
    Test guessing when to insert the python interpreter in the path when the
    `--chdir` option is used.
    """

    p = await bootstrap.spawn('sleep 30')
    await asyncio.sleep(1)
    await p.stop()
    await asyncio.sleep(1)


async def test_parallel_commands(bootstrap: WaterBootstrap):
    p = await bootstrap.spawn('-P -x "echo ok" -- "echo ok"')
    await p.expect('starting.*')
    await p.expect('starting.*')
    await p.stop()
    assert p.stdout == 'ok\nok\n'

