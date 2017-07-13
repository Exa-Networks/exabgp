# encoding: utf-8
"""
reactor/async.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.logger import Logger
from exabgp.vendoring import six


class ASYNC (object):
	def __init__ (self):
		self.logger = Logger()
		self._async = []

	def ready (self):
		return len(self._async) > 0

	def schedule (self, uid, command, callback):
		self.logger.debug('async | %s | %s' % (uid,command),'reactor')
		if self._async:
			self._async[0].append((uid,callback))
		else:
			self._async.append([(uid,callback),])

	def clear (self, deluid=None):
		if not self._async:
			return
		if deluid is None:
			self._async = []
			return
		running = []
		for (uid,generator) in self._async[0]:
			if uid != deluid:
				running.append((uid,generator))
		self._async.pop()
		if running:
			self._async.append(running)

	def run (self):
		if not self._async:
			return False
		running = []

		for (uid,generator) in self._async[0]:
			try:
				six.next(generator)
				six.next(generator)
				running.append((uid,generator))
			except StopIteration:
				pass
			except KeyboardInterrupt:
				raise
			except Exception as exc:
				self.logger.error('async | %s | problem with function' % uid,'reactor')
				for line in str(exc).split('\n'):
					self.logger.error('async | %s | %s' % (uid,line),'reactor')
		self._async.pop()
		if running:
			self._async.append(running)
		return True
