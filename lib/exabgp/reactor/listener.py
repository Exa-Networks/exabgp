# encoding: utf-8
"""
listen.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2015 Exa Networks. All rights reserved.
"""

import socket

from exabgp.util.errstr import errstr

from exabgp.protocol.family import AFI
# from exabgp.util.coroutine import each
from exabgp.reactor.network.tcp import MD5
from exabgp.reactor.network.error import error
from exabgp.reactor.network.error import errno
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.network.error import BindingError
from exabgp.reactor.network.error import AcceptError
from exabgp.reactor.network.incoming import Incoming

from exabgp.logger import Logger


class Listener (object):
	_family_AFI_map = {
		socket.AF_INET: AFI.ipv4,
		socket.AF_INET6: AFI.ipv6,
	}

	def __init__ (self, backlog=200):
		self._backlog = backlog
		self.serving = False
		self._sockets = {}

		self.logger = Logger()

	def _new_socket (self, ip):
		if ip.afi == AFI.ipv6:
			return socket.socket(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)
		if ip.afi == AFI.ipv4:
			return socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
		raise NetworkError('Can not create socket for listening, family of IP %s is unknown' % ip)

	def listen (self, local_ip, peer_ip, local_port, md5):
		self.serving = True

		for sock,(local,port,peer,md) in self._sockets.items():
			if local_ip.ip != local:
				continue
			if local_port != port:
				continue
			if md5:
				MD5(sock,peer_ip.ip,0,md5)
			return

		try:
			sock = self._new_socket(local_ip)
			if md5:
				# MD5 must match the peer side of the TCP, not the local one
				MD5(sock,peer_ip.ip,0,md5)
			try:
				sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			except (socket.error,AttributeError):
				pass
			sock.setblocking(0)
			# s.settimeout(0.0)
			sock.bind((local_ip.ip,local_port))
			sock.listen(self._backlog)
			self._sockets[sock] = (local_ip.ip,local_port,peer_ip.ip,md5)
		except socket.error,exc:
			if exc.args[0] == errno.EADDRINUSE:
				raise BindingError('could not listen on %s:%d, the port already in use by another application' % (local_ip,local_port))
			elif exc.args[0] == errno.EADDRNOTAVAIL:
				raise BindingError('could not listen on %s:%d, this is an invalid address' % (local_ip,local_port))
			raise NetworkError(str(exc))
		except NetworkError,exc:
			self.logger.network(str(exc),'critical')
			raise exc

	# @each
	def connected (self):
		if not self.serving:
			return

		try:
			for sock in self._sockets:
				try:
					io, _ = sock.accept()
					if sock.family == socket.AF_INET:
						local_ip  = io.getpeername()[0]  # local_ip,local_port
						remote_ip = io.getsockname()[0]  # remote_ip,remote_port
					elif sock.family == socket.AF_INET6:
						local_ip  = io.getpeername()[0]  # local_ip,local_port,local_flow,local_scope
						remote_ip = io.getsockname()[0]  # remote_ip,remote_port,remote_flow,remote_scope
					else:
						raise AcceptError('unexpected address family (%d)' % sock.family)
					fam = self._family_AFI_map[sock.family]
					yield Incoming(fam,remote_ip,local_ip,io)
				except socket.error,exc:
					if exc.errno in error.block:
						continue
					raise AcceptError('could not accept a new connection (%s)' % errstr(exc))
		except NetworkError,exc:
			self.logger.network(str(exc),'critical')

	def stop (self):
		if not self.serving:
			return

		for sock,(ip,port,_,_) in self._sockets.items():
			sock.close()
			self.logger.network('stopped listening on %s:%d' % (ip,port),'info')

		self._sockets = {}
		self.serving = False
