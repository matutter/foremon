import os
import os.path as op
import re
import shlex
from importlib.util import find_spec
from typing import List, Tuple

import click
from click.core import Context
from watchdog.events import FileSystemEvent

from . import __version__
from .display import *
from .monitor import Monitor

set_display_name('foremon')


def want_string(ctx, param, value: Tuple[str]):
    return ' '.join(list(value))


def want_list(ctx, param, value: Tuple[str]):
    """ Returns list of all items in value """
    l = []
    [l.extend(re.split(r'[\s,]+', v)) for v in list(value)]
    return l


def expand_exec(ctx, param, value: Tuple[str]):
    return list(value)


def expand_ext(ctx, param, value: Tuple[str]):
    value = want_list(None, None, value)
    return [(v if v.startswith('*') else '*'+v) for v in value]


def before_run(m: Monitor, ev: FileSystemEvent, scripts: List[str]):
    path: str = ev.src_path
    # display relative paths shorter
    cwd = os.getcwd()
    if path.startswith(cwd):
        path = path[len(cwd)+1:]
    display_info(f'triggered because {path} was {ev.event_type}')


def print_version(ctx: Context, param, value):
    if not value or ctx.resilient_parsing:
        return
    try:
        print(__version__)
    except:
        pass
    finally:
        ctx.exit()

def relative_if_cwd(path: str) -> str:
    """
    Converts `path` to a relative path iff it is child path of the cwd.
    """
    cwd: str = os.getcwd()
    if path.startswith(cwd):
        return op.relpath(path)
    return path

def guess_args(args: str) -> str:
    if not args: return args
    argv = shlex.split(args)
    if not argv: return args

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


@click.command(context_settings=dict(ignore_unknown_options=True))
@click.option('--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True,
              help='Print version and exit.')
@click.option('-f', '--config-file',
              type=click.Path(exists=True),
              help='Path to file config.')
@click.option('-e', '--ext',
              default='*', multiple=True,
              show_default=True, callback=expand_ext,
              help='File extensions to watch.')
@click.option('-w', '--watch',
              default='.', show_default=True,
              multiple=True, callback=want_list,
              help='File or directory patterns to watched for changes.')
@click.option('-i', '--ignore',
              multiple=True, default=[], callback=want_list,
              help='File or directory patterns to ignore.')
@click.option('-V', '--verbose',
              is_flag=True, default=False,
              help='Show details on what is causing restarts.')
@click.option('-P', '--parallel',
              is_flag=True, default=False,
              help='Allow scripts to execute in parallel if changes occur while another is running.')
@click.option('-x', '--exec',
              multiple=True, default=[], callback=expand_exec,
              help='Script to execute.')
@click.option('-u', '--unsafe',
              is_flag=True, default=False,
              help='Do not apply the default ignore list (.git, __pycache__/, etc...).')
@click.option('-n', '--no-guess',
              is_flag=True, default=False,
              help='Do not try to run commands as a script or module.')
@click.option('-C', '--chdir',
              help='Change to this directory before starting.')
@click.argument('args', callback=want_string, nargs=-1)
def foremon(ext: List[str], watch: List[str], ignore: List[str],
          verbose: bool, unsafe: bool, parallel: bool, no_guess: bool,
          exec: List[str], args: str,
          config_file: str = None, chdir: Optional[str] = None,):

    if chdir:
        os.chdir(chdir)

    if args and not no_guess:
        args = guess_args(args)

    if not unsafe:
        ignore.extend(['.git/*', '__pycache__/*', '.*'])

    m = Monitor(parallel=parallel)

    set_display_verbose(verbose)
    if verbose:
        m.before_run(before_run)

    scripts = list(filter(lambda s: s, exec[:] + [args]))
    if not scripts:
        display_warning("No script or executable specified, nothing to do ...")
        exit(2)

    add_ok = m.add_runner(scripts, watch, ext, ignore=ignore)
    if not add_ok:
        # only when all watch paths are missing
        exit(2)

    m.start_interactive()


def main():
    return foremon.main(prog_name=get_display_name())


if __name__ == '__main__':
    main()
