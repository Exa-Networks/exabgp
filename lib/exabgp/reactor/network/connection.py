# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time
import socket
import select
from struct import unpack

from exabgp.configuration.environment import environment

from exabgp.util.od import od
from exabgp.util.trace import trace
from exabgp.util.errstr import errstr

from exabgp.logger import Logger,FakeLogger,LazyFormat

from exabgp.bgp.message import Message

from exabgp.reactor.network.error import error,errno,NetworkError,TooSlowError,NotConnected,LostConnection,NotifyError

from .error import *

class Connection (object):
	direction = 'undefined'
	identifier = 0

	def __init__ (self,afi,peer,local):
		# peer and local are strings of the IP

		# If the OS tells us we have data on the socket, we should never have to wait more than read_timeout to be able to read it.
		# However real life says that on some OS we do ... So let the user control this value
		try:
			self.read_timeout = environment.settings().tcp.timeout
			self.logger = Logger()
		except RuntimeError:
			self.logger = FakeLogger
			self.read_timeout = 1
			self.logger = FakeLogger()

		self.afi = afi
		self.peer = peer
		self.local = local

		self._reading = None
		self._writing = None
		self._buffer = ''
		self.io = None
		self.established = False

		self.identifier += 1
		self.id = self.identifier

	# Just in case ..
	def __del__ (self):
		if self.io:
			self.logger.critical("%s FIX ! connection to %s was not explicitely closed, closed by GC" % (self.name(),self.peer))
			self.close()

	def name (self):
		return "session %d %s" % (self.id,self.direction)

	def close (self):
		try:
			self.logger.wire("%s, closing connection from %s to %s" % (self.name(),self.local,self.peer))
			if self.io:
				self.io.close()
				self.io = None
		except KeyboardInterrupt,e:
			raise e
		except:
			pass

	def reading (self):
		while True:
			try:
				r,_,_ = select.select([self.io,],[],[],0)
			except select.error,e:
				if e.args[0] not in error.block:
					self.close()
					self.logger.wire("%s %s errno %s on socket" % (self.name(),self.peer,errno.errorcode[e.args[0]]))
					raise NetworkError('errno %s on socket' % errno.errorcode[e.args[0]])
				return False

			if r:
				self._reading = time.time()
			return r != []

	def writing (self):
		while True:
			try:
				_,w,_ = select.select([],[self.io,],[],0)
			except select.error,e:
				if e.args[0] not in error.block:
					self.close()
					self.logger.wire("%s %s errno %s on socket" % (self.name(),self.peer,errno.errorcode[e.args[0]]))
					raise NetworkError('errno %s on socket' % errno.errorcode[e.args[0]])
				return False

			if w:
				self._writing = time.time()
			return w != []

	def _reader (self,number):
		if not self.io:
			self.close()
			raise NotConnected('Trying to read on a close TCP conncetion')
		if number == 0:
			yield ''
			return
		while not self.reading():
			yield ''
		try:
			read = ''
			while number:
				if self._reading is None:
					self._reading = time.time()
				elif time.time() > self._reading + self.read_timeout:
					self.close()
					self.logger.wire("%s %s peer is too slow" % (self.name(),self.peer))
					raise TooSlowError('Waited for data on a socket for more than %d second(s)' % self.read_timeout)
				read = self.io.recv(number)
				number -= len(read)
				if not read:
					self.close()
					self.logger.wire("%s %s lost TCP session with peer" % (self.name(),self.peer))
					raise LostConnection('the TCP connection was closed by the remote end')
				yield read
			self.logger.wire(LazyFormat("%s %-32s RECEIVED " % (self.name(),'%s / %s' % (self.local,self.peer)),od,read))
			self._reading = None
		except socket.timeout,e:
			self.close()
			self.logger.wire("%s %s peer is too slow" % (self.name(),self.peer))
			raise TooSlowError('Timeout while reading data from the network (%s)' % errstr(e))
		except socket.error,e:
			self.close()
			self.logger.wire("%s %s undefined error on socket" % (self.name(),self.peer))
			if e.args[0] == errno.EPIPE:
				raise LostConnection('issue reading on the socket: %s' % errstr(e))
			raise NetworkError('Problem while reading data from the network (%s)' % errstr(e))

	def writer (self,data):
		if not self.io:
			# XXX: FIXME: Make sure it does not hold the cleanup during the closing of the peering session
			yield True
			return
		if not self.writing():
			yield False
			return
		try:
			self.logger.wire(LazyFormat("%s %-32s SENDING " % (self.name(),'%s / %s' % (self.local,self.peer)),od,data))
			# we can not use sendall as in case of network buffer filling
			# it does raise and does not let you know how much was sent
			sent = 0
			length = len(data)
			while sent < length:
				if self._writing is None:
					self._writing = time.time()
				elif time.time() > self._writing + self.read_timeout:
					self.close()
					self.logger.wire("%s %s peer is too slow" % (self.name(),self.peer))
					raise TooSlowError('Waited for data on a socket for more than %d second(s)' % self.read_timeout)
				try:
					nb = self.io.send(data[sent:])
					if not nb:
						self.close()
						self.logger.wire("%s %s lost TCP connection with peer" % (self.name(),self.peer))
						raise LostConnection('lost the TCP connection')
					sent += nb
					yield False
				except socket.error,e:
					if e.args[0] not in error.block:
						self.logger.wire("%s %s problem sending message (%s)" % (self.name(),self.peer,errstr(e)))
						raise NetworkError('Problem while reading data from the network (%s)' % errstr(e))
					if sent == 0:
						self.logger.wire("%s %s problem sending message, will retry later (%s)" % (self.name(),self.peer,errstr(e)))
						yield False
					else:
						self.logger.wire("%s %s blocking io problem mid-way sending through a message, trying to complete" % (self.name(),self.peer))
						yield False
			self._writing = None
			yield True
			return
		except socket.error, e:
			# Must never happen as we are performing a select before the write
			#failure = getattr(e,'errno',None)
			#if failure in error.block:
			#	return False
			self.close()
			self.logger.wire("%s %s %s" % (self.name(),self.peer,trace()))
			if e.errno == errno.EPIPE:
				# The TCP connection is gone.
				raise NetworkError('Broken TCP connection')
			else:
				raise NetworkError('Problem while writing data to the network (%s)' % errstr(e))

	def reader (self):
		header = ''
		for part in self._reader(Message.HEADER_LEN):
			header += part
			if len(header) != Message.HEADER_LEN:
				yield 0,0,'',''

		if not header.startswith(Message.MARKER):
			raise NotifyError(1,1,'The packet received does not contain a BGP marker')

		msg = ord(header[18])
		length = unpack('!H',header[16:18])[0]

		if length < Message.HEADER_LEN or length > Message.MAX_LEN:
			raise NotifyError(1,2,'%s has an invalid message length of %d' %(Message().name(msg),length))

		validator = Message.Length.get(msg,lambda _ : _ >= 19)
		if not validator(length):
			# MUST send the faulty msg_length back
			raise NotifyError(1,2,'%s has an invalid message length of %d' %(Message().name(msg),msg_length))

		body = ''
		number = length - Message.HEADER_LEN
		for part in self._reader(number):
			body += part
			if len(body) != number:
				yield 0,0,'',''

		yield length,msg,header,body
