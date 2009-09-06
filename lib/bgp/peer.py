#!/usr/bin/env python
# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time

from bgp.data import Display
from bgp.data import NOP, Open, Update, Failure, Notification, SendNotification, KeepAlive
from bgp.protocol import Protocol,Network


# Present a File like interface to socket.socket

class Peer (Display):
	debug_timers = True		# debug hold/keepalive timers
	
	def __init__ (self,neighbor,supervisor):
		self.supervisor = supervisor
		self.neighbor = neighbor
		self.running = False
		self.restart = True
		self.bgp = Protocol(self.neighbor)
		self._loop = None

	def stop (self):
		self.running = False

	def shutdown (self):
		self.running = False
		self.restart = False
	
	def run (self):
		if self._loop:
			try:
				self._loop.next()
			except StopIteration:
				self._loop = None
		elif self.restart:
			self.running = True
			self._loop = self._run()
		else:
			self.bgp.close()
			self.supervisor.unschedule(self)
	
	def _run (self):
		try:
			self.bgp.connect()
		
			o = self.bgp.new_open()
			self.logIf(o,'-> %s' % o)
			yield

			o = self.bgp.read_open()
			self.logIf(o,'<- %s' % o)
			yield

			c,_ = self.bgp.new_keepalive(force=True)
			self.logIf(o,'-> KEEPALIVE')
			yield

			msg,data = self.bgp.read_keepalive()
			self.logIf(msg == KeepAlive.TYPE,'<- KEEPALIVE')

			a = self.bgp.new_announce()
			self.logIf(a,'-> %s' % a)

			while self.running:
				c = self.bgp.check_keepalive()
				self.logIf(self.debug_timers,'Receive Timer %d second(s) left' % c)

				c,k = self.bgp.new_keepalive()
				self.logIf(k,'-> KEEPALIVE')
				self.logIf(self.debug_timers,'Sending Timer %d second(s) left' % c)

				msg,data = self.bgp.read_message()
				self.logIf(msg == KeepAlive.TYPE,'<- KEEPALIVE')
				self.logIf(msg == Update.TYPE,'<- UPDATE')

				u = self.bgp.new_update()
				self.logIf(u,'-> %s' % u)

				yield 
			# User closing the connection
			raise SendNotification(6,0)
		except SendNotification,e:
			self.log('Sending Notification (%d,%d) to peer %s' % (e.code,e.subcode,str(e)))
			try:
				self.bgp.new_notification(e)
			except Failure:
				pass
			return
		except Notification, e:
			self.log('Received Notification (%d,%d) to peer %s' % (e.code,e.subcode,str(e)))
			return
		except Failure, e:
			self.log(str(e))
			return
	
