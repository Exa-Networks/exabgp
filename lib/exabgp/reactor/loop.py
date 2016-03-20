# encoding: utf-8
"""
reactor/loop.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import re
import sys
import time
import signal
import select

from collections import deque

from exabgp.protocol.ip import IP

from exabgp.reactor.daemon import Daemon
from exabgp.reactor.listener import Listener
from exabgp.reactor.listener import NetworkError
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.api.processes import ProcessError
from exabgp.reactor.peer import Peer
from exabgp.reactor.peer import ACTION
from exabgp.reactor.network.error import error

from exabgp.reactor.api.api import API
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.environment import environment

from exabgp.version import version
from exabgp.logger import Logger


class Reactor (object):
	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = ''.join([chr(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a']])

	def __init__ (self, configurations):
		self.ip = environment.settings().tcp.bind
		self.port = environment.settings().tcp.port
		self.respawn = environment.settings().api.respawn

		self.max_loop_time = environment.settings().reactor.speed
		self.early_drop = environment.settings().daemon.drop

		self.logger = Logger()
		self.daemon = Daemon(self)
		self.processes = None
		self.listener = None
		self.configuration = Configuration(configurations)
		self.api = API(self)

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

	def sigterm (self, signum, frame):
		self.logger.reactor('SIG TERM received - shutdown')
		self._shutdown = True

	def sighup (self, signum, frame):
		self.logger.reactor('SIG HUP received - shutdown')
		self._shutdown = True

	def sigalrm (self, signum, frame):
		self.logger.reactor('SIG ALRM received - restart')
		self._restart = True

	def sigusr1 (self, signum, frame):
		self.logger.reactor('SIG USR1 received - reload configuration')
		self._reload = True

	def sigusr2 (self, signum, frame):
		self.logger.reactor('SIG USR2 received - reload configuration and processes')
		self._reload = True
		self._reload_processes = True

	def ready (self, ios, sleeptime=0):
		# never sleep a negative number of second (if the rounding is negative somewhere)
		# never sleep more than one second (should the clock time change during two time.time calls)
		sleeptime = min(max(0.0,sleeptime),1.0)
		if not ios:
			time.sleep(sleeptime)
			return []
		try:
			read,_,_ = select.select(ios,[],[],sleeptime)
			return read
		except select.error,exc:
			errno,message = exc.args  # pylint: disable=W0633
			if errno not in error.block:
				raise exc
			return []

	def run (self):
		self.daemon.daemonise()

		# Make sure we create processes once we have closed file descriptor
		# unfortunately, this must be done before reading the configuration file
		# so we can not do it with dropped privileges
		self.processes = Processes(self)

		# we have to read the configuration possibly with root privileges
		# as we need the MD5 information when we bind, and root is needed
		# to bind to a port < 1024

		# this is undesirable as :
		# - handling user generated data as root should be avoided
		# - we may not be able to reload the configuration once the privileges are dropped

		# but I can not see any way to avoid it

		if not self.load():
			return False

		try:
			self.listener = Listener()

			if self.ip:
				self.listener.listen(IP.create(self.ip),IP.create('0.0.0.0'),self.port,None,None)
				self.logger.reactor('Listening for BGP session(s) on %s:%d' % (self.ip,self.port))

			for neighbor in self.configuration.neighbors.values():
				if neighbor.listen:
					self.listener.listen(neighbor.md5_ip,neighbor.peer_address,neighbor.listen,neighbor.md5_password,neighbor.ttl_in)
					self.logger.reactor('Listening for BGP session(s) on %s:%d%s' % (neighbor.md5_ip,neighbor.listen,' with MD5' if neighbor.md5_password else ''))
		except NetworkError,exc:
			self.listener = None
			if os.geteuid() != 0 and self.port <= 1024:
				self.logger.reactor('Can not bind to %s:%d, you may need to run ExaBGP as root' % (self.ip,self.port),'critical')
			else:
				self.logger.reactor('Can not bind to %s:%d (%s)' % (self.ip,self.port,str(exc)),'critical')
			self.logger.reactor('unset exabgp.tcp.bind if you do not want listen for incoming connections','critical')
			self.logger.reactor('and check that no other daemon is already binding to port %d' % self.port,'critical')
			sys.exit(1)

		if not self.early_drop:
			self.processes.start()

		if not self.daemon.drop_privileges():
			self.logger.reactor('Could not drop privileges to \'%s\' refusing to run as root' % self.daemon.user,'critical')
			self.logger.reactor('Set the environmemnt value exabgp.daemon.user to change the unprivileged user','critical')
			return

		if self.early_drop:
			self.processes.start()

		# This is required to make sure we can write in the log location as we now have dropped root privileges
		if not self.logger.restart():
			self.logger.reactor('Could not setup the logger, aborting','critical')
			return

		if not self.daemon.savepid():
			self.logger.reactor('could not update PID, not starting','error')

		# did we complete the run of updates caused by the last SIGUSR1/SIGUSR2 ?
		reload_completed = True

		wait = environment.settings().tcp.delay
		if wait:
			sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
			self.logger.reactor('waiting for %d seconds before connecting' % sleeptime)
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
						self.load()
						self.processes.start(self._reload_processes)
						self._reload_processes = False
					elif self._restart:
						self._restart = False
						self.restart()
					elif self.route_update:
						self.route_update = False
						self.route_send()

					ios = {}
					keys = set(self.peers.keys())

					while start < time.time() < end:
						for key in list(keys):
							peer = self.peers[key]
							action = peer.run()

							# .run() returns an ACTION enum:
							# * immediate if it wants to be called again
							# * later if it should be called again but has no work atm
							# * close if it is finished and is closing down, or restarting
							if action == ACTION.CLOSE:
								self.unschedule(peer)
								keys.discard(key)
							# we are loosing this peer, not point to schedule more process work
							elif action == ACTION.LATER:
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
								self.logger.reactor('accepted connection from  %s - %s' % (connection.local,connection.peer))
							elif found is False:
								self.logger.reactor('no session configured for  %s - %s' % (connection.local,connection.peer))
								connection.notification(6,3,'no session configured for the peer')
								connection.close()
							elif found is None:
								self.logger.reactor('connection refused (already connected to the peer) %s - %s' % (connection.local,connection.peer))
								connection.notification(6,5,'could not accept the connection')
								connection.close()

				self.processes.terminate()
				self.daemon.removepid()
				break
			except KeyboardInterrupt:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor('^C received')
						break
					except KeyboardInterrupt:
						pass
			except SystemExit:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor('exiting')
						break
					except KeyboardInterrupt:
						pass
			except IOError:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor('I/O Error received, most likely ^C during IO','warning')
						break
					except KeyboardInterrupt:
						pass
			except ProcessError:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor('Problem when sending message(s) to helper program, stopping','error')
						break
					except KeyboardInterrupt:
						pass
			except select.error:
				while True:
					try:
						self._shutdown = True
						self.logger.reactor('problem using select, stopping','error')
						break
					except KeyboardInterrupt:
						pass
				# from exabgp.leak import objgraph
				# print objgraph.show_most_common_types(limit=20)
				# import random
				# obj = objgraph.by_type('Route')[random.randint(0,2000)]
				# objgraph.show_backrefs([obj], max_depth=10)

	def shutdown (self):
		"""terminate all the current BGP connections"""
		self.logger.reactor('performing shutdown')
		if self.listener:
			self.listener.stop()
			self.listener = None
		for key in self.peers.keys():
			self.peers[key].stop()

	def load (self):
		"""reload the configuration and send to the peer the route which changed"""
		self.logger.reactor('performing reload of exabgp %s' % version)

		reloaded = self.configuration.reload()

		if not reloaded:
			#
			# Careful the string below is used but the QA code to check for sucess of failure
			self.logger.configuration('problem with the configuration file, no change done','error')
			# Careful the string above is used but the QA code to check for sucess of failure
			#
			self.logger.configuration(str(self.configuration.error),'error')
			return False

		for key, peer in self.peers.items():
			if key not in self.configuration.neighbors:
				self.logger.reactor('removing peer: %s' % peer.neighbor.name())
				peer.stop()

		for key, neighbor in self.configuration.neighbors.items():
			# new peer
			if key not in self.peers:
				self.logger.reactor('new peer: %s' % neighbor.name())
				peer = Peer(neighbor,self)
				self.peers[key] = peer
			# modified peer
			elif self.peers[key].neighbor != neighbor:
				self.logger.reactor('peer definition change, establishing a new connection for %s' % str(key))
				self.peers[key].reestablish(neighbor)
			# same peer but perhaps not the routes
			else:
				# finding what route changed and sending the delta is not obvious
				self.logger.reactor('peer definition identical, updating peer routes if required for %s' % str(key))
				self.peers[key].reconfigure(neighbor)
		self.logger.configuration('loaded new configuration successfully','warning')

		return True

	def schedule (self):
		try:
			# read at least on message per process if there is some and parse it
			for service,command in self.processes.received():
				self.api.text(self,service,command)

			# if we have nothing to do, return or save the work
			if not self._running:
				if not self._pending:
					return False
				self._running,name = self._pending.popleft()
				self.logger.reactor('callback | installing %s' % name)

			if self._running:
				# run it
				try:
					self.logger.reactor('callback | running')
					self._running.next()  # run
					# should raise StopIteration in most case
					# and prevent us to have to run twice to run one command
					self._running.next()  # run
				except StopIteration:
					self._running = None
					self.logger.reactor('callback | removing')
				return True

		except StopIteration:
			pass
		except KeyboardInterrupt:
			self._shutdown = True
			self.logger.reactor('^C received','error')

	def route_send (self):
		"""the process ran and we need to figure what routes to changes"""
		self.logger.reactor('performing dynamic route update')
		for key in self.configuration.neighbors.keys():
			self.peers[key].send_new()
		self.logger.reactor('updated peers dynamic routes successfully')

	def route_flush (self):
		"""we just want to flush any unflushed routes"""
		self.logger.reactor('performing route flush')
		for key in self.configuration.neighbors.keys():
			self.peers[key].send_new(update=True)

	def restart (self):
		"""kill the BGP session and restart it"""
		self.logger.reactor('performing restart of exabgp %s' % version)
		self.configuration.reload()

		for key in self.peers.keys():
			if key not in self.configuration.neighbors.keys():
				neighbor = self.configuration.neighbors[key]
				self.logger.reactor('removing Peer %s' % neighbor.name())
				self.peers[key].stop()
			else:
				self.peers[key].reestablish()
		self.processes.terminate()
		self.processes.start()

	def unschedule (self, peer):
		key = peer.neighbor.name()
		if key in self.peers:
			del self.peers[key]

	def answer (self, service, string):
		self.processes.write(service,string)
		self.logger.reactor('responding to %s : %s' % (service,string.replace('\n','\\n')))

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
	def match_neighbor (description, name):
		for string in description:
			if re.search(r'(^|[\s])%s($|[\s,])' % re.escape(string), name) is None:
				return False
		return True

	def match_neighbors (self, descriptions):
		"""return the sublist of peers matching the description passed, or None if no description is given"""
		if not descriptions:
			return self.peers.keys()

		returned = []
		for key in self.peers:
			for description in descriptions:
				if Reactor.match_neighbor(description,key):
					if key not in returned:
						returned.append(key)
		return returned

	def nexthops (self, peers):
		return dict((peer,self.peers[peer].neighbor.local_address) for peer in peers)

	def plan (self, callback,name):
		self._pending.append((callback,name))
