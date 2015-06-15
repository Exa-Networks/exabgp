# encoding: utf-8
"""
tokeniser.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.tokeniser.location import Location
from exabgp.configuration.current.tokeniser.format import formated
from exabgp.configuration.current.tokeniser.format import unescape
from exabgp.configuration.current.tokeniser.format import tokens



class Tokeniser (Location):

	class Error (Exception):
		tabsize = 3
		syntax = ''

		def __init__ (self, location, message, syntax=''):
			self.line = location.line.replace('\t',' '*self.tabsize)
			self.index_line = location.index_line
			self.index_column = location.index_column + (self.tabsize-1) * location.line[:location.index_column].count('\t')

			self.message = '\n\n'.join((
				'problem parsing configuration file line %d position %d' % (location.index_line,location.index_column+1),
				'error message: %s' % message.replace('\t',' '*self.tabsize),
				'%s%s' % (self.line,'-' * self.index_column + '^')
			))
			# allow to give the right syntax in using Raised
			if syntax:
				self.message += '\n\n' + syntax

			Exception.__init__(self)

		def __repr__ (self):
			return self.message

	class Iterator (object):
		def __init__ (self,line):
			def _generator ():
				for _ in line:
					yield _

			self.line = line  # to help debugging
			self.generator = _generator()

		def __call__ (self):
			return self.generator.next()

	@staticmethod
	def _off ():
		raise StopIteration()

	def __init__ (self, scope, error, logger):
		self.scope = scope
		self.error = error
		self.logger = logger
		self.finished = False
		self.number = 0
		self.line = []
		self.iterate = Tokeniser._off
		self.end = ''

		self._tokens = Tokeniser._off
		self._next = None
		self._data = None

	def clear (self):
		self.finished = False
		self.number = 0
		self.line = []
		self.iterate = None
		self.end = ''
		if self._data:
			self._set(self._data)

	def _tokenise (self,iterator):
		for x,line,parsed in tokens(iterator):
			if not parsed:
				continue
			# ignore # lines
			# set Location information
			yield [word for y,word in parsed]

	def content (self, producer):
		try:
			while True:
				self.index_line,self.index_column,self.line,token = producer()
				if token[0] in ('"',"'"):
					return unescape(token[1:-1])
				else:
					return token
		except ValueError:
			raise Tokeniser.Error(self,'Could not parse %s' % str(token))
		except StopIteration:
			return None

	def _set (self, function):
		try:
			self._tokens = function
			self._next = self._tokens.next()
		except IOError,exc:
			error = str(exc)
			if error.count(']'):
				self.error.set(error.split(']')[1].strip())
			else:
				self.error.set(error)
			self._tokens = Tokeniser._off
			self._next = []
			return self.error.set('issue setting the configuration parser')
		except StopIteration:
			self._tokens = Tokeniser._off
			self._next = []
			return self.error.set('issue setting the configuration parser, no data')
		return True

	def set_file (self, data):
		def _source (fname):
			with open(fname,'r') as fileobject:
				for _ in self._tokenise(fileobject):
					yield _
		return self._set(_source(data))

	def set_text (self, data):
		def _source (data):
			for _ in self._tokenise(data.split('\n')):
				yield _
		return self._set(_source(data))

	# XXX: Horrible hack until I can move everything to a consumer API

	def __call__ (self):
		self.number += 1
		try:
			self.line, self._next = self._next, self._tokens.next()
			self.end = self.line[-1]
		except StopIteration:
			if not self.finished:
				self.finished = True
				self.line, self._next = self._next, []
				self.end = self.line[-1]
			else:
				self.line = []
				self.end = ''
		# This should raise a Location if called with no more data

		self.iterate = Tokeniser.Iterator(self.line[:-1])

		return self.line
