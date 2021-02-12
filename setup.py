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
version = read('water/__init__.py', r'__version__ = "([^"]+)"')

# Use the entire README
long_description = read('README.md')

# Dependencies from requirements
install_requires = read('requirements.txt')

setup(
  name="water",
  version=version,
  description="Task automation based on filesystem changes",
  long_description=long_description,
  long_description_content_type='text/markdown',
  author="Mathew Utter",
  author_email="mcutter.svc@gmail.com",
  license="MIT",
  url="http://github.com/matutter/water",
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
    'License :: OSI Approved :: MIT',
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
    'Programming Language :: Python :: 3.10',
    'Topic :: Software Development :: Automation',
    'Topic :: Software Development :: Libraries',
    'Topic :: System :: Filesystems',
    'Topic :: System :: Monitoring',
    'Topic :: Utilities',
  ],
  packages=find_packages(include=['water']),
  install_requires=install_requires,
  cmdclass={
    'build_ext': build_ext,
  },
  entry_points={'console_scripts': [
    'water = water.__main__:main',
  ]},
  python_requires='>=3.6',
  # Due to README.md, requirements.txt, etc...
  zip_safe=False
)
