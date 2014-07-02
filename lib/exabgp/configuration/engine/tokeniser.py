from exabgp.util import coroutine

class UnexpectedData (Exception):
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
	spaces = [' ','\t','\r','\n']
	strings = ['"', "'"]
	syntax = [',','[',']','{','}',';']
	comment = ['#',]
	nb_lines = 0
	for line in stream:
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

class Tokeniser (object):
	def __init__ (self,stream):
		self.tokeniser = tokens(stream)
		self._rewind = []

	def __call__ (self):
		if self._rewind:
			return self._rewind.pop()
		return Tokeniser.parser(self.tokeniser)

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
						return l
					elif token[0] in ('"',"'"):
						return unescape(token[1:-1])
					# elif token == 'true':
					# 	return True
					# elif token == 'false':
					# 	return False
					# elif token == 'null':
					# 	return None
					else:
						return token
			except ValueError:
				raise UnexpectedData(line,position,token)
			except StopIteration:
				return ''

		def iterate_list(next):
			token = content(next)
			while token != ']':
				yield token
				token = content(next)

		return content(tokeniser)
