"""The vendored garbage dump, typed and compiled with mypyc."""

from __future__ import annotations

import gc

import pytest

from exabgp.vendoring import gcdump


class Uncollectable:
    """A class with Python source, so the dump can print it."""


def test_dump_prints_the_garbage_and_the_source_of_its_class(capsys: pytest.CaptureFixture[str]) -> None:
    kept = Uncollectable()
    # A builtin has no Python source: the dump says what it can and carries on.
    builtin = {'key': 'value'}
    gc.garbage.extend([kept, builtin])
    try:
        gcdump.dump()
    finally:
        gc.garbage.remove(kept)
        gc.garbage.remove(builtin)
    out = capsys.readouterr().out
    assert 'GARBAGE OBJECTS:' in out
    assert ".Uncollectable'>" in out
    assert 'line: class Uncollectable:' in out
    assert "{'key': 'value'}" in out
    assert out.count('line num:') == 1


def test_dump_cuts_a_long_description(capsys: pytest.CaptureFixture[str]) -> None:
    long_list = ['x' * 200]
    gc.garbage.append(long_list)
    try:
        gcdump.dump()
    finally:
        gc.garbage.remove(long_list)
    out = capsys.readouterr().out
    assert ':: ' + str(long_list)[: gcdump.MAX_DESCRIPTION_LENGTH] + '...' in out
