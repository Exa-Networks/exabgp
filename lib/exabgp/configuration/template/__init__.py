# encoding: utf-8
"""
template.py

Created by Thomas Mangin on 2015-06-16.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.core import Section
from exabgp.configuration.neighbor import ParseNeighbor


class ParseTemplate (Section):
	syntax = ''

	name = 'template'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		self._names = []

	def pre (self):
		return True

	def post (self):
		return True
