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

import sys
#from exabgp.logger import Logger

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
	def __init__ (self,hosts,port,backlog=200):
		self._hosts = hosts
		self._port = port
		self._backlog = backlog

		self.serving = False
		self.sockets = {}
		self.logger = sys.stdout.write  # Logger()

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
			if e.args[0] == errno.errno.EADDRINUSE:
				raise BindingError('could not listen, port already in use %s:%d' % (ip,self._port))
			elif e.args[0] == errno.errno.EADDRNOTAVAIL:
				raise BindingError('could not listen, invalid address %s:%d' % (ip,self._port))
			else:
				raise BindingError('could not listen on %s:%d - %s' % (ip,self._port,str(e)))

	def start (self):
		try:
			for host in self._hosts:
				if (host,self._port) not in self.sockets:
					s = self._bind(host,self._port)
					self.sockets[s] = (host,self._port)
			self.serving = True
		except NetworkError,e:
				self.logger.critical(str(e))
				raise e

	def connections (self):
		if not self.serving:
			return

		try:
			for sock in self.sockets:
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

	def stop (self):
		if not self.serving:
			return

		for sock,(ip,port) in self.sockets.items():
			self.logger.critical('stop listening on %s:%d' % (ip,port))
			sock.close()

		self.sockets = {}
		self.serving = False

# listener = Listener(['127.0.0.1',],7900)
# listener.start()
# inloop = True
# while inloop:
# 	for s,ip in listener.connections():
# 		inloop = False
# 		break
# s.send('AHAHA !')
# listener.stop()
