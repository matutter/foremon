# foremon

foremon is a tool to help develop python projects by executing build tasks when
file changes are detected.

foremon intends to have feature parity to [nodemon][nodemon], a similar tool for
the NodeJS ecosystem, but provide those features within a python toolchain. To
use `foremon` run your script or module as `foremon [script or module]` or run
`foremon --help` for advanced usage.

File monitoring for foremon is provided by [watchdog][watchdog] which provides
its own shell-utility, [watchmedo][watchmedo].

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

For CLI options, use `-h` or `--help`:

```bash
foremon -h
```

Using foremon is simple. It will guess if you are running a module or python
script and adjust the command-line arguments accordingly. To disable this
feature, add the `-n` (`--no-guess`) option.

```bash
# Executes `script.py`
foremon -n script.py

# Executes `python3 script.py`
foremon script.py

# Does not try to guess command
foremon node server.js
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
still running when the change is detected, foremon will signal the current
process with `SIGTERM` before restarting.

# Manual restart

Scripts may be manually restarted while foremon is running by typing `rs` and
then `enter` in the terminal where foremon is running.

foremon can also be shutdown gracefully by typing `exit` followed by `enter`.

# pyproject.toml

> support for pyproject.toml is under development

foremon supports _pyproject.toml_ configuration files. If the project contains a
_pyproject.toml_ file foremon will automatically load defaults from the
`[tool.foremon]` section. An alternative config file may be specified with the
`-f` (`--config-file`) option.

```ini
[tool.foremon]
# Only watch files ending in .py
ext = ["*.py"]
# Only watch files in these paths
paths = ["tests/*", "foremon/*"]
# Ignore everything under these paths
ignore = ["tests/input/*"]
# Run these scripts in-order on-change
scripts = [
  "pytest --coverage",
  "coverage"
  ]
```

foremon supports script aliasing in the config file. Sections with names
matching `[tool.foremon.*]`, where `*` is replaced with your alias`, can be ran
instead of the default script.

```ini
[tool.foremon]
  [tool.foremon.make]
  ext = ["*.c", "*.h", "make*"]
  paths = ["src/*"]
  scripts = ["make -C src"]
```

This alias may be run with `foremon run make`.

Any command-line arguments passed to foremon supersede definitions in config
files.
