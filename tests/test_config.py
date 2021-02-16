import signal

from foremon.config import *
from foremon.display import *
from pydantic.error_wrappers import ValidationError

from .fixtures import *


@pytest.mark.parametrize('toml', [
    """
[tools.foremon]
scripts = ['echo ok 1', 'echo ok 2']
paths = ['tests/input']
""",
    """
[tools.foremon]
patterns = ['*']
scripts = ['echo ok 1', 'echo ok 2']
paths = ['tests/input']

  [tools.foremon.test]
  patterns = ['*']
  scripts = ['echo test']
  paths = ['tests/input']
"""
])
def test_config_load_valid(toml: str):
    """
    Loading a valid pyproject.toml created a ForemonConfig.
    """

    project = PyProjectConfig.parse_toml(toml)
    assert project.tools.foremon
    assert isinstance(project.tools.foremon, ForemonConfig)


@pytest.mark.parametrize('toml', [
    """
[tools.other]
key = "value"
""",
    """

"""
])
def test_config_load_absent(toml: str):
    """
    Loading a pyproject.toml where tools.foremon is absent raises no exception.
    """
    project = PyProjectConfig.parse_toml(toml)
    assert project.tools.foremon is None


@pytest.mark.parametrize('toml', [
    """
[tools.foremon]
patterns = ['*']
# Error is here
scripts = 'echo ok 1'
paths = ['tests/input']
""",
    """
[tools.foremon]
patterns = ['*']
scripts = ['echo ok 1', 'echo ok 2']
paths = ['tests/input']

  [tools.foremon.test]
  patterns = ['*']
  scripts = ["echo test"]
  # Error is here
  paths = "tests/input"
"""
])
def test_config_load_invalid(toml: str):
    """
    Loading a pyproject.toml where tools.foremon has invalid properties will
    raise a ValidationError.
    """
    with pytest.raises(ValidationError):
        PyProjectConfig.parse_toml(toml)


@pytest.mark.parametrize('toml', [
    """
[tools.foremon]
patterns = ['*']
scripts = ['echo ok 1', 'echo ok 2']
paths = ['tests/input']

  [tools.foremon.test]
  patterns = ['*']
  scripts = ['echo test']
  paths = ['tests/input']
"""
])
def test_config_load_invalid(toml: str):
    """
    Loading a pyproject.toml where tools.foremon has invalid properties
    """
    project = PyProjectConfig.parse_toml(toml)
    assert len(project.tools.foremon.configs) > 0, 'missing nested configs'


@pytest.mark.parametrize('toml, term_signal', [
    ("""
[tools.foremon]
term_signal = 'SIGKILL'
scripts = ['true']
""", signal.SIGKILL),
    ("""
[tools.foremon]
term_signal = 9
scripts = ['true']
""", signal.SIGKILL),
    ("""
[tools.foremon]
term_signal = "9"
scripts = ['true']
""", signal.SIGKILL),
    ("""
[tools.foremon]
term_signal = "SIGTERM"
scripts = ['true']
""", signal.SIGTERM)
])
def test_config_term_signal_converts_to_int(toml: str, term_signal: int):
    conf = PyProjectConfig.parse_toml(toml).tools.foremon
    assert conf.term_signal == term_signal


def test_config_defaults():
    conf = PyProjectConfig.parse_toml("""
    [tools.foremon]
    scripts = ['true']
    """).tools.foremon

    from foremon.config import DEFAULT_EVENTS, DEFAULT_IGNORES

    assert conf.cwd == os.getcwd()
    assert conf.environment == {}
    assert conf.returncode == 0
    assert conf.term_signal == signal.SIGTERM
    assert conf.ignore_case == True
    assert conf.ignore_defaults == DEFAULT_IGNORES
    assert conf.ignore_dirs == True
    assert conf.ignore == []
    assert conf.paths == ['.']
    assert conf.patterns == ['*']
    assert conf.recursive == True
    assert conf.events == DEFAULT_EVENTS
