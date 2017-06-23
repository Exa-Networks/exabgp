# encoding: utf-8
"""
reactor/loop.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import re
import copy
import time
import signal
import select
import socket

from collections import deque
from exabgp.vendoring import six

from exabgp.util import character
from exabgp.util import concat_bytes_i

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
	clear = concat_bytes_i(character(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a'])

	def __init__ (self, configurations):
		self.ips = environment.settings().tcp.bind
		self.port = environment.settings().tcp.port
		self.ack = environment.settings().api.ack

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

		self._stopping = environment.settings().tcp.once
		self._shutdown = False
		self._reload = False
		self._reload_processes = False
		self._restart = False
		self._saved_pid = False
		self._running = None
		self._pending = deque()
		self._async = deque()

		self._signal = {}

		signal.signal(signal.SIGTERM, self.sigterm)
		signal.signal(signal.SIGHUP, self.sighup)
		signal.signal(signal.SIGALRM, self.sigalrm)
		signal.signal(signal.SIGUSR1, self.sigusr1)
		signal.signal(signal.SIGUSR2, self.sigusr2)

	def _termination (self,reason):
		while True:
			try:
				self._shutdown = True
				self.logger.reactor(reason,'warning')
				break
			except KeyboardInterrupt:
				pass

	def sigterm (self, signum, frame):
		self.logger.reactor('SIG TERM received - shutdown')
		self._shutdown = True
		for key in self.peers:
			if self.peers[key].neighbor.api['signal']:
				self._signal[key] = signum

	def sighup (self, signum, frame):
		self.logger.reactor('SIG HUP received - shutdown')
		self._shutdown = True
		for key in self.peers:
			if self.peers[key].neighbor.api['signal']:
				self._signal[key] = signum

	def sigalrm (self, signum, frame):
		self.logger.reactor('SIG ALRM received - restart')
		self._restart = True
		for key in self.peers:
			if self.peers[key].neighbor.api['signal']:
				self._signal[key] = signum

	def sigusr1 (self, signum, frame):
		self.logger.reactor('SIG USR1 received - reload configuration')
		self._reload = True
		for key in self.peers:
			if self.peers[key].neighbor.api['signal']:
				self._signal[key] = signum

	def sigusr2 (self, signum, frame):
		self.logger.reactor('SIG USR2 received - reload configuration and processes')
		self._reload = True
		self._reload_processes = True
		for key in self.peers:
			if self.peers[key].neighbor.api['signal']:
				self._signal[key] = signum

	def _api_ready (self,sockets):
		sleeptime = self.max_loop_time / 20
		fds = self.processes.fds()
		ios = fds + sockets
		try:
			read,_,_ = select.select(ios,[],[],sleeptime)
			for fd in fds:
				if fd in read:
					read.remove(fd)
			return read
		except select.error as exc:
			errno,message = exc.args  # pylint: disable=W0633
			if errno not in error.block:
				raise exc
			return []
		except socket.error as exc:
			# python 3 does not raise on closed FD, but python2 does
			# we have lost a peer and it is causing the select
			# to complain, the code will self-heal, ignore the issue
			# (EBADF from python2 must be ignored if when checkign error.fatal)
			# otherwise sending  notification causes TCP to drop and cause
			# this code to kill ExaBGP
			return []
		except ValueError as exc:
			# The peer closing the TCP connection lead to a negative file descritor
			return []
		except KeyboardInterrupt:
			self._termination('^C received')
			return []

	def _setup_listener (self, local_addr, remote_addr, port, md5_password, md5_base64, ttl_in):
		try:
			if not self.listener:
				self.listener = Listener()
			if not remote_addr:
				remote_addr = IP.create('0.0.0.0') if local_addr.ipv4() else IP.create('::')
			self.listener.listen(local_addr, remote_addr, port, md5_password, md5_base64, ttl_in)
			self.logger.reactor('Listening for BGP session(s) on %s:%d%s' % (local_addr, port,' with MD5' if md5_password else ''))
			return True
		except NetworkError as exc:
			if os.geteuid() != 0 and port <= 1024:
				self.logger.reactor('Can not bind to %s:%d, you may need to run ExaBGP as root' % (local_addr, port),'critical')
			else:
				self.logger.reactor('Can not bind to %s:%d (%s)' % (local_addr, port,str(exc)),'critical')
			self.logger.reactor('unset exabgp.tcp.bind if you do not want listen for incoming connections','critical')
			self.logger.reactor('and check that no other daemon is already binding to port %d' % port,'critical')
			return False

	def _handle_listener (self):
		if not self.listener:
			return

		ranged_neighbor = []

		for connection in self.listener.connected():
			for key in self.peers:
				peer = self.peers[key]
				neighbor = peer.neighbor

				connection_local = IP.create(connection.local).address()
				neighbor_peer_start = neighbor.peer_address.address()
				neighbor_peer_next = neighbor_peer_start + neighbor.range_size

				if not neighbor_peer_start <= connection_local < neighbor_peer_next:
					continue

				connection_peer = IP.create(connection.peer).address()
				neighbor_local = neighbor.local_address.address()

				if connection_peer != neighbor_local:
					if not neighbor.auto_discovery:
						continue

				# we found a range matching for this connection
				# but the peer may already have connected, so
				# we need to iterate all individual peers before
				# handling "range" peers
				if neighbor.range_size > 1:
					ranged_neighbor.append(peer.neighbor)
					continue

				denied = peer.handle_connection(connection)
				if denied:
					self.logger.reactor('refused connection from %s due to the state machine' % connection.name())
					self._async.append(denied)
					break
				self.logger.reactor('accepted connection from %s' % connection.name())
				break
			else:
				# we did not break (and nothign was found/done or we have group match)
				matched = len(ranged_neighbor)
				if matched > 1:
					self.logger.reactor('could not accept connection from %s (more than one neighbor match)' % connection.name())
					self._async.append(connection.notification(6,5,b'could not accept the connection (more than one neighbor match)'))
					return
				if not matched:
					self.logger.reactor('no session configured for %s' % connection.name())
					self._async.append(connection.notification(6,3,b'no session configured for the peer'))
					return

				new_neighbor = copy.copy(ranged_neighbor[0])
				new_neighbor.range_size = 1
				new_neighbor.generated = True
				new_neighbor.local_address = IP.create(connection.peer)
				new_neighbor.peer_address = IP.create(connection.local)

				new_peer = Peer(new_neighbor,self)
				denied = new_peer.handle_connection(connection)
				if denied:
					self.logger.reactor('refused connection from %s due to the state machine' % connection.name())
					self._async.append(denied)
					return

				self.peers[new_neighbor.name()] = new_peer
				return

	def run (self, validate):
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
		for ip in self.ips:
			if not self._setup_listener(ip, None, self.port, None, False, None):
				return False

		if not self.load():
			return False

		if validate:  # only validate configuration
			self.logger.configuration('')
			self.logger.configuration('Parsed Neighbors, un-templated')
			self.logger.configuration('------------------------------')
			self.logger.configuration('')
			for key in self.peers:
				self.logger.configuration(str(self.peers[key].neighbor))
				self.logger.configuration('')
			return True

		for neighbor in self.configuration.neighbors.values():
			if neighbor.listen:
				if not self._setup_listener(neighbor.md5_ip, neighbor.peer_address, neighbor.listen, neighbor.md5_password, neighbor.md5_base64, neighbor.ttl_in):
					return False

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
			return

		# did we complete the run of updates caused by the last SIGUSR1/SIGUSR2 ?
		reload_completed = True

		wait = environment.settings().tcp.delay
		if wait:
			sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
			self.logger.reactor('waiting for %d seconds before connecting' % sleeptime)
			time.sleep(float(sleeptime))

		workers = {}
		peers = set()
		busy = False

		while True:
			try:
				start = time.time()
				end = start + self.max_loop_time

				if self._shutdown:
					self._shutdown = False
					self.shutdown()
					break

				if self._reload and reload_completed:
					self._reload = False
					self.load()
					self.processes.start(self._reload_processes)
					self._reload_processes = False
				elif self._restart:
					self._restart = False
					self.restart()

				# We got some API routes to announce
				if self.route_update:
					self.route_update = False
					self.route_send()

				for key,peer in self.peers.items():
					if not peer.neighbor.passive or peer.proto:
						peers.add(key)
					if key in self._signal:
						self.peers[key].reactor.processes.signal(self.peers[key].neighbor,self._signal[key])
				self._signal = {}

				# check all incoming connection
				self._handle_listener()

				# give a turn to all the peers
				while start < time.time() < end:
					for key in list(peers):
						peer = self.peers[key]
						action = peer.run()

						# .run() returns an ACTION enum:
						# * immediate if it wants to be called again
						# * later if it should be called again but has no work atm
						# * close if it is finished and is closing down, or restarting
						if action == ACTION.CLOSE:
							self._unschedule(key)
							peers.discard(key)
						# we are loosing this peer, not point to schedule more process work
						elif action == ACTION.LATER:
							for io in peer.sockets():
								workers[io] = key
							# no need to come back to it before a a full cycle
							peers.discard(key)

					# handle API calls
					busy  = self._scheduled_api()
					# handle new connections
					busy |= self._scheduled_listener()

					if not peers and not busy:
						break

				if not peers:
					reload_completed = True

				for io in self._api_ready(list(workers)):
					peers.add(workers[io])
					del workers[io]

				if self._stopping and not self.peers.keys():
					break

			except KeyboardInterrupt:
				self._termination('^C received')
			# socket.error is a subclass of IOError (so catch it first)
			except socket.error:
				self._termination('socket error received')
			except IOError:
				self._termination('I/O Error received, most likely ^C during IO')
			except SystemExit:
				self._termination('exiting')
			except ProcessError:
				self._termination('Problem when sending message(s) to helper program, stopping')
			except select.error:
				self._termination('problem using select, stopping')

	def shutdown (self):
		"""terminate all the current BGP connections"""
		self.logger.reactor('performing shutdown')
		if self.listener:
			self.listener.stop()
			self.listener = None
		for key in self.peers.keys():
			self.peers[key].stop()
		self.processes.terminate()
		self.daemon.removepid()
		self._stopping = True

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
			for ip in self.ips:
				if ip.afi == neighbor.peer_address.afi:
					self._setup_listener(ip, neighbor.peer_address, self.port, neighbor.md5_password, neighbor.md5_base64, None)
		self.logger.configuration('loaded new configuration successfully','info')

		return True

	def _scheduled_listener (self, flipflop=[]):
		try:
			for generator in self._async:
				try:
					six.next(generator)
					six.next(generator)
					flipflop.append(generator)
				except StopIteration:
					pass
			self._async, flipflop = flipflop, self._async
			return len(self._async) > 0
		except KeyboardInterrupt:
			self._termination('^C received')
			return False

	def _scheduled_api (self):
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
					six.next(self._running)  # run
					# should raise StopIteration in most case
					# and prevent us to have to run twice to run one command
					six.next(self._running)  # run
				except StopIteration:
					self._running = None
					self.logger.reactor('callback | removing')
				return True
			return False

		except KeyboardInterrupt:
			self._termination('^C received')
			return False

	def route_send (self):
		"""the process ran and we need to figure what routes to changes"""
		self.logger.reactor('performing dynamic route update')
		for key in self.configuration.neighbors.keys():
			self.peers[key].send_new()
		self.logger.reactor('updated peers dynamic routes successfully')

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

	def _unschedule (self, peer):
		if peer in self.peers:
			del self.peers[peer]

	def answer (self, service, string):
		if self.ack:
			self.always_answer(service,string)

	def always_answer (self, service, string):
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
			if re.search(r'(^|\s)%s($|\s|,)' % re.escape(string), name) is None:
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
