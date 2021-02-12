import os
import os.path as op
import re
from typing import List, Tuple

import click
from click.core import Context
from watchdog.events import FileSystemEvent

from .display import *
from .monitor import Monitor
from . import __version__

set_display_name('water')


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


@click.command()
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
@click.argument('args', callback=want_string, nargs=-1)
def water(ext: List[str], watch: List[str], ignore: List[str],
          verbose: bool, unsafe: bool, parallel: bool,
          exec: List[str], args: str, config_file: str = None):

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
    water.main(prog_name=get_display_name())


if __name__ == '__main__':
    main()
