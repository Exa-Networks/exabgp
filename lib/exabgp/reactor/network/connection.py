# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time
import random
import socket
import select
from struct import unpack

from exabgp.configuration.environment import environment

from exabgp.util.od import od
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
			self.defensive = environment.settings().debug.defensive
			self.logger = Logger()
		except RuntimeError:
			self.read_timeout = 1
			self.defensive = True
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
			self.logger.network("%s connection to %s closed" % (self.name(),self.peer),'info')
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
		# The function must not be called if it does not return with no data with a smaller size as parameter
		if not self.io:
			self.close()
			raise NotConnected('Trying to read on a close TCP conncetion')
		if number == 0:
			yield ''
			return
		# XXX: one of the socket option is to recover the size of the buffer
		# XXX: we could use it to not have to put together the string with multiple reads
		# XXX: and get rid of the self.read_timeout option
		while not self.reading():
			yield ''
		data = ''
		while True:
			try:
				while True:
					if self._reading is None:
						self._reading = time.time()
					elif time.time() > self._reading + self.read_timeout:
						self.close()
						self.logger.wire("%s %s peer is too slow (we were told there was data on the socket but we can not read up to what should be there)" % (self.name(),self.peer))
						raise TooSlowError('Waited to read for data on a socket for more than %d second(s)' % self.read_timeout)

					if self.defensive and random.randint(0,2):
						raise socket.error(errno.EAGAIN,'raising network error in purpose')

					read = self.io.recv(number)
					if not read:
						self.close()
						self.logger.wire("%s %s lost TCP session with peer" % (self.name(),self.peer))
						raise LostConnection('the TCP connection was closed by the remote end')

					data += read
					number -= len(read)
					if not number:
						self.logger.wire(LazyFormat("%s %-32s RECEIVED " % (self.name(),'%s / %s' % (self.local,self.peer)),od,read))
						self._reading = None
						yield data
						return
			except socket.timeout,e:
				self.close()
				self.logger.wire("%s %s peer is too slow" % (self.name(),self.peer))
				raise TooSlowError('Timeout while reading data from the network (%s)' % errstr(e))
			except socket.error,e:
				if e.args[0] in error.block:
					self.logger.wire("%s %s blocking io problem mid-way through reading a message %s, trying to complete" % (self.name(),self.peer,errstr(e)),'debug')
				elif e.args[0] in error.fatal:
					self.close()
					raise LostConnection('issue reading on the socket: %s' % errstr(e))
				# what error could it be !
				else:
					self.logger.wire("%s %s undefined error reading on socket" % (self.name(),self.peer))
					raise NetworkError('Problem while reading data from the network (%s)' % errstr(e))

	def writer (self,data):
		if not self.io:
			# XXX: FIXME: Make sure it does not hold the cleanup during the closing of the peering session
			yield True
			return
		while not self.writing():
			yield False
		self.logger.wire(LazyFormat("%s %-32s SENDING " % (self.name(),'%s / %s' % (self.local,self.peer)),od,data))
		# The first while is here to setup the try/catch block once as it is very expensive
		while True:
			try:
				while True:
					if self._writing is None:
						self._writing = time.time()
					elif time.time() > self._writing + self.read_timeout:
						self.close()
						self.logger.wire("%s %s peer is too slow" % (self.name(),self.peer))
						raise TooSlowError('Waited to write for data on a socket for more than %d second(s)' % self.read_timeout)

					if self.defensive and random.randint(0,2):
						raise socket.error(errno.EAGAIN,'raising network error in purpose')

					# we can not use sendall as in case of network buffer filling
					# it does raise and does not let you know how much was sent
					nb = self.io.send(data)
					if not nb:
						self.close()
						self.logger.wire("%s %s lost TCP connection with peer" % (self.name(),self.peer))
						raise LostConnection('lost the TCP connection')

					data = data[nb:]
					if not data:
						self._writing = None
						yield True
						return
					yield False
			except socket.error,e:
				if e.args[0] in error.block:
					self.logger.wire("%s %s blocking io problem mid-way through writing a message %s, trying to complete" % (self.name(),self.peer,errstr(e)),'debug')
					yield False
				elif e.errno == errno.EPIPE:
					# The TCP connection is gone.
					self.close()
					raise NetworkError('Broken TCP connection')
				elif e.args[0] in error.fatal:
					self.close()
					self.logger.wire("%s %s problem sending message (%s)" % (self.name(),self.peer,errstr(e)))
					raise NetworkError('Problem while writing data to the network (%s)' % errstr(e))
				# what error could it be !
				else:
					self.logger.wire("%s %s undefined error writing on socket" % (self.name(),self.peer))
					yield False

	def reader (self):
		# _reader returns the whole number requested or nothing and then stops
		for header in self._reader(Message.HEADER_LEN):
			if not header:
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

		number = length - Message.HEADER_LEN

		if not number:
			yield length,msg,header,''
			return

		for body in self._reader(number):
			if not body:
				yield 0,0,'',''

		yield length,msg,header,body
