# water

water is a tool to help develop python projects by executing build tasks when
file changes are detected.

water intends to have feature parity to [nodemon][nodemon], a similar tool for
the NodeJS ecosystem, but provide those features within a python toolchain. To
use `water` run your script or module as `water [script or module]` or run
`water --help` for advanced usage.

File monitoring for water is provided by [watchdog][watchdog] which provides its
own shell-utility, [watchmedo][watchmedo].

water is currently in beta.

[nodemon]: https://www.npmjs.com/package/nodemon
[watchdog]: https://github.com/gorakhargosh/watchdog
[watchmedo]: https://github.com/gorakhargosh/watchdog#shell-utilities

# Installation

Clone `water` with git or install it using [pip][pip] (recommended):

```bash
pip install water
```

[pip]: https://packaging.python.org/tutorials/installing-packages/#use-pip-for-installing

# Usage

water will bootstrap your module or script with the arguments you normally pass
to it:

```bash
water [script or module] [args]
```

For CLI options, use `-h` or `--help`:

```bash
water -h
```

Using water is simple. It will guess if you are running a module or python
script and adjust the command-line arguments accordingly. To disable this
feature, add the `-n` (`--no-guess`) option.

```bash
# Executes `script.py`
water -n script.py

# Executes `python3 script.py`
water script.py

# Does not try to guess command
water node server.js
```

water runs scripts the python interpreter of the environment it is installed in
(`sys.executable`).
