#!/usr/bin/env python
# encoding: utf-8
"""
supervisor.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time
import signal

from bgp.utils                import *
from bgp.message.notification import Notification
from bgp.network.peer         import Peer

class Supervisor (object):
	debug = True

	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = ''.join([chr(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a']])

	def __init__ (self,configuration):
		self.log = Log('Supervisor','')
		self.configuration = configuration
		self._peers = {}
		self._shutdown = False
		self._reload = False
		self._restart = False
		self.reload()

		signal.signal(signal.SIGTERM, self.sigterm)
		signal.signal(signal.SIGHUP, self.sighup)
		signal.signal(signal.SIGALRM, self.sigalrm)

	def sigterm (self,signum, frame):
		self.log.out("SIG TERM received")
		self._shutdown = True

	def sighup (self,signum, frame):
		self.log.out("SIG HUP received")
		self._reload = True

	def sigalrm (self,signum, frame):
		self.log.out("SIG ALRM received")
		self._restart = True

	def run (self):
		start = time.time()
		while self._peers:
			try:
				if self._shutdown:
					self.shutdown()
				elif self._reload:
					self.reload()
				elif self._restart:
					self.restart()

				# Handle all connection
				for ip in self._peers.keys():
					peer = self._peers[ip]
					peer.run()

				# RFC state that we MUST not more than one KEEPALIVE / sec
				time.sleep(1.0)
			except KeyboardInterrupt:
				if self.debug: self.log.out("^C received")
				self._shutdown = True

	def shutdown (self):
		"""terminate all the current BGP connections"""
		self.log.out("performing shutdown")
		for ip in self._peers.keys():
			self._peers[ip].shutdown()

	def reload (self):
		"""reload the configuration and send to the peer the route which changed"""
		self.log.out("performing reload")
		self._reload = False
		self.configuration.reload()

		for ip in self._peers.keys():
			if ip not in self.configuration.neighbor.keys():
				self.log.out("Removing Peer %s" % str(ip))
				self._peers[ip].shutdown()

		for ip in self.configuration.neighbor.keys():
			neighbor = self.configuration.neighbor[ip]
			if ip not in self._peers.keys():
				self.log.out("New Peer %s" % str(ip))
				peer = Peer(neighbor,self)
				self._peers[ip] = peer
			else:
				# check if the neighbor definition are the same (BUT NOT THE ROUTES)
				if self._peers[ip].neighbor != neighbor:
					self.log.out("Peer definition change, restarting %s" % str(ip))
					self._peers[ip].restart()
				# set the new neighbor with the new routes
				self._peers[ip].neighbor = neighbor

	def restart (self):
		"""kill the BGP session and restart it"""
		self.log.out("performing restart")
		self._restart = False
		self.configuration.reload()

		for ip in self._peers.keys():
			if ip not in self.configuration.neighbor.keys():
				self.log.out("Removing Peer %s" % str(ip))
				self._peers[ip].stop()
			else:
				self._peers[ip].restart()

	def unschedule (self,peer):
		ip = peer.neighbor.peer_address.ip()
		if ip in self._peers:
			del self._peers[ip]
