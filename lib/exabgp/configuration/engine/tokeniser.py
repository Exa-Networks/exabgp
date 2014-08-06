# encoding: utf-8
"""
tokeniser.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.util import coroutine


# =============================================================== UnexpectedData
# reporting issue with the tokenisation

class UnexpectedData (Exception):
	tabsize = 3

	def __init__(self, idx_line, idx_position, line, error):
		self.line = line.replace('\t',' '*self.tabsize)
		self.error = error
		self.idx_line = idx_line
		self.idx_position = idx_position + (self.tabsize-1) * line[:idx_position].count('\t')

		super(UnexpectedData, self).__init__(
			'\n\n'.join((
				'problem parsing configuration file line %d position %d' % (idx_line,idx_position),
				'error message: %s' % error,
				'%s\n%s' % (self.line,'-'* self.idx_position + '^')
			))
		)

	def __str__ (self):
		return self.args[0]

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
						yield nb_lines,nb_chars,char,line
						word = ''
					break

			elif char in syntax:
				if quoted:
					word += char
				else:
					if word:
						yield nb_lines,nb_chars,word,line
						nb_chars += len(word)
						word = ''
					yield nb_lines,nb_chars,char,line
				nb_chars += 1

			elif char in spaces:
				if quoted:
					word += char
				elif word:
					yield nb_lines,nb_chars,word,line
					nb_chars += len(word)
					word = ''
				nb_chars += 1

			elif char in strings:
				word += char
				if quoted == char:
					quoted = ''
					yield nb_lines,nb_chars,word,line
					nb_chars += len(word) + 1
					word = ''
				else:
					quoted = char
					nb_chars += 1

			else:
				word += char
				nb_chars += 1

# ==================================================================== Tokeniser
# Return the producer token from the configuration

class Tokeniser (object):
	def __init__ (self,name,stream):
		self.name = name                  # A unique name for this tokenier, so we can have multiple
		self.tokeniser = tokens(stream)   # A corouting giving us the producer toker
		self._rewind = []                 # Should we want to rewind, the list of to pop first

	def __call__ (self):
		if self._rewind:
			return self._rewind.pop()
		self.idx_line,self.idx_position,self.token,self.line = Tokeniser.parser(self.tokeniser)
		return self.token

	# XXX: FIXME: line and position only work if we only rewind one element
	def rewind (self,token):
		self._rewind.append(token)

	@staticmethod
	def parser (tokeniser):
		def content(producer):
			try:
				while True:
					idx_line,idx_position,token,line = producer()
					if token == '[':
						returned = []
						for token in iterate_list(producer):
							returned.append(token)
						return idx_line,idx_position,returned,line
					elif token[0] in ('"',"'"):
						return idx_line,idx_position,unescape(token[1:-1]),line
					else:
						return idx_line,idx_position,token,line
			except ValueError:
				raise UnexpectedData(idx_line,idx_position,token,line)
			except StopIteration:
				return -1,-1,'',''

		def iterate_list(producer):
			idx_line,idx_position,token,line = producer()
			while token and token != ']':
				yield token
				idx_line,idx_position,token,line = producer()

		return content(tokeniser)
