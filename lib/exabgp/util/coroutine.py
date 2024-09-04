# encoding: utf-8
"""
coroutine.py

Created by Thomas Mangin on 2013-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from functools import wraps
from exabgp.vendoring import six


def each(function):
    @wraps(function)
    def start(*args, **kwargs):
        generator = function(*args, **kwargs)
        return lambda: six.next(generator)  # noqa

    return start


def join(function):
    @wraps(function)
    def start(*args, **kwargs):
        return ''.join(function(*args, **kwargs))

    return start
