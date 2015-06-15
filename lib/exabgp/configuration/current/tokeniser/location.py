# encoding: utf-8
"""
location.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

# ===================================================================== Location
# file location


class Location (object):
	def __init__ (self, index_line=0, index_column=0, line=''):
		self.line = line
		self.index_line = index_line
		self.index_column = index_column

	def clear (self):
		self.index_line = 0
		self.index_column = 0
		self.line = ''
