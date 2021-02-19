import re
from typing import List, Tuple

import click
from click.core import Context

import foremon.display as display
from foremon.app import DEFAULT_CONFIG, Foremon
from foremon.config import ForemonOptions
from foremon.errors import ForemonError

from . import __version__


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


def print_version(ctx: Context, param, value):
    if not value or ctx.resilient_parsing:
        return

    print(__version__)
    ctx.exit()


@click.command(context_settings=dict(ignore_unknown_options=True))
@click.option('--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True,
              help='Print version and exit.')
@click.option('-f', '--config-file',
              default=DEFAULT_CONFIG, show_default=False,
              help='Path to file config.')
@click.option('-e', '--ext', 'patterns',
              default='*', multiple=True,
              show_default=True, callback=expand_ext,
              help='File extensions to watch.')
@click.option('-w', '--watch', 'paths',
              default='.', show_default=True,
              multiple=True, callback=want_list,
              help='File or directory patterns to watched for changes.')
@click.option('-i', '--ignore',
              multiple=True, default=[], callback=want_list,
              help='File or directory patterns to ignore.')
@click.option('-V', '--verbose',
              is_flag=True, default=False,
              help='Show details on what is causing restarts.')
@click.option('-x', '--exec', 'scripts',
              multiple=True, default=[], callback=expand_exec,
              help='Script to execute.')
@click.option('-u', '--unsafe',
              is_flag=True, default=False,
              help='Do not apply the default ignore list (.git, __pycache__/, etc...).')
@click.option('-n', '--no-guess',
              is_flag=True, default=False,
              help='Do not try to run commands as a script or module.')
@click.option('-C', '--chdir', 'cwd',
              help='Change to this directory before starting.')
@click.option('-A', '--all', 'use_all',
              is_flag=True, default=False, show_default=True,
              help='Run all scripts in the config unless skipped.')
@click.option('-a', '--alias', 'aliases',
              multiple=True, default=['default'],
              help='Run the alias from the config.')
@click.option('--dry-run', is_flag=True, hidden=True)
@click.option('--reload/--no-reload', 'auto_reload',
              is_flag=True, default=True,
              help='Automatically reload the config if it changes.')
@click.argument('args', callback=want_string, nargs=-1)
def foremon(verbose: bool, args: str, scripts: List[str], version=None, **kwargs):

    display.set_display_verbose(verbose)

    scripts = list(filter(lambda s: s, scripts + [args]))
    options = ForemonOptions(verbose=verbose, scripts=scripts, **kwargs)
    mon = Foremon(options)

    try:
        returncode = mon.run_forever()
        exit(returncode)
    except ForemonError as e:
        display.display_error(f'error {e.code}: {e.message}')
        exit(e.code)


def main():
    display.set_display_name('foremon')
    return foremon.main(prog_name=display.get_display_name())
