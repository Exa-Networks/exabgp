# encoding: utf-8
"""
tokeniser.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.format import formated


class Tokeniser (object):
	def __init__ (self, error, logger):
		self.error = error
		self.logger = logger
		self.finished = False
		self.number = 0
		self.line = []

		self._tokens = []
		self._next = None
		self._data = None

	def clear (self):
		self.finished = False
		self.number = 0
		self.line = []
		if self._data:
			self.set(self._data)

	def _tokenise (self,iterator):
		for line in iterator:
			replaced = formated(line)
			if not replaced:
				continue
			if replaced.startswith('#'):
				continue
			command = replaced[:3]
			if command in ('md5','asm'):
				string = line.strip()[3:].strip()
				if string[-1] == ';':
					string = string[:-1]
				yield [command,string,';']
			elif replaced[:3] == 'run':
				yield [t for t in replaced[:-1].split(' ',1) if t] + [replaced[-1]]
			else:
				yield [t.lower() for t in replaced[:-1].split(' ') if t] + [replaced[-1]]

	def _tokenise_text (self, data):
		for _ in self._tokenise(data.split('\n')):
			yield _

	def _tokenise_file (self, fname):
		with open(fname,'r') as fileobject:
			for _ in self._tokenise(fileobject):
				yield _

	def _set (self, function):
		def empty_generator ():
			for _ in range(0):
				yield _

		try:
			self._tokens = function()
			self._next = self._tokens.next()
		except IOError,exc:
			error = str(exc)
			if error.count(']'):
				self.error.set(error.split(']')[1].strip())
			else:
				self.error.set(error)
			self._tokens = empty_generator()
			self._next = []
		except StopIteration:
			self._tokens = empty_generator()
			self._next = []
		return self

	def set_file (self, data):
		return self._set(lambda: self._tokenise_file(data))

	def set_text (self, data):
		return self._set(lambda: self._tokenise_text(data))

	def next (self):
		self.number += 1
		try:
			self.line, self._next = self._next, self._tokens.next()
		except StopIteration:
			self.finished = True
			self.line, self._next = self._next, []
		return self.line
