# encoding: utf-8
"""
listen.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2013 Exa Networks. All rights reserved.
"""

import time
import socket

from exabgp.util.errstr import errstr

from exabgp.protocol.family import AFI
from exabgp.util.coroutine import each
from exabgp.util.ip import isipv4,isipv6
from exabgp.reactor.network.error import error,errno,NetworkError,BindingError,AcceptError
from exabgp.reactor.network.incoming import Incoming
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.notification import Notify

from exabgp.logger import Logger


class Listener (object):
	MAX_OPEN_WAIT = 10.0  # seconds
	HEADER_LEN = 19  # bytes

	open_bye = Notify(2,0,'we do not accept incoming connection - thanks for calling').message()
	open_invalid_header = Notify(2,0,'invalid OPEN message (16 first bytes are not 0xFF)').message()
	open_invalid_type   = Notify(2,0,'invalid OPEN message (it is not an OPEN message)').message()
	open_invalid_size   = Notify(2,0,'invalid OPEN message (invalid size in message)').message()

	def __init__ (self,hosts,port,backlog=200):
		self._hosts = hosts
		self._port = port
		self._backlog = backlog

		self.serving = False
		self._sockets = {}
		self._connected = {}
		self.logger = Logger()

	def _bind (self,ip,port):
		try:
			if isipv6(ip):
				s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)
				try:
					s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				except AttributeError:
					pass
				s.bind((ip,port,0,0))
			elif isipv4(ip):
				s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
				try:
					s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				except AttributeError:
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
				self.logger.critical(str(e))
				raise e

	def _connections (self):
		if not self.serving:
			return

		try:
			for sock,(host,_) in self._sockets.items():
				try:
					io, (ip,port) = sock.accept()
					yield Incoming(AFI.ipv4,ip,host,io)
					break
				except socket.error, e:
					if e.errno in error.block:
						continue
					raise AcceptError('could not accept a new connection (%s)' % errstr(e))
		except NetworkError,e:
			self.logger.critical(str(e))
			raise e

	@each
	def connections (self):
		now = time.time()
		for connection in self._connections():
			self._connected[connection] = (now,'header',self.HEADER_LEN,'')

		for connection,(then,stage,to_read,received) in self._connected.items():
			try:
				data = connection.read(to_read)
				to_read -= len(data)
				received += data

				if now - then > self.MAX_OPEN_WAIT:
					self._delete(connection)
					continue

				if to_read:
					self._connected[connection] = (then,stage,to_read,received)
					continue

				if stage == 'header':
					if received[:16] != '\xFF' * 16:
						self._reply(connection,self.open_invalid_header)
						self._delete(connection)
						continue
					if received[18] != Open.TYPE:
						self._reply(connection,self.open_invalid_type)
						self._delete(connection)
						continue
					size = (ord(data[16]) << 16) + ord(data[17])
					if size < 29:
						self._reply(connection,self.open_invalid_size)
						self._delete(connection)
						continue
					to_read = size - self.HEADER_LEN
					self._connected[connection] = (then,'body',to_read,received)
					continue

				self._reply(connection,self.open_bye)
				self._delete(connection)

				yield received,connection.local,connection.peer
			except socket.error,e:
				if e.errno in error.block:
					if now - then > self.MAX_OPEN_WAIT:
						self._delete(connection)

	def _delete (self,sock):
		self._connected.pop(sock)
		try:
			sock.close()
		except socket.error:
			pass

	def _reply (self,sock,message):
		try:
			sock.write(message)
		except socket.error:
			pass

	def stop (self):
		if not self.serving:
			return

		for sock,(ip,port) in self._sockets.items():
			self.logger.critical('stop listening on %s:%d' % (ip,port))
			sock.close()

		self._sockets = {}
		self.serving = False
