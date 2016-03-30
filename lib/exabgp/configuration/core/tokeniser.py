# encoding: utf-8
"""
tokeniser.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.core.format import tokens
from exabgp.protocol.family import AFI
from collections import deque


class Tokeniser (object):

	class Iterator (object):
		fname = ''  # This is ok to have a unique value as API parser do not use files

		def __init__ (self):
			self.next = deque()
			self.tokens = []
			self.generator = iter([])

		def replenish (self, content):
			self.next.clear()
			self.tokens = content
			self.generator = iter(content)
			return self

		def clear (self):
			self.replenish([])

		def __call__ (self):
			if self.next:
				return self.next.popleft()

			try:
				return self.generator.next()
			except StopIteration:
				return ''

		def peek (self):
			try:
				peaked = self.generator.next()
				self.next.append(peaked)
				return peaked
			except StopIteration:
				return ''

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
		self.iterate = Tokeniser.Iterator()
		self.end = ''
		self.index_column = 0
		self.index_line = 0
		self.fname = ''
		self.type = 'unset'
		self.afi = AFI.undefined

		self._tokens = Tokeniser._off
		self._next = None
		self._data = None

	def clear (self):
		self.finished = False
		self.number = 0
		self.line = []
		self.iterate.clear()
		self.end = ''
		self.index_column = 0
		self.index_line = 0
		self.fname = ''
		self.type = 'unset'
		if self._data:
			self._set(self._data)

	def params (self):
		if len(self.line) <= 2:
			return ''
		if self.end in ('{','}',';'):
			return "'%s'" % "' '".join(self.line[1:-1])
		return "'%s'" % "' '".join(self.line[1:])

	def _tokenise (self,iterator):
		for parsed in tokens(iterator):
			words = [word for y,x,word in parsed]
			self.line = ''.join(words)
			# ignore # lines
			# set Location information
			yield words

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
				def formated ():
					while True:
						line = fileobject.next().rstrip()
						self.index_line += 1
						while line.endswith('\\'):
							line = line[:-1] + fileobject.next().rstrip()
							self.index_line += 1
						yield line
				for _ in self._tokenise(formated()):
					yield _
		self.type = 'file'
		self.Iterator.fname = data
		return self._set(_source(data))

	def set_text (self, data):
		def _source (data):
			for _ in self._tokenise(data.split('\n')):
				yield _
		self.type = 'text'
		return self._set(_source(data))

	def set_api (self, line):
		return self._set(self._tokenise(iter([line])))

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

		# should we raise a Location if called with no more data ?
		self.iterate.replenish(self.line[:-1])

		return self.line
