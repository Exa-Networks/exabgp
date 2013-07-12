# encoding: utf-8
"""
listen.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2013 Exa Networks. All rights reserved.
"""

import time
import socket

from exabgp.util.error import error,errno
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.notification import Notification

#from exabgp.logger import Logger
import sys
class Logger:
	critical = sys.stdout.write



# START --------- To move in util ---------------

def isipv4(address):
	try:
		socket.inet_pton(socket.AF_INET, address)
		return True
	except socket.error:
		return False

def isipv6(address):
	try:
		socket.inet_pton(socket.AF_INET6, address)
		return True
	except socket.error:
		return False

def isip(address):
	return isipv4(address) or isipv6(address)

# END --------- To move in util ---------------

class NetworkError (Exception): pass
class BindingError (NetworkError): pass
class AcceptError  (NetworkError): pass

class Listener (object):
	MAX_OPEN_WAIT = 20.0  # seconds
	HEADER_LEN = 19  # bytes

	open_bye = Notification().new(2,0,'we do not accept incoming connection - thanks for calling').message()
	open_invalid_header = Notification().new(2,0,'invalid OPEN message (16 first bytes are not 0xFF)').message()
	open_invalid_type   = Notification().new(2,0,'invalid OPEN message (it is not an OPEN message)').message()
	open_invalid_size   = Notification().new(2,0,'invalid OPEN message (invalid size in message)').message()

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
					s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
				except AttributeError:
					pass
				s.bind((ip,port,0,0))
			elif isipv4(ip):
				s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
				try:
					s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
					s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
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
				raise BindingError('could not listen, port already in use %s:%d' % (ip,self._port))
			elif e.args[0] == errno.EADDRNOTAVAIL:
				raise BindingError('could not listen, invalid address %s:%d' % (ip,self._port))
			else:
				raise BindingError('could not listen on %s:%d - %s' % (ip,self._port,str(e)))

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
			for sock in self._sockets:
				try:
					s, (ip,port) = sock.accept()
					s.setblocking(0)
					yield s, ip
					break
				except socket.error, e:
					if e.errno in error.block:
						continue
					raise AcceptError('could not accept a new connection %s' % str(e))
		except NetworkError,e:
			self.logger.critical(str(e))
			raise e

	def connections (self):
		now = time.time()
		for sock,ip in self._connections():
			self._connected[sock] = (now,ip,'header',self.HEADER_LEN,'')

		for sock,(then,ip,stage,to_read,received) in self._connected.items():
			try:
				data = sock.recv(to_read)
				print "read", len(data)
				to_read -= len(data)
				received += data

				if now - then > self.MAX_OPEN_WAIT:
					self._delete(sock)
					continue

				if to_read:
					self._connected[sock] = (then,ip,stage,to_read,received)
					continue

				if stage == 'header':
					if received[:16] != '\xFF' * 16:
						self._reply(sock,self.open_invalid_header)
						self._delete(sock)
						continue
					if received[18] != Open.TYPE:
						self._reply(sock,self.open_invalid_type)
						self._delete(sock)
						continue
					size = (ord(data[16]) << 16) + ord(data[17])
					if size < 29:
						self._reply(sock,self.open_invalid_size)
						self._delete(sock)
						continue
					to_read = size - self.HEADER_LEN
					print 'to_read', to_read
					self._connected[sock] = (then,ip,'body',to_read,received)
					continue

				yield sock,received,ip  # XXX: must the the socket remove end IP
			except socket.error,e:
				if e.errno in error.block:
					if now - then > self.MAX_OPEN_WAIT:
						self._delete(sock)

	def _delete (self,sock):
		self._connected.pop(sock)
		try:
			sock.close()
		except socket.error:
			pass

	def _reply (self,sock,message):
		try:
			sock.send(message)
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


listener = Listener(['127.0.0.1',],179)
listener.start()
inloop = True
while inloop:
	for s,data,ip in listener.connections():
		inloop = False
		break
s.send(Listener.open_bye)
listener.stop()
