# encoding: utf-8
"""
reader.py

Created by Thomas Mangin on 2013-03-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


class InvalidFormat (Exception):

	"""Raised when the configuration can not be parsed"""

	pass


class Format (object):

	r"""Text formating class

	Store class used to convert the configuration format to json
	Every configuration file must start with the line "#syntax: <format>\\n"
	where <format> is one of the class defined within format (simplejson or json)
	"""

	class exabgp (object):

		"""raw reader without any modification"""

		@staticmethod
		def skip (current):
			return False

		@staticmethod
		def read (last, current):
			return current


class Reader (object):

	"""File like object

	providing a read() method which will convert the configuration
	in JSON following the format information set at
	the start of the file with the "#syntax: <format>"
	"""

	def __init__ (self, fname):
		self.file = open(fname,'rb')
		self.last = ''      # the last line we read from the file
		self.formated = ''  # the formated data we have already converted

		name = ''.join(self.file.readline().split())
		if not name.startswith('#syntax:'):
			name = '#syntax:exabgp'
			self.file.close()
			self.file = open(fname,'rb')

		klass = getattr(Format,name[8:],None)
		if not klass:
			raise InvalidFormat('unknown configuration format')

		self.format = klass.read
		self.skip = klass.skip

	def __del__ (self):
		if self.file:
			self.file.close()
			self.file = None

	def __enter__ (self):
		return self

	def __exit__ (self, dtype, value, tb):
		if self.file:
			self.file.close()
			self.file = None

	def read (self, number=0):
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
