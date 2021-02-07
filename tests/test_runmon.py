import asyncio
import os.path as op
from .fixtures import *


async def test_help():
    p = await Runmon().spawn('--help')
    await p.stop()
    assert '--help' in p.stdout
    assert p.returncode == 0

async def test_version():
    p = await Runmon().spawn('--version')
    await p.stop()
    with open(get_version_file(),'r') as fd:
      assert fd.read() == p.stdout.strip()

async def test_watch_one_file(tempfiles:Tempfiles):

  f1, f2 = tempfiles.make_files([
    'test/a.txt',
    'test/b.txt'
  ])

  p = await Runmon().spawn('-w', f1, '-e "*"', '-V', '-- rm', f2)

  await asyncio.sleep(.1)

  with open(f1, 'w') as fd:
    fd.write('modify')

  await asyncio.sleep(.1)
  await p.stop()

  # rm ../b.txt exited with status == 1
  assert 'returned 1' in p.stderr
  # stopped batch script because a non-zero exit
  assert 'exec stopped' in p.stderr


async def test_watch_one_dir(tempfiles:Tempfiles):

  f1, f2 = tempfiles.make_files([
    'test/a.txt',
    'test/b.txt'
  ])

  p = await Runmon().spawn('-w', tempfiles.root, '-e "*"', '-V', '-- rm', f2)

  await asyncio.sleep(1)

  with open(f1, 'w') as fd:
    fd.write('modify')

  await asyncio.sleep(1)
  await p.stop()

  # rm ../b.txt exited with status == 1
  assert 'returned 1' in p.stderr
  # stopped batch script because a non-zero exit
  assert 'exec stopped' in p.stderr
