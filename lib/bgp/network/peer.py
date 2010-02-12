#!/usr/bin/env python
# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import sys
import traceback

from bgp.utils                import Log
from bgp.message              import Failure
from bgp.message.nop          import NOP
from bgp.message.open         import Capabilities
from bgp.message.update       import Update
from bgp.message.keepalive    import KeepAlive
from bgp.message.notification import Notification, Notify, NotConnected
from bgp.network.protocol     import Protocol

# As we can not know if this is our first start or not, this flag is used to
# always make the program act like it was recovering from a failure
# If set to FALSE, no EOR and OPEN Flags set for Restart will be set in the
# OPEN Graceful Restart Capability
FORCE_GRACEFUL = True

# Present a File like interface to socket.socket

class Peer (object):
	debug_timers = False		# debug hold/keepalive timers
	debug_trace = True			# debug traceback on unexpected exception

	def __init__ (self,neighbor,supervisor):
		self.log = Log(neighbor.peer_address,neighbor.peer_as)
		self.supervisor = supervisor
		self.neighbor = neighbor
		self.bgp = None

		self._loop = None
		self._open = None

		# The peer message should be processed
		self._running = False
		# The peer should restart after a stop
		self._restart = True
		# The peer was restarted (to know what kind of open to send for graceful restart)
		self._restarted = FORCE_GRACEFUL

	def stop (self):
		# we want to tear down the session and re-establish it
		self._running = False
		self._restart = True
		self._restarted = False

	def restart (self):
		# we want to tear down the session and re-establish it
		self._running = False
		self._restart = True
		self._restarted = True

	def shutdown (self):
		# this peer is going down forever
		self._running = False
		self._restart = False
		self._restarted = False

	def run (self):
		if self._loop:
			try:
				self._loop.next()
			except StopIteration:
				self._loop = None
		elif self._restart:
			self._running = True
			self._loop = self._run()
		else:
			self.bgp.close()
			self.supervisor.unschedule(self)

	def _run (self):
		try:
			self.bgp = Protocol(self)
			self.bgp.connect()

			_open = self.bgp.new_open(self._restarted)
			self.log.out('-> %s' % _open)
			yield None

			self._open = self.bgp.read_open(_open,self.neighbor.peer_address.ip)
			self.log.out('<- %s' % self._open)
			yield None

			message = self.bgp.new_keepalive(force=True)
			self.log.out('-> KEEPALIVE')
			yield None

			message = self.bgp.read_keepalive()
			self.log.out('<- KEEPALIVE')

			asn4 = not not self._open.capabilities.announced(Capabilities.FOUR_BYTES_ASN)

			messages = self.bgp.new_announce(asn4)
			if messages:
				self.log.out('-> UPDATE (%d)' % len(messages))

			if	self.neighbor.graceful_restart and \
				self._open.capabilities.announced(Capabilities.MULTIPROTOCOL_EXTENSIONS) and \
				self._open.capabilities.announced(Capabilities.GRACEFUL_RESTART):

				families = []
				for family in self._open.capabilities[Capabilities.GRACEFUL_RESTART].families():
					if family in self.neighbor.families:
						families.append(family)
				self.bgp.new_eors(families)
				self.log.outIf(families,'-> EOR %s' % ', '.join(['%s %s' % (str(afi),str(safi)) for (afi,safi) in families]))
			else:
				# If we are not sending an EOR, send a keepalive as soon as when finished
				# So the other routers knows that we have no (more) routes to send ...
				# (is that behaviour documented somewhere ??)
				c,k = self.bgp.new_keepalive()
				self.log.outIf(k,'-> KEEPALIVE (no more UPDATE and no EOR)')

			while self._running:
				c = self.bgp.check_keepalive()
				self.log.outIf(self.debug_timers,'Receive Timer %d second(s) left' % c)

				c,k = self.bgp.new_keepalive()
				self.log.outIf(k,'-> KEEPALIVE')
				self.log.outIf(self.debug_timers,'Sending Timer %d second(s) left' % c)

				message = self.bgp.read_message()

				self.log.outIf(message.TYPE == KeepAlive.TYPE,'<- KEEPALIVE')
				self.log.outIf(message.TYPE == Update.TYPE,'<- UPDATE')
				self.log.outIf(message.TYPE not in (KeepAlive.TYPE,Update.TYPE,NOP.TYPE), '<- %d' % ord(message.TYPE))

				messages = self.bgp.new_update(asn4)
				self.log.outIf(messages,'-> UPDATE (%d)' % len(messages))

				yield None
			
			if self.neighbor.graceful_restart and self._open.capabilities.announced(Capabilities.GRACEFUL_RESTART):
				self.log.out('Closing the connection without notification')
				self.bgp.close()
				return

			# User closing the connection
			raise Notify(6,3)
		except NotConnected, e:
			self.log.out('we can not connect to the peer %s' % str(e))
			try:
				self.bgp.close()
			except Failure:
				pass
			return
		except Notify,e:
			self.log.out('Sending Notification (%d,%d) [%s]  %s' % (e.code,e.subcode,str(e),e.data))
			try:
				self.bgp.new_notification(e)
				self.bgp.close()
			except Failure:
				pass
			return
		except Notification, e:
			self.log.out('Received Notification (%d,%d) from peer %s' % (e.code,e.subcode,str(e)))
			self.bgp.close()
			return
		except Failure, e:
			self.log.out(str(e))
			self.bgp.close()
			return
		except Exception, e:
			self.log.out('UNHANDLED EXCEPTION')
			if self.debug_trace:
				traceback.print_exc(file=sys.stdout)
				raise
			else:
				self.log.out(str(e))
			if self.bgp: self.bgp.close()
			return
