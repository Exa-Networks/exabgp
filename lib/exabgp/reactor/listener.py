# encoding: utf-8
"""
listen.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2013 Exa Networks. All rights reserved.
"""

import socket

from exabgp.util.errstr import errstr

from exabgp.protocol.family import AFI
#from exabgp.util.coroutine import each
from exabgp.util.ip import isipv4,isipv6
from exabgp.reactor.network.error import error,errno,NetworkError,BindingError,AcceptError
from exabgp.reactor.network.incoming import Incoming
#from exabgp.bgp.message.open import Open
#from exabgp.bgp.message.notification import Notify

from exabgp.logger import Logger


class Listener (object):
	def __init__ (self,hosts,port,backlog=200):
		self._hosts = hosts
		self._port = port
		self._backlog = backlog

		self.serving = False
		self._sockets = {}
		#self._connected = {}
		self.logger = Logger()

	def _bind (self,ip,port):
		try:
			if isipv6(ip):
				s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)
				try:
					s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				except (socket.error,AttributeError):
					pass
				s.bind((ip,port,0,0))
			elif isipv4(ip):
				s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
				try:
					s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				except (socket.error,AttributeError):
					pass
				s.bind((ip,port))
			else:
				return None
			s.setblocking(0)
			##s.settimeout(0.0)
			s.listen(self._backlog)
			return s
		except socket.error, e:
			if e.args[0] == errno.EADDRINUSE:
				raise BindingError('could not listen on %s:%d, the port already in use by another application' % (ip,self._port))
			elif e.args[0] == errno.EADDRNOTAVAIL:
				raise BindingError('could not listen on %s:%d, this is an invalid address' % (ip,self._port))
			else:
				raise BindingError('could not listen on %s:%d (%s)' % (ip,self._port,errstr(e)))

	def start (self):
		try:
			for host in self._hosts:
				if (host,self._port) not in self._sockets:
					s = self._bind(host,self._port)
					self._sockets[s] = (host,self._port)
			self.serving = True
		except NetworkError,e:
				self.logger.network(str(e),'critical')
				raise e
		self.serving = True

	# @each
	def connected (self):
		if not self.serving:
			return

		try:
			for sock,(host,_) in self._sockets.items():
				try:
					io, _ = sock.accept()
					local_ip,local_port = io.getpeername()
					remote_ip,remote_port = io.getsockname()
					yield Incoming(AFI.ipv4,remote_ip,local_ip,io)
					break
				except socket.error, e:
					if e.errno in error.block:
						continue
					raise AcceptError('could not accept a new connection (%s)' % errstr(e))
		except NetworkError,e:
			self.logger.network(str(e),'critical')
			raise e

	def stop (self):
		if not self.serving:
			return

		for sock,(ip,port) in self._sockets.items():
			sock.close()
			self.logger.network('stopped listening on %s:%d' % (ip,port),'info')

		self._sockets = {}
		self.serving = False
