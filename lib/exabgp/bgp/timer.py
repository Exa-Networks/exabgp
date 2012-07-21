# encoding: utf-8
"""
timer.py

Created by Thomas Mangin on 2012-07-21.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

import time

from exabgp.structure.log import Logger
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.notification import Notify

# Track the time for keepalive updates

class Timer (object):
	def __init__ (self,me,holdtime):
		self.logger = Logger()

		self.me = me
		self.holdtime = holdtime
		self.last_read = time.time()
		self.last_sent = time.time()

	def tick (self,message):
		left = int(self.last_read  + self.holdtime - time.time())
		self.logger.timers(self.me('Receive Timer %d second(s) left' % left))
		if left <= 0:
			raise Notify(4,0)
		if message.TYPE != NOP.TYPE:
			self.last_read = time.time()

	def keepalive (self):
		left = int(self.last_sent + self.holdtime.keepalive() - time.time())
		self.logger.timers(self.me('Sending Timer %d second(s) left' % left))

		if left <= 0:
			self.last_sent = time.time()
			return True
		return False
