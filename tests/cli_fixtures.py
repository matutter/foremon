"""
Fixtures specific to Click.
"""

from foremon.display import display_verbose, set_display_verbose
from typing import Any, Callable, List

import pytest
from click.testing import CliRunner, Result

from .fixtures import *

CliProg = Callable[[List[Any]], Result]


@pytest.fixture
def cli(request: SubRequest,  output: CapLines) -> Result:
    from foremon.cli import foremon

    def run(*args):
        cmd = " ".join(list(map(str, args)))
        runner = CliRunner(mix_stderr=False)
        result: Result = runner.invoke(foremon, cmd)
        output.stdout_append(result.stdout)
        output.stderr_append(result.stderr)
        return result


    # If testing the `-V` flag we can accidentally toggle this global and
    # contaminate other tests checking for debug output indicators.
    current_verbose = display_verbose()

    def reset_display():
        set_display_verbose(current_verbose)

    request.addfinalizer(reset_display)

    return run


__all__ = ['cli', 'CliProg', 'Result']
