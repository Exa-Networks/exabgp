# encoding: utf-8
"""
reactor.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os
import re
import sys
import time
import signal
import select

from collections import deque

from exabgp.reactor.daemon import Daemon
from exabgp.reactor.listener import Listener
from exabgp.reactor.listener import NetworkError
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.api.processes import ProcessError
from exabgp.reactor.peer import Peer
from exabgp.reactor.peer import ACTION
from exabgp.reactor.network.error import error

from exabgp.reactor.api.decoding import Decoder
from exabgp.configuration.file import Configuration
from exabgp.configuration.environment import environment

from exabgp.version import version
from exabgp.logger import Logger

class Reactor (object):
	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = ''.join([chr(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a']])

	def __init__ (self,configuration):
		self.ip = environment.settings().tcp.bind
		self.port = environment.settings().tcp.port
		self.respawn = environment.settings().api.respawn

		self.max_loop_time = environment.settings().reactor.speed

		self.logger = Logger()
		self.daemon = Daemon(self)
		self.processes = None
		self.listener = None
		self.configuration = Configuration(configuration)
		self.decoder = Decoder()

		self.peers = {}
		self.route_update = False

		self._shutdown = False
		self._reload = False
		self._reload_processes = False
		self._restart = False
		self._saved_pid = False
		self._pending = deque()
		self._running = None

		signal.signal(signal.SIGTERM, self.sigterm)
		signal.signal(signal.SIGHUP, self.sighup)
		signal.signal(signal.SIGALRM, self.sigalrm)
		signal.signal(signal.SIGUSR1, self.sigusr1)
		signal.signal(signal.SIGUSR2, self.sigusr2)

	def sigterm (self,signum, frame):
		self.logger.reactor("SIG TERM received - shutdown")
		self._shutdown = True

	def sighup (self,signum, frame):
		self.logger.reactor("SIG HUP received - shutdown")
		self._shutdown = True

	def sigalrm (self,signum, frame):
		self.logger.reactor("SIG ALRM received - restart")
		self._restart = True

	def sigusr1 (self,signum, frame):
		self.logger.reactor("SIG USR1 received - reload configuration")
		self._reload = True

	def sigusr2 (self,signum, frame):
		self.logger.reactor("SIG USR2 received - reload configuration and processes")
		self._reload = True
		self._reload_processes = True

	def ready (self,ios,sleeptime=0):
		sleeptime = max(0,sleeptime)
		if not ios:
			time.sleep(sleeptime)
			return []
		try:
			read,_,_ = select.select(ios,[],[],sleeptime)
			return read
		except select.error,e:
			errno,message = e.args
			if not errno in error.block:
				raise e
			return []

	def run (self):
		if self.ip:
			try:
				self.listener = Listener([self.ip,],self.port)
				self.listener.start()
			except NetworkError,e:
				self.listener = None
				if os.geteuid() != 0 and self.port <= 1024:
					self.logger.reactor("Can not bind to %s:%d, you may need to run ExaBGP as root" % (self.ip,self.port),'critical')
				else:
					self.logger.reactor("Can not bind to %s:%d (%s)" % (self.ip,self.port,str(e)),'critical')
				self.logger.reactor("unset exabgp.tcp.bind if you do not want listen for incoming connections",'critical')
				self.logger.reactor("and check that no other daemon is already binding to port %d" % self.port,'critical')
				sys.exit(1)
			self.logger.reactor("Listening for BGP session(s) on %s:%d" % (self.ip,self.port))

		if not self.daemon.drop_privileges():
			self.logger.reactor("Could not drop privileges to '%s' refusing to run as root" % self.daemon.user,'critical')
			self.logger.reactor("Set the environmemnt value exabgp.daemon.user to change the unprivileged user",'critical')
			return

		# This is required to make sure we can write in the log location as we now have dropped root privileges
		if not self.logger.restart():
			self.logger.reactor("Could not setup the logger, aborting",'critical')
			return

		self.daemon.daemonise()

		if not self.daemon.savepid():
			self.logger.reactor('could not update PID, not starting','error')

		# Make sure we create processes one we have dropped privileges and closed file descriptor
		self.processes = Processes(self)
		self.reload()

		# did we complete the run of updates caused by the last SIGUSR1/SIGUSR2 ?
		reload_completed = True

		wait = environment.settings().tcp.delay
		if wait:
			sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
			self.logger.reactor("waiting for %d seconds before connecting" % sleeptime)
			time.sleep(float(sleeptime))

		while True:
			try:
				while self.peers:
					start = time.time()
					end = start+self.max_loop_time

					if self._shutdown:
						self._shutdown = False
						self.shutdown()
					elif self._reload and reload_completed:
						self._reload = False
						self.reload(self._reload_processes)
						self._reload_processes = False
					elif self._restart:
						self._restart = False
						self.restart()
					elif self.route_update:
						self.route_update = False
						self.route_send()

					for key in self.peers.keys():
						peer = self.peers[key]

					ios = {}
					keys = set(self.peers.keys())

					while time.time() < end:
						for key in list(keys):
							peer = self.peers[key]
							action = peer.run()

							# .run() returns an ACTION enum:
							# * immediate if it wants to be called again
							# * later if it should be called again but has no work atm
							# * close if it is finished and is closing down, or restarting
							if action == ACTION.close:
								self.unschedule(peer)
								keys.discard(key)
							# we are loosing this peer, not point to schedule more process work
							elif action == ACTION.later:
								for io in peer.sockets():
									ios[io] = key
								# no need to come back to it before a a full cycle
								keys.discard(key)

						if not self.schedule() and not keys:
							ready = self.ready(ios.keys() + self.processes.fds(),end-time.time())
							for io in ready:
								if io in ios:
									keys.add(ios[io])
									del ios[io]

					if not keys:
						reload_completed = True

					# RFC state that we MUST not send more than one KEEPALIVE / sec
					# And doing less could cause the session to drop

					if self.listener:
						for connection in self.listener.connected():
							# found
							# * False, not peer found for this TCP connection
							# * True, peer found
							# * None, conflict found for this TCP connections
							found = False
							for key in self.peers:
								peer = self.peers[key]
								neighbor = peer.neighbor
								# XXX: FIXME: Inet can only be compared to Inet
								if connection.local == str(neighbor.peer_address) and connection.peer == str(neighbor.local_address):
									if peer.incoming(connection):
										found = True
										break
									found = None
									break

							if found:
								self.logger.reactor("accepted connection from  %s - %s" % (connection.local,connection.peer))
							elif found is False:
								self.logger.reactor("no session configured for  %s - %s" % (connection.local,connection.peer))
								connection.notification(6,3,'no session configured for the peer')
								connection.close()
							elif found is None:
								self.logger.reactor("connection refused (already connected to the peer) %s - %s" % (connection.local,connection.peer))
								connection.notification(6,5,'could not accept the connection')
								connection.close()

				self.processes.terminate()
				self.daemon.removepid()
				break
			except KeyboardInterrupt:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("^C received")
						break
					except KeyboardInterrupt:
						pass
			except SystemExit:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("exiting")
						break
					except KeyboardInterrupt:
						pass
			except IOError:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("I/O Error received, most likely ^C during IO",'warning')
						break
					except KeyboardInterrupt:
						pass
			except ProcessError:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("Problem when sending message(s) to helper program, stopping",'error')
						break
					except KeyboardInterrupt:
						pass
			except select.error,e:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor("problem using select, stopping",'error')
						break
					except KeyboardInterrupt:
						pass
#				from exabgp.leak import objgraph
#				print objgraph.show_most_common_types(limit=20)
#				import random
#				obj = objgraph.by_type('Route')[random.randint(0,2000)]
#				objgraph.show_backrefs([obj], max_depth=10)

	def shutdown (self):
		"""terminate all the current BGP connections"""
		self.logger.reactor("Performing shutdown")
		if self.listener:
			self.listener.stop()
		for key in self.peers.keys():
			self.peers[key].stop()

	def reload (self,restart=False):
		"""reload the configuration and send to the peer the route which changed"""
		self.logger.reactor("Performing reload of exabgp %s" % version)

		reloaded = self.configuration.reload()

		if not reloaded:
			self.logger.configuration("Problem with the configuration file, no change done",'error')
			self.logger.configuration(self.configuration.error,'error')
			return

		for key, peer in self.peers.items():
			if key not in self.configuration.neighbor:
				self.logger.reactor("Removing Peer %s" % peer.neighbor.name())
				peer.stop()

		for key, neighbor in self.configuration.neighbor.items():
			# new peer
			if key not in self.peers:
				self.logger.reactor("New Peer %s" % neighbor.name())
				peer = Peer(neighbor,self)
				self.peers[key] = peer
			# modified peer
			elif self.peers[key].neighbor != neighbor:
				self.logger.reactor("Peer definition change, restarting %s" % str(key))
				self.peers[key].restart(neighbor)
			# same peer but perhaps not the routes
			else:
				# finding what route changed and sending the delta is not obvious
				# self.peers[key].send_new(neighbor.rib.outgoing.queued_changes())
				self.logger.reactor("restarting %s" % str(key))
				self.peers[key].restart(neighbor)
		self.logger.configuration("Loaded new configuration successfully",'warning')
		# This only starts once ...
		self.processes.start(restart)

	def schedule (self):
		try:
			# read at least on message per process if there is some and parse it
			for service,command in self.processes.received():
				self.decoder.parse_command(self,service,command)

			# if we have nothing to do, return or save the work
			if not self._running:
				if not self._pending:
					return False
				self._running = self._pending.popleft()

			# run it
			try:
				self._running.next()  # run
				# should raise StopIteration in most case
					# and prevent us to have to run twice to run one command
				self._running.next()  # run
			except StopIteration:
				self._running = None
			return True

		except StopIteration:
			pass
		except KeyboardInterrupt:
			self._shutdown = True
			self.logger.reactor("^C received",'error')


	def route_send (self):
		"""the process ran and we need to figure what routes to changes"""
		self.logger.reactor("Performing dynamic route update")
		for key in self.configuration.neighbor.keys():
			self.peers[key].send_new()
		self.logger.reactor("Updated peers dynamic routes successfully")

	def route_flush (self):
		"""we just want to flush any unflushed routes"""
		self.logger.reactor("Performing route flush")
		for key in self.configuration.neighbor.keys():
			self.peers[key].send_new(update=True)

	def restart (self):
		"""kill the BGP session and restart it"""
		self.logger.reactor("Performing restart of exabgp %s" % version)
		self.configuration.reload()

		for key in self.peers.keys():
			if key not in self.configuration.neighbor.keys():
				neighbor = self.configuration.neighbor[key]
				self.logger.reactor("Removing Peer %s" % neighbor.name())
				self.peers[key].stop()
			else:
				self.peers[key].restart()
		self.processes.terminate()
		self.processes.start()

	def unschedule (self,peer):
		key = peer.neighbor.name()
		if key in self.peers:
			del self.peers[key]

	def answer (self,service,string):
		self.processes.write(service,string)
		self.logger.reactor('Responding to %s : %s' % (service,string))

	def api_shutdown (self):
		self._shutdown = True
		self._pending = deque()
		self._running = None

	def api_reload (self):
		self._reload = True
		self._pending = deque()
		self._running = None

	def api_restart (self):
		self._restart = True
		self._pending = deque()
		self._running = None

	@staticmethod
	def match_neighbor (description,name):
		for string in description:
			if re.search('(^|[\s])%s($|[\s,])' % re.escape(string), name) is None:
				return False
		return True

	def match_neighbors (self,descriptions):
		"returns the sublist of peers matching the description passed, or None if no description is given"
		if not descriptions:
			return self.peers.keys()

		returned = []
		for key in self.peers:
			for description in descriptions:
				if Reactor.match_neighbor(description,key):
					if key not in returned:
						returned.append(key)
		return returned

	def nexthops (self,peers):
		return dict((peer,self.peers[peer].neighbor.local_address) for peer in peers)

	def plan (self,callback):
		self._pending.append(callback)
