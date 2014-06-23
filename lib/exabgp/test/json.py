# encoding: utf-8
"""
json.py

Created by Thomas Mangin on 2013-07-01.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from decimal import Decimal

from exabgp.util import coroutine

class JSONError(Exception):
	pass

class UnexpectedData(JSONError):
	def __init__(self, line, position, token):
		super(UnexpectedData, self).__init__('Unexpected data at line %d position %d : "%s"' % (line,position,token))

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

@coroutine.each
def tokens (stream):
	spaces = [' ', '\t', '\r', '\n']
	strings = ['"', "'"]
	syntax = [',','[',']','{','}']
	nb_lines = 0
	for line in stream:
		nb_lines += 1
		nb_chars = 0
		quoted = ''
		word = ''
		for char in line:
			if char in spaces:
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

			else:
				word += char
				nb_chars += 1

def parser (tokeniser,container):
	# Yes, you can add attributes to function ...
	tokeniser.path = []

	def content(next):
		try:
			while True:
				line,position,token = next()

				if token == '{':
					klass = container(next.path)
					d = klass()
					for key,value in iterate_dict(next):
						d[key] = value
					return d
				elif token == '[':
					l = []
					for element in iterate_list(next):
						l.append(element)
					return l
				elif token[0] == '"':
					return unescape(token[1:-1])
				elif token == 'true':
					return True
				elif token == 'false':
					return False
				elif token == 'null':
					return None
				elif token == ']':  # required for parsing arrays
					return ']'
				else:
					# can raise ValueError
					return Decimal(token) if '.' in token else int(token)
		except ValueError:
			raise UnexpectedData(line,position,token)
		except StopIteration:
			return ''

	def iterate_dict(next):
		line,position,key = next()
		if key != '}':
			while True:
				if key[0] != '"':
					raise UnexpectedData(line,position,key)

				line,position,colon = next()
				if colon != ':':
					raise UnexpectedData(line,position,colon)

				next.path.append(key)
				yield key[1:-1],content(next)
				next.path.pop()

				line,position,separator = next()
				if separator == '}':
					break
				if separator != ',':
					raise UnexpectedData(line,position,separator)
				line,position,key = next()

	def iterate_list(next):
		value = content(next)
		if value != ']':
			while True:
				yield value

				line,position,separator = next()
				if separator == ']':
					break
				if separator != ',':
					raise UnexpectedData(line,position,separator)

				value = content(next)

	return content(tokeniser)


def load (stream,container=lambda _:dict):
	return parser(tokens(stream),container)

__all__ = [load,JSONError,UnexpectedData]
