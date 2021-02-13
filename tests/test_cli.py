import json
import os
import os.path as op
import shutil
import sys
from water.display import display_debug

from .fixtures import *


async def test_help():
    p = await WaterBootstrap().spawn('--help')
    await p.stop()
    assert '--help' in p.stdout
    assert p.returncode == 0


async def test_version():
    p = await WaterBootstrap().spawn('--version')
    await p.stop()
    from water import __version__
    assert p.stdout.strip() == __version__


async def test_watch_one_file(tempfiles: Tempfiles):

    f1, f2 = tempfiles.make_files([
        'test/a.txt',
        'test/b.txt'
    ])

    p = await WaterBootstrap().spawn('-w', f1, '-e "*"', '-V', '-- rm', f2)
    assert await p.expect(r'starting.*')
    assert await p.expect(r'clean exit.*')
    with open(f1, 'w') as fd:
        fd.write('modify')
    assert await p.expect(r'trigger.*modified')
    assert await p.expect(r'app crashed.*')
    await p.stop()


async def test_watch_one_dir(tempfiles: Tempfiles):

    f1, f2, f3 = tempfiles.make_files([
        'test/a.txt',
        'test/b.txt',
        'test/c.txt'
    ])

    p = await WaterBootstrap().spawn('-w', tempfiles.root, '-e "*"', '-V', '-- rm', f2)
    assert await p.expect(r'starting.*')
    assert await p.expect(r'clean exit.*')

    display_debug('modifying a file')
    with open(f1, 'w') as fd:
        fd.write('modify')

    assert await p.expect(r'trigger.*modified')
    assert await p.expect(r'app crashed.*')

    display_debug('deleting a file')
    os.unlink(f3)
    assert await p.expect(r'trigger.*deleted')
    assert await p.expect(r'app crashed.*')

    display_debug('moving a file')
    shutil.move(f1, f2)
    assert await p.expect(r'trigger.*moved')
    assert await p.expect(r'(app crashed|clean exit).*')

    await p.stop()


async def test_chdir_guess_insert_interpreter(sampledir: str):
    """
    Test guessing when to insert the python interpreter in the path when the
    `--chdir` option is used.
    """

    p = await WaterBootstrap().spawn('-V', '-C', sampledir, 'script1.py')
    await p.stop()

    d = json.loads(p.stdout)

    assert d['executable'] == sys.executable
    assert d['argv'] == ['script1.py']


async def test_guess_insert_interpreter(sampledir: str):
    """
    Test guessing when to insert the python interpreter in the path.
    """

    script = op.join(sampledir, 'script1.py')
    p = await WaterBootstrap().spawn('-V', script)
    await p.stop()

    d = json.loads(p.stdout)

    assert d['executable'] == sys.executable
    assert d['argv'] == [script]


async def test_guess_script_is_executable(sampledir: str):
    """
    Check that the interpreter is not inserted if the python script is
    executable.
    """

    script = op.join(sampledir, 'script2.py')

    p = await WaterBootstrap().spawn(script)
    await p.stop()

    d = json.loads(p.stdout)
    assert d['executable'] == ""
    assert d['argv'] == [script]


async def test_guess_insert_module(sampledir: str):
    """
    Check that `python -m` is inserted into the command when a python module is detected.
    """

    p = await WaterBootstrap().spawn('-V', '-C', sampledir, 'module1')

    python = op.basename(sys.executable)
    assert await p.expect(f'starting.*{python} -m module1')
    assert await p.expect(r'clean exit.*')
    await p.stop()

    d = json.loads(p.stdout)

    assert d['executable'] == sys.executable
    assert d['argv'] == [op.join(sampledir, 'module1/__main__.py')]


async def test_no_guess(sampledir: str):
    """
    Check that command guessing is turned off then `-n, --no-guess` is used.
    """

    # Module is ambiguous with `echo` command so the module will run
    p = await WaterBootstrap().spawn('-V', '-C', sampledir, 'echo')
    assert await p.expect(f'starting.*-m echo')
    assert await p.expect(r'clean exit.*')
    await p.stop()

    # If this does not throw then it is our module
    d = json.loads(p.stdout)
    assert d

    # Using -n disables guessing
    p = await WaterBootstrap().spawn('-Vn', '-C', sampledir, 'echo Hello World!')
    await p.stop()
    assert p.stdout == 'Hello World!\n'
