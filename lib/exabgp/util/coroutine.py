# encoding: utf-8
"""
coroutine.py

Created by Thomas Mangin on 2013-07-01.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from functools import wraps


def each (function):
	@wraps(function)
	def start (*args, **kwargs):
		generator = function(*args, **kwargs)
		return lambda: generator.next()  # noqa
	return start


def join (function):
	@wraps(function)
	def start (*args, **kwargs):
		return ''.join(function(*args, **kwargs))
	return start
