# encoding: utf-8
"""
timer.py

Created by Thomas Mangin on 2012-07-21.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time

from exabgp.logger import Logger
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.notification import Notify

# Track the time for keepalive updates

_NOP = NOP()

class Timer (object):
	def __init__ (self,me,holdtime,code,subcode,message=''):
		self.logger = Logger()

		self.me = me

		self.code = code
		self.subcode = subcode
		self.message = message

		self.holdtime = holdtime
		self.last_read = time.time()
		self.last_sent = time.time()

	def tick (self,message=_NOP,ignore=_NOP.TYPE):
		if message.TYPE != ignore:
			self.last_read = time.time()
		if self.holdtime:
			left = int(self.last_read  + self.holdtime - time.time())
			self.logger.timers(self.me('Receive Timer %d second(s) left' % left))
			if left <= 0:
				raise Notify(self.code,self.subcode,self.message)
		elif message.TYPE == KeepAlive.TYPE:
			raise Notify(2,6,'Holdtime is zero and we got a keepalive message')

	def keepalive (self):
		if not self.holdtime:
			return False

		left = int(self.last_sent + self.holdtime.keepalive() - time.time())
		self.logger.timers(self.me('Sending Timer %d second(s) left' % left))

		if left <= 0:
			self.last_sent = time.time()
			return True
		return False
