"""mypyc.py

The class markers mypyc reads, usable without mypyc installed.

`trait` and `mypyc_attr` live in mypy_extensions, which the compiled build has and a
pure Python install may not. The type checker, and therefore mypyc, always sees the real
ones. At run time they are imported when present and otherwise replaced by decorators
which return the class unchanged, so ExaBGP keeps no runtime dependency.

See plan/wip-mypyc.md.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from mypy_extensions import mypyc_attr, trait
else:
    try:
        from mypy_extensions import mypyc_attr, trait
    except ImportError:
        _Class = TypeVar('_Class')

        def trait(cls: _Class) -> _Class:
            return cls

        def mypyc_attr(*attributes: str, **values: Any) -> Callable[[_Class], _Class]:
            def unchanged(cls: _Class) -> _Class:
                return cls

            return unchanged


__all__ = ['mypyc_attr', 'trait']
