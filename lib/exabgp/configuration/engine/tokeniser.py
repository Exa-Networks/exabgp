# encoding: utf-8
"""
tokeniser.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.util import coroutine
from collections import defaultdict


# =============================================================== UnexpectedData
# reporting issue with the tokenisation

class UnexpectedData (Exception):
	def __init__(self, line, position, token):
		super(UnexpectedData, self).__init__('Unexpected data at line %d position %d : "%s"' % (line,position,token))



# ===================================================================== dictdict
# an Hardcoded defaultdict with dict as method

class dictdict (defaultdict):
	def __init__ (self):
		self.default_factory = dict


# convert special caracters

@coroutine.join
def unescape(s):
	start = 0
	while start < len(s):
		pos = s.find('\\', start)
		if pos == -1:
			yield s[start:]
			break
		yield s[start:pos]
		pos += 1
		esc = s[pos]
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
			yield chr(int(s[pos + 1:pos + 5], 16))
			pos += 4
		else:
			yield esc
		start = pos + 1


# A coroutine which return the next token, or string if quoted from the stream

@coroutine.each
def tokens (stream):
	spaces = [' ','\t','\r']
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
				else:
					if word:
						yield nb_lines,nb_chars,char
						word = ''
					break

			elif char in syntax:
				if quoted:
					word += char
				else:
					if word:
						yield nb_lines,nb_chars,word
						nb_chars += len(word)
						word = ''
					yield nb_lines,nb_chars,char
				nb_chars += 1

			elif char in spaces:
				if quoted:
					word += char
				elif word:
					yield nb_lines,nb_chars,word
					nb_chars += len(word)
					word = ''
				nb_chars += 1

			elif char in strings:
				word += char
				if quoted == char:
					quoted = ''
					yield nb_lines,nb_chars,word
					nb_chars += len(word) + 1
					word = ''
				else:
					quoted = char
					nb_chars += 1

			else:
				word += char
				nb_chars += 1

# ==================================================================== Tokeniser
# Return the next token from the configuration

class Tokeniser (object):
	def __init__ (self,name,stream):
		self.name = name                  # A unique name for this tokenier, so we can have multiple
		self.tokeniser = tokens(stream)   # A corouting giving us the next toker
		self._rewind = []                 # Should we want to rewind, the list of to pop first

		# each section can registered named configuration for reference here
		self.sections = defaultdict(dictdict)

	def __call__ (self):
		if self._rewind:
			return self._rewind.pop()
		self.line,self.position,self.token = Tokeniser.parser(self.tokeniser)
		return self.token

	# XXX: FIXME: line and position only work if we only rewind one element
	def rewind (self,token):
		self._rewind.append(token)

	@staticmethod
	def parser (tokeniser):
		def content(next):
			try:
				while True:
					line,position,token = next()

					if token == '[':
						l = []
						for element in iterate_list(next):
							l.append(element)
						return line,position,l
					elif token[0] in ('"',"'"):
						return line,position,unescape(token[1:-1])
					# elif token == 'true':
					# 	return True
					# elif token == 'false':
					# 	return False
					# elif token == 'null':
					# 	return None
					else:
						return line,position,token
			except ValueError:
				raise UnexpectedData(line,position,token)
			except StopIteration:
				return -1,-1,''

		def iterate_list(next):
			line,position,token = content(next)
			while token != ']':
				yield line,position,token
				line,position,token = content(next)

		return content(tokeniser)
