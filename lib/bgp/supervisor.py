#!/usr/bin/env python
# encoding: utf-8
"""
supervisor.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time
import signal

from bgp.message import Notification
from bgp.peer import Peer

class Supervisor (object):
	debug = True
	
	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = ''.join([chr(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a']])
	
	def __init__ (self,configuration):
		self.configuration = configuration
		self._peers = {}
		self._shutdown = False
		self._reload = False
		self.reload()
		
		signal.signal(signal.SIGTERM, self.sigterm)
		signal.signal(signal.SIGHUP, self.sighup)
	
	def sigterm (self,signum, frame):
		print "SIG TERM received"
		self.shutdown()

	def sighup (self,signum, frame):
		print "SIG HUP received"
		self._reload = True
	
	def run (self):
		start = time.time()
		while self._peers:
			try:
				if self._shutdown:
					for ip in self._peers.keys():
						self._peers[ip].shutdown()
				else:
					if self._reload:
						self.reload()
				
				# Handle all connection
				for ip in self._peers.keys():
					peer = self._peers[ip]
					peer.run()
				
				# MUST not more than one KEEPALIVE / sec
				time.sleep(1.0)
			except KeyboardInterrupt:
				if self.debug: print "^C received"
				self.shutdown()

	def reload (self):
		self._reload = False
		self.configuration.reload()
		for ip in self._peers.keys():
			if ip not in [n.human() for n in self.configuration.neighbor]:
				print "Removing Peer", ip
				self._peers[ip].shutdown()
		
		for _,neighbor in self.configuration.neighbor.iteritems():
			# XXX: we should really use .human() for the key everywhere
			ip = neighbor.peer_address.human()
			if ip not in self._peers:
				print "New neighbor ", ip 
				peer = Peer(neighbor,self)
				self._peers[ip] = peer
			else:
				if self._peers[ip].neighbor != neighbor:
					self._peers[ip].stop()
	
	def shutdown (self):
		self._shutdown = True
	
	def unschedule (self,peer):
		ip = peer.neighbor.peer_address.human()
		if ip in self._peers:
			del self._peers[ip]
	