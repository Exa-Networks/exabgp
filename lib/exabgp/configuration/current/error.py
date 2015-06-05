from exabgp.configuration.environment import environment


class Error (object):

	def __init__ (self):
		self._error = ''
		self._debug = environment.settings().debug.configuration

	def set (self, message):
		self._error = message
		if self._debug:
			raise Exception()  # noqa
		return False

	def clear (self):
		self._error = ''

	def __repr__ (self):
		return self._error
