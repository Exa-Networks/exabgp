# encoding: utf-8
"""
json.py

Created by Thomas Mangin on 2013-07-01.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from functools import wraps
from decimal import Decimal

def cofunction(function):
	@wraps(function)
	def start(*args, **kwargs):
		generator = function(*args, **kwargs)
		return lambda: generator.next()
	return start

def cojoin (function):
	@wraps(function)
	def start (*args, **kwargs):
		return ''.join(function(*args, **kwargs))
	return start

class JSONError(Exception):
	pass

class IncompleteJSONError(JSONError):
	pass

class UnexpectedData(JSONError):
	def __init__(self, line, position, token):
		super(UnexpectedData, self).__init__('Unexpected data at line %d position %d : "%s"' % (line,position,token))

@cojoin
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

def json (fname):
	with open(fname,'r') as stream:
		parser(tokens(stream))

@cofunction
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

def parser (tokeniser):
	def content(next):
		try:
			while True:
				line,position,token = next()

				if token == '{':
					d = dict()
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

	def iterate_dict(next):
		line,position,key = next()
		if key != '}':
			while True:
				if key[0] != '"':
					raise UnexpectedData(line,position,key)

				line,position,colon = next()
				if colon != ':':
					raise UnexpectedData(line,position,colon)

				yield key[1:-1],content(next)

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

	# while True:
	# 	print tokeniser()

	print content(tokeniser)

if __name__ == '__main__':
	json ('small.json')

# def stringlexem(self):
#	 start = self.pos + 1
#	 while True:
#		 try:
#			 end = self.buffer.index('"', start)
#			 escpos = end - 1
#			 while self.buffer[escpos] == '\\':
#				 escpos -= 1
#			 if (end - escpos) % 2 == 0:
#				 start = end + 1
#			 else:
#				 result = self.buffer[self.pos:end + 1]
#				 self.pos = end + 1
#				 return result
#		 except ValueError:
#			 old_len = len(self.buffer)
#			 self.buffer += self.f.read(BUFSIZE).decode('utf-8')
#			 if len(self.buffer) == old_len:
#				 raise common.IncompleteJSONError()
