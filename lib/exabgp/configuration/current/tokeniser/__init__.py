# encoding: utf-8
"""
tokeniser.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.tokeniser.format import tokens


class Tokeniser (object):

	class Iterator (object):
		fname = ''  # This is ok to have a unique value as API parser do not use files

		def __init__ (self,tokens):
			def _generator ():
				for token in tokens:
					yield token

			self.tokens = tokens  # to help debugging
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
		self.index_column = 0
		self.index_line = 0
		self.fname = ''

		self._tokens = Tokeniser._off
		self._next = None
		self._data = None

	def clear (self):
		self.finished = False
		self.number = 0
		self.line = []
		self.iterate = None
		self.end = ''
		self.index_column = 0
		self.index_line = 0
		self.fname = ''
		if self._data:
			self._set(self._data)

	def _tokenise (self,iterator):
		for self.line,parsed in tokens(iterator):
			if not parsed:
				continue
			# ignore # lines
			# set Location information
			yield [word for x,word in parsed]

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
		self.Iterator.fname = data
		return self._set(_source(data))

	def set_text (self, data):
		def _source (data):
			for _ in self._tokenise(data.replace('\\\n',' ').split('\n')):
				yield _
		return self._set(_source(data))

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
