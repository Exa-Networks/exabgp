# encoding: utf-8
"""
location.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

# ===================================================================== Location
# file location


class Location (object):
	def __init__ (self, idx_line=0, idx_column=0, line=''):
		self.line = line
		self.idx_line = idx_line
		self.idx_column = idx_column
