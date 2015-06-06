# encoding: utf-8
"""
raised.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

# ======================================================================= Raised
# reporting issue with the tokenisation


class Raised (Exception):
	tabsize = 3
	syntax = ''

	def __init__ (self, location, message, syntax=''):
		self.line = location.line.replace('\t',' '*self.tabsize)
		self.idx_line = location.idx_line
		self.idx_column = location.idx_column + (self.tabsize-1) * location.line[:location.idx_column].count('\t')

		self.message = '\n\n'.join((
			'problem parsing configuration file line %d position %d' % (location.idx_line,location.idx_column+1),
			'error message: %s' % message.replace('\t',' '*self.tabsize),
			'%s%s' % (self.line,'-' * self.idx_column + '^')
		))
		# allow to give the right syntax in using Raised
		if syntax:
			self.message += '\n\n' + syntax

		Exception.__init__(self)

	def __str__ (self):
		return self.message
