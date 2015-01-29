# encoding: utf-8
"""
timer.py

Created by Thomas Mangin on 2012-07-21.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import time

from exabgp.logger import Logger
from exabgp.bgp.message.nop import _NOP
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.notification import Notify

# ================================================================ ReceiveTimer
# Track the time for keepalive updates


class ReceiveTimer (object):
	def __init__ (self, me, holdtime, code, subcode, message=''):
		self.logger = Logger()
		self.me = me

		self.holdtime = holdtime
		self.last_read = time.time()

		self.code = code
		self.subcode = subcode
		self.message = message

	def check_ka (self, message=_NOP,ignore=_NOP.TYPE):
		if message.TYPE != ignore:
			self.last_read = time.time()
		if self.holdtime:
			left = int(self.last_read  + self.holdtime - time.time())
			self.logger.timers(self.me('Receive Timer %d second(s) left' % left))
			if left <= 0:
				raise Notify(self.code,self.subcode,self.message)
		elif message.TYPE == KeepAlive.TYPE:
			raise Notify(2,6,'Negotiated holdtime was zero, it was invalid to send us a keepalive messages')


class SendTimer (object):
	def __init__ (self, me, holdtime):
		self.logger = Logger()
		self.me = me

		self.keepalive = holdtime.keepalive()
		self.last_sent = int(time.time())

	def need_ka (self):
		if not self.keepalive:
			return False

		now  = int(time.time())
		left = self.last_sent + self.keepalive - now

		if now != self.last_sent:
			self.logger.timers(self.me('Send Timer %d second(s) left' % left))

		if left <= 0:
			self.last_sent = now
			return True
		return False
