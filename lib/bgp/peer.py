#!/usr/bin/env python
# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time

from bgp.data import NOP, Open, Update, Failure, Notification, SendNotification, KeepAlive
from bgp.protocol import Protocol,Network


# Present a File like interface to socket.socket

class Peer (object):
	debug = False
	
	def dump (self,test,string):
		if self.follow and 	test: print time.strftime('%j %H:%M:%S',time.localtime()), '%15s/%7s' % (self.neighbor.peer_address.human(),self.neighbor.peer_as), string
	
	def __init__ (self,neighbor,supervisor,follow=True):
		self.supervisor = supervisor
		self.neighbor = neighbor
		self.follow = follow
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
			self.dump(o,'-> %s' % o)
			yield

			o = self.bgp.read_open()
			self.dump(o,'<- %s' % o)
			yield

			c,_ = self.bgp.new_keepalive(force=True)
			self.dump(o,'-> KEEPALIVE')
			yield

			msg,data = self.bgp.read_keepalive()
			self.dump(msg == KeepAlive.TYPE,'<- KEEPALIVE')

			a = self.bgp.new_announce()
			self.dump(a,'-> %s' % a)

			while self.running:
				c = self.bgp.check_keepalive()
				if self.debug: print 'Receive Timer', self.bgp.network.host, ':', c, 'second(s) left'

				c,k = self.bgp.new_keepalive()
				self.dump(k,'-> KEEPALIVE')
				if self.debug: print 'Sending Timer', self.bgp.network.host, ':', c, 'second(s) left'

				msg,data = self.bgp.read_message()
				self.dump(msg == KeepAlive.TYPE,'<- KEEPALIVE')
				self.dump(msg == Update.TYPE,'<- UPDATE')

				u = self.bgp.new_update()
				self.dump(u,'-> %s' % u)

				yield 
			# User closing the connection
			raise SendNotification(6,0)
		except SendNotification,e:
			self.dump(True,'Sending Notification (%d,%d) to peer %s' % (e.code,e.subcode,str(e)))
			try:
				self.bgp.new_notification(e)
			except Failure:
				pass
			return
		except Notification, n:
			self.dump(True,'Received Notification (%d,%d) to peer %s' % (e.code,e.subcode,str(e)))
			return
		except Failure, e:
			self.dump(True,str(e))
			return
	
