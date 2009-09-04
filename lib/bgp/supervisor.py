#!/usr/bin/env python
# encoding: utf-8
"""
supervisor.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time
import signal

from bgp.data import Notification
from bgp.peer import Peer

class Supervisor (object):
	debug = True
	
	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = ''.join([chr(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a']])
	
	def __init__ (self,configuration):
		self.configuration = configuration
		self._peers = {}
		self._respawn = []
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
				for ip in self._peers.keys():
					print "peer",ip
					peer = self._peers[ip]
					peer.run()
				if self._shutdown:
					for ip in self._peers.keys():
						print "shutdown",ip
						self._peers[ip].stop()
				else:
					if self._reload:
						print "reload"
						self.reload()
					for peer in self._respawn:
						print "restart",ip
						peer.start()
					self._respawn = []
				# MUST not more than one KEEPALIVE / sec
				time.sleep(1.0)
			except KeyboardInterrupt:
				if self.debug: print "^C received"
				self.shutdown()
	
	def _add_peer (self,neighbor):
		peer = Peer(neighbor,self)
		self._peers[neighbor.peer_address.human()] = peer

	def reload (self):
		self._reload = False
		self.configuration.reload()
		for ip in self._peers.keys():
			print ip, [n.human() for n in self.configuration.neighbor]
			if ip not in [n.human() for n in self.configuration.neighbor]:
				self._peers[ip].stop()
		
		for _,neighbor in self.configuration.neighbor.iteritems():
			if neighbor.peer_address.human() not in self._peers:
				self._add_peer(neighbor)
		
	def shutdown (self):
		self._shutdown = True
	
	def unschedule (self,peer):
		del self._peers[peer.bgp.neighbor.peer_address.human()]
	
	def respawn (self,peer):
		self._respawn.append(peer)