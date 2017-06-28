# encoding: utf-8
"""
reactor/loop.py

Created by Thomas Mangin on 2012-06-10.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import re
import time
import signal
import select
import socket

from exabgp.vendoring import six

from exabgp.util import character
from exabgp.util import concat_bytes_i

from exabgp.reactor.daemon import Daemon
from exabgp.reactor.listener import Listener
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.api.processes import ProcessError
from exabgp.reactor.peer import Peer
from exabgp.reactor.peer import ACTION
from exabgp.reactor.network.error import error

from exabgp.reactor.api import API
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.environment import environment

from exabgp.version import version
from exabgp.logger import Logger


class SIGNAL (object):
	NONE     = 0
	SHUTDOWN = 1
	RESTART  = 2
	RELOAD   = 3


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
		self.listener = Listener(self)
		self.configuration = Configuration(configurations)
		self.api = API(self,self.configuration)

		self.peers = {}

		self._stopping = environment.settings().tcp.once
		self._signaled = SIGNAL.NONE
		self._reload_processes = False
		self._saved_pid = False
		self._running = None
		self._async = []

		self._signal = {}

		signal.signal(signal.SIGTERM, self.sigterm)
		signal.signal(signal.SIGHUP, self.sighup)
		signal.signal(signal.SIGALRM, self.sigalrm)
		signal.signal(signal.SIGUSR1, self.sigusr1)
		signal.signal(signal.SIGUSR2, self.sigusr2)

	def _termination (self,reason):
		while True:
			try:
				self._signaled = SIGNAL.SHUTDOWN
				self.logger.reactor(reason,'warning')
				break
			except KeyboardInterrupt:
				pass

	# XXX: It seems odd to find all the signal api processes via peers

	def sigterm (self, signum, frame):
		if self._signaled:
			self.logger.reactor('SIG TERM received - ignoring - still handling previous signal')
			return
		self.logger.reactor('SIG TERM received - shutdown')
		self._signaled = SIGNAL.SHUTDOWN
		for key in self.peers:
			if self.peers[key].neighbor.api['signal']:
				self._signal[key] = signum

	def sighup (self, signum, frame):
		if self._signaled:
			self.logger.reactor('SIG HUP received - ignoring - still handling previous signal')
			return
		self.logger.reactor('SIG HUP received - shutdown')
		self._signaled = SIGNAL.SHUTDOWN
		for key in self.peers:
			if self.peers[key].neighbor.api['signal']:
				self._signal[key] = signum

	def sigalrm (self, signum, frame):
		if self._signaled:
			self.logger.reactor('SIG ALRM received - ignoring - still handling previous signal')
			return
		self.logger.reactor('SIG ALRM received - restart')
		self._signaled = SIGNAL.RESTART
		for key in self.peers:
			if self.peers[key].neighbor.api['signal']:
				self._signal[key] = signum

	def sigusr1 (self, signum, frame):
		if self._signaled:
			self.logger.reactor('SIG USR1 received - ignoring - still handling previous signal')
			return
		self.logger.reactor('SIG USR1 received - reload configuration')
		self._signaled = SIGNAL.RELOAD
		for key in self.peers:
			if self.peers[key].neighbor.api['signal']:
				self._signal[key] = signum

	def sigusr2 (self, signum, frame):
		if self._signaled:
			self.logger.reactor('SIG USR1 received - ignoring - still handling previous signal')
			return
		self.logger.reactor('SIG USR2 received - reload configuration and processes')
		self._signaled = SIGNAL.RELOAD
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

	def schedule_rib_check (self):
		self.logger.reactor('performing dynamic route update')
		for key in self.configuration.neighbors.keys():
			self.peers[key].schedule_rib_check()

	def _active_peers (self):
		peers = set()
		for key,peer in self.peers.items():
			if not peer.neighbor.passive or peer.proto:
				peers.add(key)
		return peers

	def run (self, validate, root):
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
			if not self.listener.listen_on(ip, None, self.port, None, False, None):
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
				if not self.listener.listen_on(neighbor.md5_ip, neighbor.peer_address, neighbor.listen, neighbor.md5_password, neighbor.md5_base64, neighbor.ttl_in):
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
		reload_completed = False

		wait = environment.settings().tcp.delay
		if wait:
			sleeptime = (wait * 60) - int(time.time()) % (wait * 60)
			self.logger.reactor('waiting for %d seconds before connecting' % sleeptime)
			time.sleep(float(sleeptime))

		workers = {}
		evaluated = []
		peers = set()

		max_loop_time = self.max_loop_time
		half_loop_time = self.max_loop_time / 2

		while True:
			try:
				start = time.time()

				if self._signaled:
					signaled = self._signaled
					self._signaled = SIGNAL.NONE

					# Handle signal message to API
					for key in self._signal:
						self.peers[key].reactor.processes.signal(self.peers[key].neighbor,self._signal[key])
					self._signal = {}

					if signaled == SIGNAL.SHUTDOWN:
						self.shutdown()
						break

					if signaled == SIGNAL.RESTART:
						self.restart()
						continue

					if not reload_completed:
						continue
					if signaled == SIGNAL.RELOAD:
						self.load()
						self.processes.start(self._reload_processes)
						self._reload_processes = False
						continue

				if self.listener.serving:
					# check all incoming connection
					self.async('check new connection',self.listener.new_connections())

				peers = self._active_peers()
				if not peers:
					reload_completed = True

				end_peers = start + half_loop_time
				end_loop = start + max_loop_time

				if not evaluated:
					evaluated.extend(list(peers))

				# give a turn to all the peers
				while evaluated:
					if not start < time.time() < end_peers:
						break
					key = evaluated.pop()
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

					if not peers:
						break

				# read at least on message per process if there is some and parse it
				for service,command in self.processes.received():
					self.api.text(self,service,command)

				while time.time() < end_loop:
					# handle API calls
					if not self._run_async():
						break

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
		"""Terminate all the current BGP connections"""
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
		"""Reload the configuration and send to the peer the route which changed"""
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
					self.listener.listen_on(ip, neighbor.peer_address, self.port, neighbor.md5_password, neighbor.md5_base64, None)
		self.logger.configuration('loaded new configuration successfully','info')

		return True

	def async (self, name, callback):
		self.logger.reactor('async | %s' % name)
		self._async.append(callback)

	def _run_async (self, flipflop=[]):
		try:
			for generator in self._async:
				try:
					six.next(generator)
					six.next(generator)
					flipflop.append(generator)
				except StopIteration:
					pass
			self._async, flipflop = flipflop, []
			return len(self._async) > 0
		except KeyboardInterrupt:
			self._termination('^C received')
			return False

	def restart (self):
		"""Kill the BGP session and restart it"""
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
		self._signaled = SIGNAL.SHUTDOWN
		self._async = []
		self._running = None

	def api_reload (self):
		self._signaled = SIGNAL.RELOAD
		self._async = []
		self._running = None

	def api_restart (self):
		self._signaled = SIGNAL.RESTART
		self._async = []
		self._running = None

	@staticmethod
	def match_neighbor (description, name):
		for string in description:
			if re.search(r'(^|\s)%s($|\s|,)' % re.escape(string), name) is None:
				return False
		return True

	def match_neighbors (self, descriptions):
		"""Return the sublist of peers matching the description passed, or None if no description is given"""
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
