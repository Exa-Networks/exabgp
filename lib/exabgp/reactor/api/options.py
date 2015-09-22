#!/usr/bin/env python
# encoding: utf-8
"""
options.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

class APIOptions (dict):
	def set (self, key, value):
		self[key] = self.get(key,False) or value

	def set_value (self, direction, name, value):
		key = '%s-%s' % (direction,name)
		self[key] = self.get(key,False) or value

	def set_message (self, direction, name, value):
		raise RuntimeError('deprecated')
		# key = '%s-%d' % (direction,name)
		# self[key] = self.get(key,False) or value

	def __missing__ (self, key):
		return False


def hexstring (value):
	def spaced (value):
		for v in value:
			yield '%02X' % ord(v)
	return ''.join(spaced(value))
