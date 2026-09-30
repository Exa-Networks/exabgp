"""The mypyc class markers work whether or not mypy_extensions is installed."""

from __future__ import annotations

import builtins
import importlib
import sys
from types import ModuleType
from typing import Any

import pytest

import exabgp.util.mypyc


def _reload_without_mypy_extensions(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    real_import = builtins.__import__

    def refuse(name: str, *args: Any, **kwargs: Any) -> ModuleType:
        if name == 'mypy_extensions':
            raise ImportError('mypy_extensions is not installed')
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, 'mypy_extensions', raising=False)
    monkeypatch.setattr(builtins, '__import__', refuse)
    return importlib.reload(exabgp.util.mypyc)


def test_markers_leave_the_class_unchanged_without_mypy_extensions(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_without_mypy_extensions(monkeypatch)
    try:

        class Marked:
            pass

        assert module.trait(Marked) is Marked
        assert module.mypyc_attr(allow_interpreted_subclasses=True)(Marked) is Marked
        assert module.mypyc_attr('value')(Marked) is Marked
    finally:
        monkeypatch.undo()
        importlib.reload(exabgp.util.mypyc)


def test_markers_come_from_mypy_extensions_when_installed() -> None:
    pytest.importorskip('mypy_extensions')
    assert exabgp.util.mypyc.trait.__module__ == 'mypy_extensions'
    assert exabgp.util.mypyc.mypyc_attr.__module__ == 'mypy_extensions'
