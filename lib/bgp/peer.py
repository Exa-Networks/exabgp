#!/usr/bin/env python
# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time

from bgp.data import NOP, Open, Update, Failure, Notification, SendNotification, KeepAlive

# Present a File like interface to socket.socket

class Peer (object):
	debug = False
	
	def dump (self,test,string):
		if self.follow and test: print time.strftime('%j %H/%M/%S',time.localtime()), '%15s/%7s' % (self.bgp.neighbor.peer_address.human(),self.bgp.neighbor.peer_as), string
	
	def __init__ (self,bgp,supervisor,follow=True):
		self.supervisor = supervisor
		self.bgp = bgp
		self.follow = True
		self.running = False
		self._loop = self._run()
	
	def run (self):
		try:
			self._loop.next()
		except StopIteration:
			pass
	
	def _run (self):
		self.running = True
		try:
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
			raise SendNotification(6,0)
		except SendNotification,e:
			print 'Sending notification (%d,%d) to peer' % (e.code,e.subcode)
			try:
				self.bgp.new_notification(e)
			except Failure:
				pass
		except Notification, n:
			print 'Notification Received', str(n)
		except Failure, e:
			print 'Failure Received', str(e)
		self.supervisor.unschedule(self.bgp.neighbor.peer_address.human())
		self.bgp.close()
	
	def shutdown (self):
		self.running = False
	
