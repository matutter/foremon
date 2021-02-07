import os
import os.path as op
import shutil
from runmon.display import display_debug

from .fixtures import *


async def test_help():
    p = await Runmon().spawn('--help')
    await p.stop()
    assert '--help' in p.stdout
    assert p.returncode == 0


async def test_version():
    p = await Runmon().spawn('--version')
    await p.stop()
    with open(get_version_file(), 'r') as fd:
        assert fd.read() == p.stdout.strip()


async def test_watch_one_file(tempfiles: Tempfiles):

    f1, f2 = tempfiles.make_files([
        'test/a.txt',
        'test/b.txt'
    ])

    p = await Runmon().spawn('-w', f1, '-e "*"', '-V', '-- rm', f2)
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

    p = await Runmon().spawn('-w', tempfiles.root, '-e "*"', '-V', '-- rm', f2)
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
