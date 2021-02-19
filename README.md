# foremon

[![ci](https://github.com/matutter/foremon/workflows/CI/badge.svg?event=push)](https://github.com/matutter/foremon/actions?query=event%3Apush+branch%3Amaster+workflow%3ACI)
[![coverage](https://codecov.io/gh/matutter/foremon/branch/master/graph/badge.svg)](https://codecov.io/gh/matutter/foremon)
[![pypi](https://img.shields.io/pypi/v/foremon.svg)](https://pypi.python.org/pypi/foremon)
[![downloads](https://img.shields.io/pypi/dm/foremon.svg)](https://pypistats.org/packages/foremon)
[![versions](https://img.shields.io/pypi/pyversions/foremon.svg)](https://github.com/matutter/foremon)
[![license](https://img.shields.io/github/license/matutter/foremon.svg)](https://github.com/matutter/foremon/blob/master/LICENSE)

foremon is a tool to help develop python projects by executing build tasks when
file changes are detected.

foremon intends to have feature parity to [nodemon][nodemon], a similar tool for
the NodeJS ecosystem, but provide those features within a python toolchain. To
use `foremon` run your script or module as `foremon [script or module]` or run
`foremon --help` for advanced usage.

File monitoring is provided by [watchdog][watchdog] which provides its own
shell-utility, [watchmedo][watchmedo].

foremon is currently in beta.

[nodemon]: https://www.npmjs.com/package/nodemon
[watchdog]: https://github.com/gorakhargosh/watchdog
[watchmedo]: https://github.com/gorakhargosh/watchdog#shell-utilities

# Installation

Clone `foremon` with git or install it using [pip][pip] (recommended):

```bash
pip install foremon
```

[pip]: https://packaging.python.org/tutorials/installing-packages/#use-pip-for-installing

# Usage

foremon will bootstrap your module or script with the arguments you normally
pass to it:

```bash
foremon [script or module] [args]
```

If your application uses options which conflict with foremon's options use the
`--` argument separator.

```bash
foremon -- mymodules --version
```

For CLI options, use `-h` or `--help`:

```bash
foremon -h
```

Using foremon is simple. It will guess if you are running a module or python
script and adjust the command-line arguments accordingly. To disable this
feature, add the `-n` (`--no-guess`) option.

```bash
# Executes `script.py`
foremon -n -- script.py

# Executes `python3 script.py`
foremon -- script.py

# Does not try to guess command. `test` is ambiguous because it is a
# shell-builtin and python module.
foremon -- test -f script.py
```

foremon runs python scripts with the python interpreter of the environment it is
installed in (`sys.executable`).

All foremon output is prefixed with `[foremon]` and written to `stderr`. Output
from your script, errors included, will be echoed out as expected.

If no script is given, foremon will test for a `pyproject.toml` file and if
found, will run scripts specified in the `[tool.foremon]` section
[(ref.)](#pyproject.toml).

# Automatic re-running

When file changes are detected foremon will restart the script. If scripts are
still running when the change is detected, foremon will ignore the event until
the script completes and a new change occurs.

# Manual restart

Scripts may be manually restarted by typing `rs` and `enter` in the terminal
where foremon is running. If a script is still running when `rs` is entered then
foremon will terminate the script with a signal. By default `SIGTERM` is sent
but the signal may be changed by setting `term_signal` in the config file.

foremon can also be shutdown gracefully by typing `exit` followed by `enter`.
Just using `ctrl+c` has the same effect.

# pyproject.toml

> support for pyproject.toml

foremon supports _pyproject.toml_ configuration files. If the project contains a
_pyproject.toml_ file foremon will automatically load defaults from the
`[tool.foremon]` section. An alternative config file may be specified with the
`-f` (`--config-file`) option.

All configuration settings are optional but foremon wont begin monitoring for
changes if there are no `scripts` to run.

foremon will automatically reload the config file if it changes while foremon is
running. Using the `--no-reload` option will disable this feature.

```ini
[tool.foremon]
# Only watch files ending in .py
patterns = ["*.py"]
# Run these scripts in-order on-change
scripts = ["pytest --cov=myproj"]
# Only run if explicitly run with `-a [alias]
skip = true
# Run script like they're in this directory
cwd = "./"
# Key-Value paris of environment variables
[tool.foremon.environment]
TERM = "MONO"
# Exit code to expect for a successful exit
returncode = 0
# Signal to send if the process should be terminated
term_signal = "SIGTERM"
# Set to false to turn on case-sensitive pattern matching
ignore_case = true
# List of default ignored paths like .git, or .tox
ignore_defaults = []
# Ignore changes to directories
ignore_dirs = true
# A list of patterns to ignore
ignore = ["*/build/*"]
# Paths to watch for changes
paths = ["src/"]
# Watch paths recursively
recursive = true
# List of events - created, deleted, moved, modified
events = ["created", "modified"]
```

All subsections contain the same options.

foremon supports multiple monitor and script definitions. Sections in the config
file matching `[tool.foremon.*]`, where `*` is the alias for the section, may be
defined in addition to the default section.

To run these other sections specify the `-a [alias]` option. The `-a` option may
be used multiple times or the `--all` option can be used to turn on all tasks.


```ini
[tool.foremon]
patterns = ["*.c", "*.h"]
scripts = ["./configure"]

  # Run me with 'foremon -a make'
  [tool.foremon.make]
  patterns = ["make*"]
  paths = ["src/*"]
  scripts = ["make -C src"]
  events = ["created"]

  [tool.foremon.other]
  scripts = ["echo skipped"]
  skip = true
```

Any command-line arguments passed to foremon only supersede definitions in
default section.

For other example of foremon's `pyproject.toml` configuration please refer to
the [configuration samples][config].

[config]: /config
