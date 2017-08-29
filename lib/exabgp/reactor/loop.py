# encoding: utf-8
"""
reactor/loop.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import time
import uuid
import select
import socket

from exabgp.util import character
from exabgp.util import concat_bytes_i

from exabgp.reactor.daemon import Daemon
from exabgp.reactor.listener import Listener
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.api.processes import ProcessError
from exabgp.reactor.peer import Peer
from exabgp.reactor.peer import ACTION
from exabgp.reactor.async import ASYNC
from exabgp.reactor.interrupt import Signal
from exabgp.reactor.network.error import error

from exabgp.reactor.api import API
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.environment import environment

from exabgp.version import version
from exabgp.logger import Logger


class Reactor (object):
	# [hex(ord(c)) for c in os.popen('clear').read()]
	clear = concat_bytes_i(character(int(c,16)) for c in ['0x1b', '0x5b', '0x48', '0x1b', '0x5b', '0x32', '0x4a'])

	def __init__ (self, configurations):
		self._ips = environment.settings().tcp.bind
		self._port = environment.settings().tcp.port
		self._stopping = environment.settings().tcp.once

		self.max_loop_time = environment.settings().reactor.speed
		self.early_drop = environment.settings().daemon.drop

		self.processes = None

		self.configuration = Configuration(configurations)
		self.logger = Logger()
		self.async = ASYNC()
		self.signal = Signal()
		self.daemon = Daemon(self)
		self.listener = Listener(self)
		self.api = API(self)

		self.peers = {}

		self._reload_processes = False
		self._saved_pid = False

	def _termination (self,reason):
		self.signal.received = Signal.SHUTDOWN
		self.logger.critical(reason,'reactor')

	def _api_ready (self,sockets,dontsleep=False):
		sleeptime = 0 if dontsleep or self.async.ready() else self.max_loop_time / 100
		fds = self.processes.fds()
		ios = fds + sockets
		try:
			read,_,_ = select.select(ios,[],[],sleeptime)
			for fd in fds:
				if fd in read:
					read.remove(fd)
			return read
		except select.error as exc:
			err_no,message = exc.args  # pylint: disable=W0633
			if err_no not in error.block:
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

	def _active_peers (self):
		peers = set()
		for key,peer in self.peers.items():
			if not peer.neighbor.passive or peer.proto:
				peers.add(key)
		return peers

	def _completed (self,peers):
		for peer in peers:
			if self.peers[peer].neighbor.rib.outgoing.pending():
				return False
		return True

	def run (self, validate, root):
		self.daemon.daemonise()

		# Make sure we create processes once we have closed file descriptor
		# unfortunately, this must be done before reading the configuration file
		# so we can not do it with dropped privileges
		self.processes = Processes()

		# we have to read the configuration possibly with root privileges
		# as we need the MD5 information when we bind, and root is needed
		# to bind to a port < 1024

		# this is undesirable as :
		# - handling user generated data as root should be avoided
		# - we may not be able to reload the configuration once the privileges are dropped

		# but I can not see any way to avoid it
		for ip in self._ips:
			if not self.listener.listen_on(ip, None, self._port, None, False, None):
				return False

		if not self.load():
			return False

		if validate:  # only validate configuration
			self.logger.warning('','configuration')
			self.logger.warning('parsed Neighbors, un-templated','configuration')
			self.logger.warning('------------------------------','configuration')
			self.logger.warning('','configuration')
			for key in self.peers:
				self.logger.warning(str(self.peers[key].neighbor),'configuration')
				self.logger.warning('','configuration')
			return True

		for neighbor in self.configuration.neighbors.values():
			if neighbor.listen:
				if not self.listener.listen_on(neighbor.md5_ip, neighbor.peer_address, neighbor.listen, neighbor.md5_password, neighbor.md5_base64, neighbor.ttl_in):
					return False

		if not self.early_drop:
			self.processes.start(self.configuration.processes)

		if not self.daemon.drop_privileges():
			self.logger.critical('could not drop privileges to \'%s\' refusing to run as root' % self.daemon.user,'reactor')
			self.logger.critical('set the environmemnt value exabgp.daemon.user to change the unprivileged user','reactor')
			return

		if self.early_drop:
			self.processes.start(self.configuration.processes)

		# This is required to make sure we can write in the log location as we now have dropped root privileges
		if not self.logger.restart():
			self.logger.critical('could not setup the logger, aborting','reactor')
			return

		if not self.daemon.savepid():
			return

		# did we complete the run of updates caused by the last SIGUSR1/SIGUSR2 ?
		reload_completed = False

		wait = environment.settings().tcp.delay
		if wait:
			sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
			self.logger.debug('waiting for %d seconds before connecting' % sleeptime,'reactor')
			time.sleep(float(sleeptime))

		workers = {}
		peers = set()

		while True:
			try:
				if self.signal.received:
					for key in self.peers:
						if self.peers[key].neighbor.api['signal']:
							self.peers[key].reactor.processes.signal(self.peers[key].neighbor,self.signal.number)

					signaled = self.signal.received
					self.signal.rearm()

					if signaled == Signal.SHUTDOWN:
						self.shutdown()
						break

					if signaled == Signal.RESTART:
						self.restart()
						continue

					if not reload_completed:
						continue

					if signaled == Signal.FULL_RELOAD:
						self._reload_processes = True

					if signaled in (Signal.RELOAD, Signal.FULL_RELOAD):
						self.load()
						self.processes.start(self.configuration.processes,self._reload_processes)
						self._reload_processes = False
						continue

				if self.listener.incoming():
					# check all incoming connection
					self.async.schedule(str(uuid.uuid1()),'check new connection',self.listener.new_connections())

				peers = self._active_peers()
				if self._completed(peers):
					reload_completed = True

				# give a turn to all the peers
				for key in list(peers):
					peer = self.peers[key]
					action = peer.run()

					# .run() returns an ACTION enum:
					# * immediate if it wants to be called again
					# * later if it should be called again but has no work atm
					# * close if it is finished and is closing down, or restarting
					if action == ACTION.CLOSE:
						if key in self.peers:
							del self.peers[key]
						peers.discard(key)
					# we are loosing this peer, not point to schedule more process work
					elif action == ACTION.LATER:
						for io in peer.sockets():
							workers[io] = key
						# no need to come back to it before a a full cycle
						peers.discard(key)

					if not peers:
						break

				# read at least on message per process if there is some and parse it
				for service,command in self.processes.received():
					self.api.text(self,service,command)

				self.async.run()

				for io in self._api_ready(list(workers),len(peers)):
					peers.add(workers[io])
					del workers[io]

				if self._stopping and not self.peers.keys():
					self._termination('exiting on peer termination')

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
		"""Terminate all the current BGP connections"""
		self.logger.critical('performing shutdown','reactor')
		if self.listener:
			self.listener.stop()
			self.listener = None
		for key in self.peers.keys():
			self.peers[key].stop()
		self.async.clear()
		self.processes.terminate()
		self.daemon.removepid()
		self._stopping = True

	def load (self):
		"""Reload the configuration and send to the peer the route which changed"""
		self.logger.notice('performing reload of exabgp %s' % version,'configuration')

		reloaded = self.configuration.reload()

		if not reloaded:
			#
			# Careful the string below is used but the QA code to check for sucess of failure
			self.logger.error('problem with the configuration file, no change done','configuration')
			# Careful the string above is used but the QA code to check for sucess of failure
			#
			self.logger.error(str(self.configuration.error),'configuration')
			return False

		for key, peer in self.peers.items():
			if key not in self.configuration.neighbors:
				self.logger.debug('removing peer: %s' % peer.neighbor.name(),'reactor')
				peer.stop()

		for key, neighbor in self.configuration.neighbors.items():
			# new peer
			if key not in self.peers:
				self.logger.debug('new peer: %s' % neighbor.name(),'reactor')
				peer = Peer(neighbor,self)
				self.peers[key] = peer
			# modified peer
			elif self.peers[key].neighbor != neighbor:
				self.logger.debug('peer definition change, establishing a new connection for %s' % str(key),'reactor')
				self.peers[key].reestablish(neighbor)
			# same peer but perhaps not the routes
			else:
				# finding what route changed and sending the delta is not obvious
				self.logger.debug('peer definition identical, updating peer routes if required for %s' % str(key),'reactor')
				self.peers[key].reconfigure(neighbor)
			for ip in self._ips:
				if ip.afi == neighbor.peer_address.afi:
					self.listener.listen_on(ip, neighbor.peer_address, self._port, neighbor.md5_password, neighbor.md5_base64, None)
		self.logger.notice('loaded new configuration successfully','reactor')

		return True

	def restart (self):
		"""Kill the BGP session and restart it"""
		self.logger.notice('performing restart of exabgp %s' % version,'reactor')
		self.configuration.reload()

		for key in self.peers.keys():
			if key not in self.configuration.neighbors.keys():
				neighbor = self.configuration.neighbors[key]
				self.logger.debug('removing Peer %s' % neighbor.name(),'reactor')
				self.peers[key].stop()
			else:
				self.peers[key].reestablish()
		self.processes.start(self.configuration.processes,True)

	# def nexthops (self, peers):
	# 	return dict((peer,self.peers[peer].neighbor.local_address) for peer in peers)
