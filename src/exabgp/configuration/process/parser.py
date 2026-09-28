"""parse_process.py

Created by Thomas Mangin on 2015-06-18.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.configuration.core.parser import Tokeniser

from exabgp.util.program import ENOENT, _make_path, resolve_program, validate_executable

__all__ = ['ENOENT', '_make_path', 'encoder', 'run']


def encoder(tokeniser: 'Tokeniser') -> str:
    value = tokeniser()

    if value not in ('text', 'json'):
        raise ValueError('"{}" is an invalid option'.format(value))
    return value


def _resolve_relative_program(tokeniser: 'Tokeniser', prg: str) -> str:
    """Resolve `prg` relative to the configuration file the tokeniser is reading."""
    return resolve_program(prg, tokeniser.fname)


def _validate_executable(prg: str) -> None:
    validate_executable(prg)


def run(tokeniser: 'Tokeniser') -> list[str]:
    """Parse and validate the 'run' command for a process.

    Args:
        tokeniser: Configuration tokeniser providing command tokens

    Returns:
        List containing program path and arguments

    Raises:
        ValueError: If program cannot be found or validated
        OSError: If file access fails
    """
    prg = tokeniser()

    if not prg:
        raise ValueError('the "run" command requires a program path\n  Format: run <path-to-executable>;')

    if prg[0] != '/':
        prg = _resolve_relative_program(tokeniser, prg)

    _validate_executable(prg)

    return [prg] + [_ for _ in tokeniser.generator]
