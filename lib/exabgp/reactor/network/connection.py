# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time
import socket
import select

from exabgp.configuration.environment import environment

from exabgp.util.od import od
from exabgp.util.trace import trace
from exabgp.reactor.network.error import error,errno,NetworkError,TooSlowError,NotConnected

from exabgp.logger import Logger,LazyFormat

from .error import *

class Connection (object):
	def __init__ (self,afi,peer,local):
		# peer and local are strings of the IP

		# If the OS tells us we have data on the socket, we should never have to wait more than read_timeout to be able to read it.
		# However real life says that on some OS we do ... So let the user control this value
		self.read_timeout = environment.settings().tcp.timeout
		self.async = not environment.settings().tcp.block

		self.logger = Logger()

		self.afi = afi
		self.peer = peer
		self.local = local

		self._loop_start = None

	def pending (self,reset=False):
		if reset:
			self._loop_start = None
		else:
			if not self._loop_start:
				self._loop_start = time.time()
			else:
				if self._loop_start + self.read_timeout < time.time():
					raise TooSlowError('Waited for data on a socket for more than %d second(s)' % self.read_timeout)
		try:
			r,_,_ = select.select([self.io,],[],[],0)
		except select.error,e:
			errno,message = e.args
			if errno in error.block:
				return False
			raise
		if r: return True
		return False

	def ready (self):
		while True:
			try:
				_,w,_ = select.select([],[self.io,],[],0)
			except select.error,e:
				eno,message = e.args
				if eno in error.block:
					if self.async:
						return False
					continue
				raise
			if not w:
				if self.async:
					return False
				continue
			return True

	def read (self,number):
		if not self.io:
			raise NotConnected('Trying to read on a close TCP conncetion')
		if number == 0: return ''
		try:
			r = self.io.recv(number)
			if not r:
				# The socket was closed - no data is available anymore (the caller will call .close() on us)
				raise NotConnected('The TCP connection is closed')
			self.logger.wire(LazyFormat("Peer %15s RECV " % self.peer,od,r))
			return r
		except socket.timeout,e:
			self.close()
			raise TooSlowError('Timeout while reading data from the network:  %s ' % str(e))
		except socket.error,e:
			self.close()
			raise NetworkError('Problem while reading data from the network:  %s ' % str(e))

	def write (self,data):
		if not self.io:
			# We already returned a Failure
			# It must be a write attempted during the closing of the peering session
			# Make sure it does not hold the cleanup.
			return True
		if not self.ready():
			return False
		try:
			self.logger.wire(LazyFormat("Peer %15s SENT " % self.peer,od,data))
			# we can not use sendall as in case of network buffer filling
			# it does raise and does not let you know how much was sent
			sent = 0
			length = len(data)
			while sent < length:
				try:
					nb = self.io.send(data[sent:])
					if not nb:
						self.logger.wire("%15s lost TCP session with peer" % self.peer)
						raise NotConnected('lost TCP session')
					sent += nb
				except socket.error,e:
					if e.args[0] in error.block:
						if sent == 0:
							self.logger.wire("%15s problem sending message, errno %s, will retry later" % (errno.errorcode[e.args[0]],self.peer))
							return False
						else:
							self.logger.wire("%15s problem sending mid-way through a message, trying to complete" % self.peer)
							time.sleep(0.01)
						continue
					else:
						self.logger.wire("%15s problem sending message, errno %s" % (self.peer,str(e.args[0])))
						raise e
			return True
		except socket.error, e:
			# Must never happen as we are performing a select before the write
			#failure = getattr(e,'errno',None)
			#if failure in error.block:
			#	return False
			self.close()
			self.logger.wire("%15s %s" % (self.peer,trace()))
			if e.errno == errno.EPIPE:
				# The TCP connection is gone.
				raise NetworkError('Broken TCP connection')
			else:
				raise NetworkError('Problem while writing data to the network: %s' % str(e))

	def close (self):
		try:
			self.logger.wire("Closing connection to %s" % self.peer)
			if self.io:
				self.io.close()
		except KeyboardInterrupt,e:
			raise e
		except:
			pass
