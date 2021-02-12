#!usr/bin/env python3

from setuptools import setup, find_packages
from setuptools.command.build_ext import build_ext

from water import __version__ as version


def requirements_txt(path='requirements.txt'):
    return filter(lambda l: l, [l.strip() for l in open(path).readlines()])

def readme(path='README.md'):
  return open(path).read().strip()

packages = find_packages(include=['water'])
install_requires = list(requirements_txt())

setup(name="water",
      version=version,
      description="Task automation based on filesystem changes",
      long_description=readme(),
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
          'Development Status :: 5 - Production/Stable',
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
      package_dir={'': 'water'},
      packages=find_packages('water'),
      include_package_data=True,
      cmdclass={
          'build_ext': build_ext,
      },
      entry_points={'console_scripts': [
          'water = water:main',
      ]},
      python_requires='>=3.6',
      zip_safe=True
)
