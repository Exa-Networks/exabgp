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
		self._neighbor = []
		self._neighbor_to_peer = {}
		
		self.reload()
		
	def run (self):
		start = time.time()
		while self._neighbor:
			try:
				for ip in self._neighbor:
					peer = self._neighbor_to_peer[ip]
					peer.run()
				time.sleep(1)
			except KeyboardInterrupt:
				if self.debug: print "^C received"
				self.shutdown()
	
	def remove_neighbor (self,neighbor):
		ip = neighbor.peer_address.human()
		peer = self._neighbor_to_peer[ip]
		peer.shutdown()
	
	def remove_peer (self,neighbor):
		ip = neighbor.peer_address.human()
		self._neighbor.remove(ip)
		del self._neighbor_to_peer[ip]

	def _add_peer (self,neighbor):
		ip = neighbor.peer_address.human()
		if ip in self._neighbor:
			return
		network = Network(ip)
		peer = Peer(Protocol(neighbor,network),self)
		self._neighbor.append(ip)
		self._neighbor_to_peer[ip] = peer

	def reload (self):
		self.configuration.reload()
		for ip in self._neighbor:
			if ip not in self.configuration.neighbor.keys():
				print "IP", ip
				self.remove_neighbor(ip)
		
		for _,neighbor in self.configuration.neighbor.iteritems():
			ip = neighbor.peer_address.human()
			if ip in self._neighbor:
				continue
			self._add_peer(neighbor)
		
	def shutdown (self):
		for ip in self._neighbor:
			peer = self._neighbor_to_peer[ip]
			peer.shutdown()
		
	def unschedule (self,ip):
		self._neighbor.remove(ip)