from foremon.config import ForemonConfig
import os
from posixpath import dirname
import sys
import os.path as op
import shlex
from importlib.util import find_spec


def relative_if_cwd(path: str) -> str:
    """
    Converts `path` to a relative path iff it is child path of the cwd.
    """
    cwd: str = os.getcwd()
    if path.startswith(cwd):
        return op.relpath(path)
    return path


def guess_and_update_scripts(config: ForemonConfig):
    """
    Guess how to mutate arguments to conveniently execute python scripts or
    modules.

    This mutation is only applied to the default config.

    Cases handled:

    foremon script.py -> python script.py
    foremon script.py -> script.py (when script.py is executable)
    foremon module -> python -m module (if __main__ present)
    foremon path/to/module -> python -m module (PYTHONPATH=path/to if __main__ present)
    foremon module:main ->  python -c 'from module import main; main()' (if __init__ present but no __main__)
    foremon path/to/module:main ->  python -c 'from module import main; main()' (if __init__ present but no __main__)
    """

    if not config.scripts:
        return

    # Only applies to last script, other scripts are defined by the `-x` option.
    python = relative_if_cwd(sys.executable)
    script = config.scripts[-1]
    new_script = None
    args = shlex.split(script)
    if not args:
        return

    arg0 = args[0]
    func = None

    # handle `module:function` declarations
    if ':' in arg0:
        arg0, func = arg0.rsplit(':', 1)

    # remove trailing /
    arg0 = arg0.rstrip(op.sep)
    dirname = op.dirname(arg0)
    basename = op.basename(arg0)

    if arg0.endswith('.py'):
        # Attempt to insert python interpreter before script path if script is not executable
        if not os.access(arg0, os.X_OK):
            args.insert(0, python)
        new_script = ' '.join(args)
    elif op.isdir(arg0):
        # Invoke as `python -m directory` and update PYTHONPATH
        if op.isfile(op.join(arg0, '__main__.py')):

            args = [python, '-m', basename] + args[1:]
            new_script = ' '.join(args)

        # Invoke as `python -c 'from basename import func; func()'`
        elif func and op.isfile(op.join(arg0, '__init__.py')):
            py_script = f'from {basename} import {func}; {func}()'
            args = [python, '-c', shlex.quote(py_script)] + args[1:]
            new_script = ' '.join(args)

        if new_script and dirname:
            python_path = config.environment.get('PYTHONPATH', '')
            python_path = python_path.split(op.pathsep)
            python_path.insert(0, dirname)
            config.environment['PYTHONPATH'] = op.sep.join(python_path)
    elif find_spec(arg0) is not None:
        args = [python, '-m', basename] + args[1:]
        new_script = ' '.join(args)

    if new_script:
        # Replace the original script
        config.scripts[-1] = new_script
