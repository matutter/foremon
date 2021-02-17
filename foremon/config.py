import os
import signal
from enum import Enum
from typing import Any, Dict, List, Optional

import toml
from pydantic import BaseSettings, Field, validator

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


class ForemonConfig(BaseSettings):

    alias:           str = Field('')

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
        data = toml.loads(text)
        project = cls.parse_obj(data)
        return project


__all__ = ['PyProjectConfig', 'ToolConfig', 'ForemonConfig', 'Events']
