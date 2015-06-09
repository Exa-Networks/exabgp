# encoding: utf-8
"""
scope.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

class Scope (object):
	def __init__ (self):
		self.content = []
		self.location = ['root']

	def clear (self):
		self.content = [{}]
		self.location = ['root']
