#!/usr/bin/env python
# encoding: utf-8
"""
supervisor.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time
from bgp.data import Notification
from bgp.protocol import Protocol,Network
from bgp.peer import Peer

class Supervisor (object):
	debug = True
	
	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = ''.join([chr(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a']])
	
	def __init__ (self,configuration):
		self.configuration = configuration
		self._peers = {}
		self._shutdown = False
		self.reload()
		
	def run (self):
		start = time.time()
		while self._peers:
			try:
				for ip in self._peers:
					peer = self._peers[ip]
					peer.run()
				if self._shutdown:
					for ip in self._peers:
						self._peer[ip].shutdown()
				# MUST not more than one KEEPALIVE / sec
				time.sleep(1.0)
			except KeyboardInterrupt:
				if self.debug: print "^C received"
				self.shutdown()
	
	def _add_peer (self,neighbor):
		ip = neighbor.peer_address.human()
		assert ip not in self._peers
		network = Network(ip)
		peer = Peer(Protocol(neighbor,network),self)
		self._peers[ip] = peer

	def reload (self):
		self.configuration.reload()
		for ip in self._peers.keys():
			if ip not in self.configuration.neighbor:
				self._peers[ip].shutdown()
		
		for _,neighbor in self.configuration.neighbor.iteritems():
			ip = neighbor.peer_address.human()
			if ip in self._peers:
				continue
			self._add_peer(neighbor)
		
	def shutdown (self):
		self._shutdown = True
	
	def unschedule (self,ip):
		del self._peers[ip]