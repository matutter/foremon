import os
import signal
from enum import Enum
from itertools import count
from typing import Any, Dict, List, MutableMapping, Optional

import toml
from pydantic import BaseSettings, Field, validator
from pydantic.main import BaseModel

DEFAULT_IGNORES = [
    # Some of these are redundant
    '.git/*', '__pycache__/*', '.*',
    '.tox/*', '.venv/*', '.pytest_cache/*'
]

DEFAULT_EVENTS = [
    'modified', 'deleted'
]


class Events(str, Enum):
    created = 'created'
    modified = 'modified'
    deleted = 'deleted'
    moved = 'moved'


Increment = count(start=0)


def NextIncrement():
    global Increment
    val = next(Increment)
    return val


def SetIncrement(start: int = 0):
    global Increment
    Increment = count(start=start)


class ForemonConfig(BaseSettings):

    alias: str = Field('')
    order: Optional[int]

    ################################
    # Script execution
    ################################
    cwd:             str = Field(os.getcwd())
    environment:     Dict = Field(default_factory=dict)
    returncode:      int = Field(0)
    scripts:         List[str] = Field(default_factory=list)
    term_signal:     int = Field(int(signal.SIGTERM))

    ################################
    # Change monitoring
    ################################
    ignore_case:     bool = Field(True)
    ignore_defaults: List[str] = Field(default_factory=DEFAULT_IGNORES.copy)
    ignore_dirs:     bool = Field(True)
    ignore:          List[str] = Field(default_factory=list)
    paths:           List[str] = Field(default_factory=['.'].copy)
    patterns:        List[str] = Field(default_factory=['*'].copy)
    recursive:       bool = Field(True)
    events:          List[Events] = Field(default_factory=DEFAULT_EVENTS.copy)

    skip:            bool = Field(False)
    configs:         List['ForemonConfig'] = Field(default_factory=list)

    @validator('term_signal', pre=True)
    def validate_term_signal(cls, value) -> int:
        if isinstance(value, str):
            if hasattr(signal.Signals, value):
                value = getattr(signal.Signals, value)
        return int(value)

    @validator('paths', 'patterns', 'ignore')
    def validate_expandvars(cls, value) -> Any:
        if value:
            if isinstance(value, list):
                value = list(map(os.path.expandvars, value))
            elif isinstance(value, str):
                value = os.path.expandvars(value)
        return value

    @validator('order')
    def validate_order(cls, value) -> int:
        """
        If and `order` is set explicitly we increment the default anyway. This
        will ensure default `order` values will have a consistant value related
        to their delcaration in the config file.

        Due to the order-of-operations used by Pydantic internally we can't use
        the Field default_factory.
        """

        inc = NextIncrement()
        if value is None:
            value = inc
        return value

    class Config:
        env_prefix = 'foremon_'
        # we mutate objects while parsing objects to handle sub-configs
        extra = 'forbid'
        anystr_strip_whitespace = True

    def __init__(self, *args, **kwargs):
        configs = kwargs.get('configs', [])
        kwargs['configs'] = configs

        for name in list(kwargs.keys()):
            if name in self.__fields__:
                continue

            # extra fields that are dicts are treated as configs
            if not isinstance(kwargs[name], dict):
                continue

            obj = kwargs.pop(name)

            obj['alias'] = name
            configs.append(obj)
        super().__init__(*args, **kwargs)

    def get_env(self) -> MutableMapping[str, str]:
        env = os.environ.copy()
        env.update(self.environment)
        return env

    def get_configs(self) -> List['ForemonConfig']:
        """
        Generator yields all configs in order
        """
        configs = [self]
        ordered: List[ForemonConfig] = []
        while configs:
            config = configs.pop(0)
            configs.extend(config.configs)
            ordered.append(config)
        return sorted(ordered, key=lambda c: c.order)


ForemonConfig.update_forward_refs()


class ToolConfig(BaseSettings):

    foremon: Optional[ForemonConfig]

    class Config:
        extra = 'allow'


class PyProjectConfig(BaseSettings):

    tool: ToolConfig = Field(default_factory=ToolConfig)

    class Config:
        extra = 'allow'

    @classmethod
    def parse_toml(cls, text: str) -> 'PyProjectConfig':
        # TODO - Do this without a global. We need to reset this to zero each
        # time a config is reloaded to keep auto-values constant between config
        # reloads.
        SetIncrement(0)
        data = toml.loads(text)
        project = cls.parse_obj(data)
        return project


class ForemonOptions(BaseModel):
    aliases: List[str] = Field(['default'])
    config_file: Optional[str]
    cwd: Optional[str]
    dry_run: bool = Field(False)
    ignore: List[str] = Field([])
    no_guess: bool = Field(False)
    paths: List[str] = Field([])
    patterns: List[str] = Field([])
    scripts: List[str] = Field([])
    unsafe: bool = Field(False)
    use_all: bool = Field(False)
    verbose: bool = Field(False)
    auto_reload: bool = Field(True)
    dwell: float = Field(0.1)


__all__ = ['PyProjectConfig', 'ToolConfig',
           'ForemonConfig', 'Events', 'ForemonOptions']
