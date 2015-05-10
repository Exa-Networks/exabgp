# encoding: utf-8
"""
sequence.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


class Sequence (int):
	_instance = dict()

	def __new__ (cls):
		cls._instance['next'] = cls._instance.get('next', 0) + 1
		return cls._instance['next']
