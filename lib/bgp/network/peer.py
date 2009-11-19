#!/usr/bin/env python
# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils                import *
from bgp.message.parent       import Failure
from bgp.message.nop          import NOP
from bgp.message.open         import Open
from bgp.message.update       import Update
from bgp.message.keepalive    import KeepAlive
from bgp.message.notification import Notification, Notify
from bgp.network.protocol     import Protocol

# Present a File like interface to socket.socket

class Peer (object):
	debug_timers = False		# debug hold/keepalive timers
	debug_trace = True			# debug traceback on unexpected exception

	def __init__ (self,neighbor,supervisor):
		self.log = Log(neighbor.peer_address,neighbor.peer_as)
		self.supervisor = supervisor
		self.neighbor = neighbor
		self.running = False
		self.restart = True
		self.bgp = None
		self._loop = None


	def stop (self):
		self.running = False

	def shutdown (self):
		self.running = False
		self.restart = False

	def run (self):
		if self._loop:
			try:
				self._loop.next()
			except StopIteration:
				self._loop = None
		elif self.restart:
			self.running = True
			self._loop = self._run()
		else:
			self.bgp.close()
			self.supervisor.unschedule(self)

	def _run (self):
		try:
			self.bgp = Protocol(self.neighbor)
			self.bgp.connect()

			o = self.bgp.new_open()
			self.log.out('-> %s' % o)
			yield None

			o = self.bgp.read_open(self.neighbor.peer_address.ip())
			self.log.out('<- %s' % o)
			yield None

			message = self.bgp.new_keepalive(force=True)
			self.log.out('-> KEEPALIVE')
			yield None

			message = self.bgp.read_keepalive()
			self.log.out('<- KEEPALIVE')

			messages = self.bgp.new_announce()
			self.log.outIf(messages,'-> UPDATE (%d)' % len(messages))

			while self.running:
				c = self.bgp.check_keepalive()
				self.log.outIf(self.debug_timers,'Receive Timer %d second(s) left' % c)

				c,k = self.bgp.new_keepalive()
				self.log.outIf(k,'-> KEEPALIVE')
				self.log.outIf(self.debug_timers,'Sending Timer %d second(s) left' % c)

				message = self.bgp.read_message()

				self.log.outIf(message.TYPE == KeepAlive.TYPE,'<- KEEPALIVE')
				self.log.outIf(message.TYPE == Update.TYPE,'<- UPDATE')
				self.log.outIf(message.TYPE not in (KeepAlive.TYPE,Update.TYPE,NOP.TYPE), '<- %d' % ord(message.TYPE))

				messages = self.bgp.new_update()
				self.log.outIf(messages,'-> UPDATE (%d)' % len(messages))

				yield None
			# User closing the connection
			raise Notify(6,0)
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
