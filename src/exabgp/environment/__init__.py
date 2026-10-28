from __future__ import annotations

import os

# Import base constants
from exabgp.environment.base import (
    APPLICATION,
    ENVFILE,
    ETC,
    ROOT,
)

# Import new typed configuration system
from exabgp.environment.config import Environment

__all__ = [
    'APPLICATION',
    'ENVFILE',
    'ETC',
    'ROOT',
    'Env',
    'Environment',
    'getconf',
    'getenv',
]


def getenv() -> Environment:
    """Return the global environment configuration."""
    Environment.setup()
    return Environment.instance()


def getconf(name: str) -> str:
    # some users are using symlinks for atomic change of the configuration file
    # using mv may however be better practice :p
    # so we must not follow symlink when looking for the file
    normalised: str
    if name.startswith('etc/exabgp'):
        normalised = os.path.join(ETC, name[11:])
    else:
        normalised = os.path.normpath(name)

    absolute: str = os.path.abspath(normalised)
    if os.path.isfile(absolute):
        return absolute

    return ''


# Backward compatibility - Env class alias
Env = Environment
