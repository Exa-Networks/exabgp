#!/usr/bin/env python
# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2011 Exa Networks. All rights reserved.
"""

import sys
import time
import traceback

from bgp.message              import Failure
from bgp.message.nop          import NOP
from bgp.message.open         import Capabilities
from bgp.message.update       import Update
from bgp.message.keepalive    import KeepAlive
from bgp.message.notification import Notification, Notify, NotConnected
from bgp.network.protocol     import Protocol

from bgp.log import Logger
logger = Logger()

# As we can not know if this is our first start or not, this flag is used to
# always make the program act like it was recovering from a failure
# If set to FALSE, no EOR and OPEN Flags set for Restart will be set in the
# OPEN Graceful Restart Capability
FORCE_GRACEFUL = True

# Present a File like interface to socket.socket

class Peer (object):
	# debug hold/keepalive timers
	debug_trace = True			# debug traceback on unexpected exception

	def __init__ (self,neighbor,supervisor):
		self.supervisor = supervisor
		self.neighbor = neighbor
		# The next restart neighbor definition
		self._neighbor = None
		self.bgp = None
		# We may have new update to transmit to our peers, so we need to check
		self._updates = False

		self._loop = None
		self.open = None

		# The peer message should be processed
		self._running = False
		# The peer should restart after a stop
		self._restart = True
		# The peer was restarted (to know what kind of open to send for graceful restart)
		self._restarted = FORCE_GRACEFUL
		self._reset_skip()

	def _reset_skip (self):
		# We are currently not skipping connection attempts
		self._skip = 0
		# when we can not connect to a peer how many time (in loop) should we back-off
		self._next_skip = 1

	def _more_skip (self):
		self._skip = self._next_skip
		self._next_skip = self._next_skip*2
		if self._next_skip > 512:
			self._next_skip = 512

	def me (self,message):
		return "Peer %15s ASN %-7s %s" % (self.neighbor.peer_address,self.neighbor.peer_as,message)

	def stop (self):
		self._running = False
		self._restart = False
		self._restarted = False
		self._reset_skip()

	def reload (self,routes):
		self._updates = True
		self.neighbor.set_routes(routes)
		self._reset_skip()

	def restart (self,restart_neighbor=None):
		# we want to tear down the session and re-establish it
		self._running = False
		self._restart = True
		self._restarted = True
		self._neighbor = restart_neighbor
		self._reset_skip()

	def run (self):
		if self._loop:
			try:
				if self._skip:
					self._skip -= 1
					return None
				else:
					return self._loop.next()
			except StopIteration:
				self._loop = None
		elif self._restart:
			# If we are restarting, and the neighbor definition is different, update the neighbor
			if self._neighbor:
				self.neighbor = self._neighbor
				self._neighbor = None
			self._running = True
			self._loop = self._run()
		else:
			self.bgp.close()
			self.supervisor.unschedule(self)

	def _run (self,max_wait_open=10.0):
		try:
			self.bgp = Protocol(self)
			self.bgp.connect()

			_open = self.bgp.new_open(self._restarted)
			logger.message(self.me('>> %s' % _open))
			yield None

			start = time.time()
			while True:
				print "\n\n\------ IN LOOP \n\n"
				self.open = self.bgp.read_open(_open,self.neighbor.peer_address.ip)
				if self.open:
					logger.message(self.me('<< %s' % self.open))
					yield None
					break
				if time.time() - start > max_wait_open: 
					logger.message(self.me('waited for an OPEN for too long - killing the session'))
					raise Notify(1,1,'the packet received does not contain a BGP marker')
				yield None

			message = self.bgp.new_keepalive(force=True)
			logger.message(self.me('>> KEEPALIVE (OPENCONFIRM)'))
			yield True

			message = self.bgp.read_keepalive()
			logger.message(self.me('<< KEEPALIVE (ESTABLISHED)'))

			count = 0
			for count in self.bgp.new_announce():
				yield True
			if count:
				logger.message(self.me('>> %d UPDATE(s)' % count))

			eor = False
			if	self.neighbor.graceful_restart and \
				self.open.capabilities.announced(Capabilities.MULTIPROTOCOL_EXTENSIONS) and \
				self.open.capabilities.announced(Capabilities.GRACEFUL_RESTART):

				families = []
				for family in self.open.capabilities[Capabilities.GRACEFUL_RESTART].families():
					if family in self.neighbor.families:
						families.append(family)
				self.bgp.new_eors(families)
				if families:
					eor = True
					logger.message(self.me('>> EOR %s' % ', '.join(['%s %s' % (str(afi),str(safi)) for (afi,safi) in families])))
			
			if not eor:
				# If we are not sending an EOR, send a keepalive as soon as when finished
				# So the other routers knows that we have no (more) routes to send ...
				# (is that behaviour documented somewhere ??)
				c,k = self.bgp.new_keepalive(True)
				if k: logger.message(self.me('>> KEEPALIVE (no more UPDATE and no EOR)'))

			while self._running:
				c,k = self.bgp.new_keepalive()
				if k: logger.message(self.me('>> KEEPALIVE'))
				logger.timers(self.me('Sending Timer %d second(s) left' % c))

				message = self.bgp.read_message()
				# let's read if we have keepalive before doing the timer check
				c = self.bgp.check_keepalive()
				logger.timers(self.me('Receive Timer %d second(s) left' % c))

				if message.TYPE == KeepAlive.TYPE:
					logger.message(self.me('<< KEEPALIVE'))
				if message.TYPE == Update.TYPE:
					logger.message(self.me('<< UPDATE'))
				if message.TYPE not in (KeepAlive.TYPE,Update.TYPE,NOP.TYPE):
					 logger.message(self.me('<< %d' % ord(message.TYPE)))

				if self._updates:
					self._updates = False

					count = 0
					for count in self.bgp.new_update():
						yield True
					logger.message(self.me('>> UPDATE (%d)' % count))

				yield None
			
			if self.neighbor.graceful_restart and self.open.capabilities.announced(Capabilities.GRACEFUL_RESTART):
				logger.warning('Closing the connection without notification')
				self.bgp.close()
				return

			# User closing the connection
			raise Notify(6,3)
		except NotConnected, e:
			logger.warning('we can not connect to the peer %s' % str(e))
			self._more_skip()
			try:
				self.bgp.close()
			except Failure:
				pass
			return
		except Notify,e:
			logger.message(self.me('Sending Notification (%d,%d) [%s]  %s' % (e.code,e.subcode,str(e),e.data)))
			try:
				self.bgp.new_notification(e)
				self.bgp.close()
			except Failure:
				pass
			return
		except Notification, e:
			logger.message(self.me('Received Notification (%d,%d) from peer %s' % (e.code,e.subcode,str(e))))
			self.bgp.close()
			return
		except Failure, e:
			logger.warning(self.me(str(e)))
			self._more_skip()
			self.bgp.close()
			return
		except Exception, e:
			logger.warning(self.me('UNHANDLED EXCEPTION'))
			self._more_skip()
			if self.debug_trace:
				# should really go to syslog
				traceback.print_exc(file=sys.stdout)
				raise
			else:
				logger.warning(self.me(str(e)))
			if self.bgp: self.bgp.close()
			return
