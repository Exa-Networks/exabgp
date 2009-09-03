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
	debug = True
	
	def __init__ (self,bgp,supervisor):
		self.supervisor = supervisor
		self.running = False
		self.bgp = bgp
		self._loop = self._run()
	
	def run (self):
		try:
			self._loop.next()
		except StopIteration:
			pass
	
	def _run (self):
		self.running = True
		try:
			print 'Peer', self.bgp.neighbor.peer_address.human()
			o = self.bgp.new_open()
			if self.debug and o: print "->", o
			yield

			print 'Peer', self.bgp.neighbor.peer_address.human()
			o = self.bgp.read_open()
			if self.debug and o: print "<-", o
			yield

			print 'Peer', self.bgp.neighbor.peer_address.human()
			c,_ = self.bgp.new_keepalive(force=True)
			if self.debug: print "->", 'KEEPALIVE'
			yield

			print 'Peer', self.bgp.neighbor.peer_address.human()
			msg,data = self.bgp.read_keepalive()
			if self.debug and msg == KeepAlive.TYPE: print "<- KEEPALIVE",self.bgp.network.host

			print 'Peer', self.bgp.neighbor.peer_address.human()
			a = self.bgp.new_announce()
			if self.debug and a: print '->', a

			while self.running:
				print 'Peer', self.bgp.neighbor.peer_address.human()
				c = self.bgp.check_keepalive()
				if self.debug: print "Receive Timer", self.bgp.network.host, ":", c, "second(s) left"

				c,k = self.bgp.new_keepalive()
				if self.debug and k: print "-> KEEPALIVE"
				if self.debug: print "Sending Timer", self.bgp.network.host, ":", c, "second(s) left"

				msg,data = self.bgp.read_message()
				if self.debug and msg == KeepAlive.TYPE: print "<- KEEPALIVE",self.bgp.network.host
				if self.debug and msg == Update.TYPE: print "<- UPDATE",self.bgp.network.host

#				u = self.bgp.new_update()
#				if self.debug and u: print "->", u

				yield 
			# User closing the connection
			raise SendNotification(6,0)
		except SendNotification,e:
			if self.debug: print "Sending notification (%d,%d) to peer" % (e.code,e.subcode)
			self.bgp.new_notification(e)
		except Notification, n:
			if self.debug: print "Notification Received"
			if self.debug: print str(n)
		except Failure, e:
			if self.debug: print "Failure Received", str(e)
		self.supervisor.unschedule(self.bgp.neighbor.peer_address.human())
		self.bgp.close()
	
	def shutdown (self):
		self.running = False
	
