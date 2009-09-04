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
		self.running = True
		self.restart = True
		self.bgp = Protocol(self.neighbor)
		self.start()

	def start (self):
		self._loop = self._run()

	def stop (self):
		if self.running:
			self.running = False
		else:
			# The peer already stopped (due to a notification or conneciton issue)
			self.supervisor.unschedule(self)
	
	def run (self):
		try:
			self._loop.next()
		except StopIteration:
			pass
	
	def _run (self):
		self.restart = True
		
		try:
			self.bgp.connect()
		
			o = self.bgp.new_open()
			self.dump(o,'-> %s' % o)
			yield

			o = self.bgp.read_open()
			self.dump(o,'-> %s' % o)
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
			self.restart = False
			raise SendNotification(6,0)
		except SendNotification,e:
			print 'Sending Notification (%d,%d) to peer %s' % (e.code,e.subcode,str(e))
			try:
				self.bgp.new_notification(e)
			except Failure:
				pass
			self.respawn()
			return
		except Notification, n:
			print 'Received Notification (%d,%d) to peer %s' % (e.code,e.subcode,str(e))
			self.respawn()
			return
		except Failure, e:
			print str(e)
			# delay the retry
			for r in range(0,10):
				if self.running:
					yield
			self.respawn()
			return
		
		if not self.running:
			self.unschedule()
	
	def unschedule (self):
		self.supervisor.unschedule(self)
		self.bgp.close()
	
	def respawn (self):
		if self.restart:
			self.supervisor.respawn(self)
			self.bgp.close()
	