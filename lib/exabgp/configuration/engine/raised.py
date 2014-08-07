# encoding: utf-8
"""
raised.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

# =============================================================== UnexpectedData
# reporting issue with the tokenisation

class UnexpectedData (Exception):
	tabsize = 3

	# idx_column is the number of char read
	# so when it reports zero, it is the first character

	def __init__(self, idx_line, idx_column, line, error):
		self.error = error.replace('\t',' '*self.tabsize)
		self.line = line.replace('\t',' '*self.tabsize)
		self.idx_line = idx_line
		self.idx_column = idx_column + (self.tabsize-1) * line[:idx_column].count('\t')

		super(UnexpectedData, self).__init__(
			'\n\n'.join((
				'problem parsing configuration file line %d position %d' % (idx_line,idx_column+1),
				'error message: %s' % error,
				'%s%s' % (self.line,'-'* self.idx_column + '^')
			))
		)

	def __str__ (self):
		return self.args[0]


# ======================================================================= Raised
# To replace Fxception, and give line etc.

class Raised (UnexpectedData):
	syntax = ''

	def __init__ (self,tokeniser,message,syntax=''):
		super(Raised,self).__init__(
			tokeniser.idx_line,
			tokeniser.idx_column,
			tokeniser.line,
			message
		)
		# allow to give the right syntax in using Raised
		if syntax:
			self.syntax = syntax

	def __str__ (self):
		return '\n\n'.join((
			UnexpectedData.__str__(self),
			'syntax:\n%s' % self.syntax if self.syntax else '',
		))
