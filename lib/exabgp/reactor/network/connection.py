# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import random
import socket
import select
from struct import unpack

from exabgp.configuration.environment import environment

from exabgp.util.errstr import errstr

from exabgp.logger import Logger
from exabgp.logger import FakeLogger
from exabgp.logger import LazyFormat

from exabgp.bgp.message import Message

from exabgp.reactor.network.error import error
from exabgp.reactor.network.error import errno
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.network.error import TooSlowError
from exabgp.reactor.network.error import NotConnected
from exabgp.reactor.network.error import LostConnection
from exabgp.reactor.network.error import NotifyError

from .error import *


class Connection (object):
	direction = 'undefined'
	identifier = 0

	def __init__ (self, afi, peer, local):
		# peer and local are strings of the IP

		try:
			self.defensive = environment.settings().debug.defensive
			self.logger = Logger()
		except RuntimeError:
			self.defensive = True
			self.logger = FakeLogger()

		self.afi = afi
		self.peer = peer
		self.local = local

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
		except KeyboardInterrupt,exc:
			raise exc
		except:
			pass

	def reading (self):
		while True:
			try:
				r,_,_ = select.select([self.io,],[],[],0)
			except select.error,exc:
				if exc.args[0] not in error.block:
					self.close()
					self.logger.wire("%s %s errno %s on socket" % (self.name(),self.peer,errno.errorcode[exc.args[0]]))
					raise NetworkError('errno %s on socket' % errno.errorcode[exc.args[0]])
				return False
			return r != []

	def writing (self):
		while True:
			try:
				_,w,_ = select.select([],[self.io,],[],0)
			except select.error,exc:
				if exc.args[0] not in error.block:
					self.close()
					self.logger.wire("%s %s errno %s on socket" % (self.name(),self.peer,errno.errorcode[exc.args[0]]))
					raise NetworkError('errno %s on socket' % errno.errorcode[exc.args[0]])
				return False
			return w != []

	def _reader (self, number):
		# The function must not be called if it does not return with no data with a smaller size as parameter
		if not self.io:
			self.close()
			raise NotConnected('Trying to read on a closed TCP conncetion')
		if number == 0:
			yield ''
			return

		while not self.reading():
			yield ''
		data = ''
		reported = ''
		while True:
			try:
				while True:
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
						self.logger.wire(
							LazyFormat(
								"%s %-32s RECEIVED " % (
									self.name(),
									'%s / %s' % (self.local,self.peer)
								),
								read
							)
						)
						yield data
						return

					yield ''
			except socket.timeout,exc:
				self.close()
				self.logger.wire("%s %s peer is too slow" % (self.name(),self.peer))
				raise TooSlowError('Timeout while reading data from the network (%s)' % errstr(exc))
			except socket.error,exc:
				if exc.args[0] in error.block:
					message = "%s %s blocking io problem mid-way through reading a message %s, trying to complete" % (self.name(),self.peer,errstr(exc))
					if message != reported:
						reported = message
						self.logger.wire(message,'debug')
					yield ''
				elif exc.args[0] in error.fatal:
					self.close()
					raise LostConnection('issue reading on the socket: %s' % errstr(exc))
				# what error could it be !
				else:
					self.logger.wire("%s %s undefined error reading on socket" % (self.name(),self.peer))
					raise NetworkError('Problem while reading data from the network (%s)' % errstr(exc))

	def writer (self, data):
		if not self.io:
			# XXX: FIXME: Make sure it does not hold the cleanup during the closing of the peering session
			yield True
			return
		while not self.writing():
			yield False
		self.logger.wire(LazyFormat("%s %-32s SENDING " % (self.name(),'%s / %s' % (self.local,self.peer)),data))
		# The first while is here to setup the try/catch block once as it is very expensive
		while True:
			try:
				while True:
					if self.defensive and random.randint(0,2):
						raise socket.error(errno.EAGAIN,'raising network error in purpose')

					# we can not use sendall as in case of network buffer filling
					# it does raise and does not let you know how much was sent
					number = self.io.send(data)
					if not number:
						self.close()
						self.logger.wire("%s %s lost TCP connection with peer" % (self.name(),self.peer))
						raise LostConnection('lost the TCP connection')

					data = data[number:]
					if not data:
						yield True
						return
					yield False
			except socket.error,exc:
				if exc.args[0] in error.block:
					self.logger.wire(
						"%s %s blocking io problem mid-way through writing a message %s, trying to complete" % (
							self.name(),
							self.peer,
							errstr(exc)
						),
						'debug'
					)
					yield False
				elif exc.errno == errno.EPIPE:
					# The TCP connection is gone.
					self.close()
					raise NetworkError('Broken TCP connection')
				elif exc.args[0] in error.fatal:
					self.close()
					self.logger.wire("%s %s problem sending message (%s)" % (self.name(),self.peer,errstr(exc)))
					raise NetworkError('Problem while writing data to the network (%s)' % errstr(exc))
				# what error could it be !
				else:
					self.logger.wire("%s %s undefined error writing on socket" % (self.name(),self.peer))
					yield False

	def reader (self):
		# _reader returns the whole number requested or nothing and then stops
		for header in self._reader(Message.HEADER_LEN):
			if not header:
				yield 0,0,'','',None

		if not header.startswith(Message.MARKER):
			report = 'The packet received does not contain a BGP marker'
			yield 0,0,header,'',NotifyError(1,1,report)
			return

		msg = ord(header[18])
		length = unpack('!H',header[16:18])[0]

		if length < Message.HEADER_LEN or length > Message.MAX_LEN:
			report = '%s has an invalid message length of %d' % (Message.CODE.name(msg),length)
			yield length,0,header,'',NotifyError(1,2,report)
			return

		validator = Message.Length.get(msg,lambda _: _ >= 19)
		if not validator(length):
			# MUST send the faulty length back
			report = '%s has an invalid message length of %d' % (Message.CODE.name(msg),length)
			yield length,0,header,'',NotifyError(1,2,report)
			return

		number = length - Message.HEADER_LEN

		if not number:
			yield length,msg,header,'',None
			return

		for body in self._reader(number):
			if not body:
				yield 0,0,'','',None

		yield length,msg,header,body,None
