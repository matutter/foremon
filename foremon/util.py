import os
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


def guess_args(args: str) -> str:
    if not args:
        return args
    argv = shlex.split(args)
    if not argv:
        return args

    arg0: str = argv[0]

    if arg0.endswith('.py'):
        # Attempt to insert python interpreter before script path if script is not executable
        is_x = os.access(arg0, os.X_OK)
        if not is_x:
            argv.insert(0, relative_if_cwd(sys.executable))
        # Attempt to insert `python -m` before module name if arg[0] is dir
    elif op.isdir(arg0):
        init_file = op.join(arg0, '__main__.py')
        if op.isfile(init_file):
            argv = [relative_if_cwd(sys.executable), '-m'] + argv

    else:
        # Attempt run as module that isn't local
        spec = find_spec(arg0)
        if spec is not None:
            argv = [relative_if_cwd(sys.executable), '-m'] + argv

    # shlex.join not in py3.7
    return " ".join(argv)