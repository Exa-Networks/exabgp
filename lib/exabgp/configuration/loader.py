# encoding: utf-8
"""
configuration.py

Created by Thomas Mangin on 2013-03-15.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.configuration import json

class InvalidFormat (Exception):
	"Raised when the configuration can not be parsed"
	pass


class Format (object):
	"""
	Store class used to convert the configuration format to json
	Every configuration file must start with the line "#syntax: <format>\n"
	where <format> is one of the class defined within format (simplejson or json)
	"""

	class simplejson (object):
		"""
		the new format, which is a json bastard
		* single line (no non-json nesting), the parser does not handle it
		* keyword do not need to be quoted
		(ie: key: "value" as a shortcut for "key": "value")
		* the dictionary do not need a
		(ie: storage { } as a shortcut for "storage" : { })
		* comma between lines will be automatically added
		* will ignore every line which first non-space (or tab) character is #
		"""

		@staticmethod
		def skip (current):
			striped = current.strip()
			return striped == '' or striped[0] == '#'

		@staticmethod
		def read (last,current):
			_last = last.strip()
			_current = current.strip()
			prefix = '\n'

			# do not allow nesting
			if '{' in current and (current.count('{') > 1 or not '{\n' in current):
				raise InvalidFormat('You can not write "%s", only one { per name is allowed' % _current)

			# automatically add the comma
			if last:
				if _current == '}' or _current == ']':
					pass
				elif not _last.endswith('{') and not _last.endswith('['):
					prefix = ',\n'

			# handle the non-quoted keys
			if ':' in _current:
				position = current.find(_current)
				key = _current.split(':',1)[0]
				if '"' not in key:
					return prefix + current[:position] + '"%s"' % key + current[position+len(key):].rstrip()
			# handle the simple dictionary
			elif _current.endswith('{') and not _current.startswith('{'):
				position = current.find(_current)
				section = _current.split()[0]
				if '"' not in section:
					return prefix + current[:position] + '"%s":' % section + current[position+len(section):].rstrip()
			# nothing to change
			else:
				return prefix + current.rstrip()

	class json (object):
		"""
		raw json reader without any modification to allow easier scripting
		"""
		@staticmethod
		def skip (current):
			return False

		@staticmethod
		def read (last,current):
			return current


class Reader (object):
	"""
	A file-like object providing a read() method which will convert
	the configuration in JSON following the format information set at
	the start of the file with the "#syntax: <format>"
	"""
	def __init__ (self,fname):
		self.file = open(fname,'rb')
		self.last = ''      # the last line we read from the file
		self.formated = ''  # the formated data we have already converted

		name = ''.join(self.file.readline().split())
		if not name.startswith('#syntax:'):
			name = '#syntax:json'
			self.file.close()
			self.file = open(fname,'rb')

		klass = getattr(Format,name[8:],None)
		if not klass:
			raise InvalidFormat('unknown configuration format')

		self.format = klass.read
		self.skip = klass.skip

	def __del__(self):
		if self.file:
			self.file.close()
			self.file = None

	def __enter__ (self):
		return self

	def __exit__(self, type, value, tb):
		if self.file:
			self.file.close()
			self.file = None

	def read (self,number=0):
		# we already done the work, just return the small chunks
		if number and len(self.formated) >= number:
			returned, self.formated = self.formated[:number], self.formated[number:]
			return returned

		data = bytearray()

		try:
			# restore / init the last line seen
			last = self.last

			# reading up to number bytes or until EOF which will raise StopIteration
			while not number or len(data) < number:
				new = self.file.next()
				if self.skip(new):
					continue
				data += self.format(last,new)
				last = new

			# save the last line seen for the next call
			self.last = last

			if number:
				complete = self.formated + bytes(data)
				returned, self.formated = complete[:number], complete[number:]
				return returned

			return bytes(data)
		except StopIteration:
			# we can come here twice : on EOF and again
			# to empty self.formated when its len becomes smaller than number
			complete = self.formated + bytes(data)
			if number:
				returned, self.formated = complete[:number], complete[number:]
				return returned
			else:
				self.formated = ''
				return complete

	def readline (self, limit=-1):
		returned = bytearray()
		while limit < 0 or len(returned) < limit:
			byte = self.read(1)
			if not byte:
				break
			returned += byte
			if returned.endswith(b'\n'):
				break
		return bytes(returned)

	def __iter__ (self):
		if not self.file:
			raise ValueError("I/O operation on closed file.")
		return self

	def next (self):
		line = self.readline()
		if not line:
			raise StopIteration
		return line

	__next__ = next

def load (fname):
	"""
	Convert a exa configuration format to its dictionary representation
	Can raise InvalidFormat and all file related exceptions such as IOError
	"""
	with Reader(fname) as reader:
		return json.load(reader)

def parse (fname):
	"""
	Convert a exa configuration format to its json representation
	Can raise InvalidFormat and all file related exceptions such as IOError
	"""
	with Reader(fname) as reader:
		return reader.read()

__all__ = [load,parse,InvalidFormat]
