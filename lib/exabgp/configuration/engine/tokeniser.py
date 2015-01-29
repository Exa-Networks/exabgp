# encoding: utf-8
"""
tokeniser.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.util import coroutine
from exabgp.configuration.engine.location import Location
from exabgp.configuration.engine.raised import Raised

# convert special caracters


@coroutine.join
def unescape (string):
	start = 0
	while start < len(string):
		pos = string.find('\\', start)
		if pos == -1:
			yield string[start:]
			break
		yield string[start:pos]
		pos += 1
		esc = string[pos]
		if esc == 'b':
			yield '\b'
		elif esc == 'f':
			yield '\f'
		elif esc == 'n':
			yield '\n'
		elif esc == 'r':
			yield '\r'
		elif esc == 't':
			yield '\t'
		elif esc == 'u':
			yield chr(int(string[pos + 1:pos + 5], 16))
			pos += 4
		else:
			yield esc
		start = pos + 1


# A coroutine which return the producer token, or string if quoted from the stream

@coroutine.each
def tokens (stream):
	spaces = [' ','\t','\r','\n']
	strings = ['"', "'"]
	syntax = [',','[',']','{','}']
	comment = ['#',]
	nb_lines = 0
	for line in stream:
		nb_lines += 1
		nb_chars = 0
		quoted = ''
		word = ''
		for char in line:
			if char in comment:
				if quoted:
					word += char
					nb_chars += 1
				else:
					if word:
						yield nb_lines,nb_chars,line,char
						word = ''
					break

			elif char in syntax:
				if quoted:
					word += char
				else:
					if word:
						yield nb_lines,nb_chars-len(word),line,word
						word = ''
					yield nb_lines,nb_chars,line,char
				nb_chars += 1

			elif char in spaces:
				if quoted:
					word += char
				elif word:
					yield nb_lines,nb_chars-len(word),line,word
					word = ''
				nb_chars += 1

			elif char in strings:
				word += char
				if quoted == char:
					quoted = ''
					yield nb_lines,nb_chars-len(word),line,word
					word = ''
				else:
					quoted = char
				nb_chars += 1

			else:
				word += char
				nb_chars += 1

# ==================================================================== Tokeniser
# Return the producer token from the configuration


class Tokeniser (Location):
	def __init__ (self, name, stream):
		super(Tokeniser,self).__init__()
		self.name = name                  # A unique name for this tokenier, so we can have multiple
		self.tokeniser = tokens(stream)   # A corouting giving us the producer toker
		self._rewind = []                 # Should we want to rewind, the list of to pop first

	def __call__ (self):
		if self._rewind:
			return self._rewind.pop()
		token = self.content(self.tokeniser)
		return token

	# XXX: FIXME: line and position only work if we only rewind one element
	def rewind (self, token):
		self._rewind.append(token)

	def content (self, producer):
		try:
			while True:
				self.idx_line,self.idx_column,self.line,token = producer()
				if token == '[':
					returned = []
					for token in self.iterate_list(producer):
						returned.append((self.idx_line,self.idx_column,self.line,token))
					return returned
				elif token[0] in ('"',"'"):
					return unescape(token[1:-1])
				else:
					return token
		except ValueError:
			raise Raised(Location(self.idx_line,self.idx_column,self.line),'Could not parse %s' % str(token))
		except StopIteration:
			return None

	def iterate_list (self, producer):
		token = self.content(producer)
		while token and token != ']':
			yield token
			token = self.content(producer)
