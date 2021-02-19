#!usr/bin/env python3

from setuptools import setup, find_packages
from setuptools.command.build_ext import build_ext
import os.path as op
import re

def read(file, pattern = None):
  this_dir = op.abspath(op.dirname(__file__))
  with open(op.join(this_dir, file), encoding='utf-8') as fd:
    text = fd.read().strip()
    if pattern:
      text = re.findall(pattern, text)[0]
    return text

# Extract the __version__ value from __init__.py
version = read('foremon/__init__.py', r'__version__ = "([^"]+)"')

# Use the entire README
long_description = read('README.md')

# Dependencies from requirements
install_requires = """
ansicolors>=1.1.8
click>=7.1.2
watchdog>=1.0.2
toml>=0.10.2
pydantic>=1.7.3
"""

setup(
  name="foremon",
  version=version,
  description="Automatically restart applications when file changes are detected.",
  long_description=long_description,
  long_description_content_type='text/markdown',
  author="Mathew Utter",
  author_email="mcutter.svc@gmail.com",
  license="MIT",
  url="http://github.com/matutter/foremon",
  keywords=' '.join([
    'python',
    'filesystem',
    'monitoring',
    'scripting',
    'task',
    'automation'
  ]),
  classifiers=[
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Natural Language :: English',
    'Operating System :: POSIX :: Linux',
    'Operating System :: MacOS :: MacOS X',
    'Operating System :: POSIX :: BSD',
    'Operating System :: Microsoft :: Windows :: Windows Vista',
    'Operating System :: Microsoft :: Windows :: Windows 7',
    'Operating System :: Microsoft :: Windows :: Windows 8',
    'Operating System :: Microsoft :: Windows :: Windows 8.1',
    'Operating System :: Microsoft :: Windows :: Windows 10',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3 :: Only',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Topic :: Software Development :: Build Tools',
    'Topic :: Software Development :: Libraries',
    'Topic :: System :: Filesystems',
    'Topic :: System :: Monitoring',
    'Topic :: Utilities',
  ],
  packages=find_packages(include=['foremon']),
  install_requires=install_requires,
  requires=re.findall(r'^\w+', install_requires, re.MULTILINE),
  cmdclass={
    'build_ext': build_ext,
  },
  entry_points={'console_scripts': [
    'foremon = foremon.cli:main',
  ]},
  python_requires='>=3.6.1',
  # Due to README.md, requirements.txt, etc...
  zip_safe=False
)
