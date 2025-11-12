"""coroutine.py

Created by Thomas Mangin on 2013-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Any, TypeVar, Iterator

T = TypeVar('T')


def each(function: Callable[..., Iterator[T]]) -> Callable[..., Callable[[], T]]:
    @wraps(function)
    def start(*args: Any, **kwargs: Any) -> Callable[[], T]:
        generator = function(*args, **kwargs)
        return lambda: next(generator)  # noqa

    return start


def join(function: Callable[..., Iterator[str]]) -> Callable[..., str]:
    @wraps(function)
    def start(*args: Any, **kwargs: Any) -> str:
        return ''.join(function(*args, **kwargs))

    return start
