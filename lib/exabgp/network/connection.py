# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

#import os
#import sys
import struct
import time
import socket
#import fcntl
import errno
import select
#import array

from exabgp.environment import load

from exabgp.utils import hexa,trace
from exabgp.structure.address import AFI
from exabgp.message import Failure

from exabgp.log import Logger,LazyFormat
logger = Logger()

# If the OS tells us we have data on the socket, we should never have to wait more than READ_TIMEOUT to be able to read it.
# However real life says that on some OS we do ... So let the user control this value
READ_TIMEOUT = load().tcp.timeout

errno_block = set((
	errno.EINPROGRESS, errno.EALREADY,
	errno.EAGAIN, errno.EWOULDBLOCK,
	errno.EINTR, errno.EDEADLK,
))

errno_fatal = set((
	errno.EBADF, errno.ECONNRESET,
	errno.ENOTCONN, errno.ESHUTDOWN,
	errno.ECONNABORTED, errno.EPIPE,
))

class Connection (object):
	def __init__ (self,peer,local,md5,ttl):
		self.io = None
		self.last_read = 0
		self.last_write = 0
		self.peer = peer
		self._loop_start = None

		logger.wire("Opening connection to %s" % self.peer)

		if peer.afi != local.afi:
			raise Failure('The local IP and peer IP must be of the same family (both IPv4 or both IPv6)')

		try:
			if peer.afi == AFI.ipv4:
				self.io = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
			if peer.afi == AFI.ipv6:
				self.io = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)
			try:
				self.io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			except AttributeError:
				pass
			try:
				self.io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
			except AttributeError:
				pass
			try:
				# diable Nagle's algorithm (no grouping of packets)
				self.io.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
			except AttributeError:
				logger.warning("wire","Could not disable nagle's algorithm for %s" % self.peer,'network')
				pass
			self.io.settimeout(1)
			if peer.afi == AFI.ipv4:
				self.io.bind((local.ip,0))
			if peer.afi == AFI.ipv6:
				self.io.bind((local.ip,0,0,0))
		except socket.error,e:
			self.close()
			raise Failure('Could not bind to local ip %s - %s' % (local.ip,str(e)))

		if md5:
			try:
				TCP_MD5SIG = 14
				TCP_MD5SIG_MAXKEYLEN = 80
				SS_PADSIZE = 120

				n_addr = socket.inet_aton(peer.ip)
				n_port = socket.htons(179)
				tcp_md5sig = 'HH4s%dx2xH4x%ds' % (SS_PADSIZE, TCP_MD5SIG_MAXKEYLEN)
				md5sig = struct.pack(tcp_md5sig, socket.AF_INET, n_port, n_addr, len(md5), md5)
				self.io.setsockopt(socket.IPPROTO_TCP, TCP_MD5SIG, md5sig)
			except socket.error,e:
				self.close()
				raise Failure('This OS does not support TCP_MD5SIG, you can not use MD5 : %s' % str(e))

		# None (ttl-security unset) or zero (maximum TTL) is the same thing
		if ttl:
			try:
				self.io.setsockopt(socket.IPPROTO_IP,socket.IP_TTL, 20)
			except socket.error,e:
				self.close()
				raise Failure('This OS does not support IP_TTL (ttl-security), you can not use MD5 : %s' % str(e))

		try:
			if peer.afi == AFI.ipv4:
				self.io.connect((peer.ip,179))
			if peer.afi == AFI.ipv6:
				self.io.connect((peer.ip,179,0,0))
			self.io.setblocking(0)
		except socket.error, e:
			self.close()
			raise Failure('Could not connect to peer (if you use MD5, check your passwords): %s' % str(e))

		try:
			try:
				# Linux / Windows
				self.message_size = self.io.getsockopt(socket.SOL_SOCKET, socket.SO_MAX_MSG_SIZE)
			except AttributeError:
				# BSD
				self.message_size = self.io.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
		except socket.error, e:
			self.message_size = None

	def pending (self,reset=False):
		if reset:
			self._loop_start = None
		else:
			if not self._loop_start:
				self._loop_start = time.time()
			else:
				if self._loop_start + READ_TIMEOUT < time.time():
					raise Failure('Waited for data on a socket for more than %d second(s)' % READ_TIMEOUT)
		try:
			r,_,_ = select.select([self.io,],[],[],0)
		except select.error,e:
			errno,message = e.args
			if errno in errno_block:
				return False
			raise
		if r: return True
		return False

	def ready (self):
		try:
			_,w,_ = select.select([],[self.io,],[],0)
		except select.error,e:
			errno,message = e.args
			if errno in errno_block:
				return False
			raise
		if not w: return False
		return True

	def read (self,number):
		if not self.io:
			raise Failure('Trying to read on a close TCP conncetion')
		if number == 0: return ''
		try:
			r = self.io.recv(number)
			self.last_read = time.time()
			logger.wire(LazyFormat("%15s RECV " % self.peer,hexa,r))
			return r
		except socket.timeout,e:
			self.close()
			raise Failure('Timeout while reading data from the network:  %s ' % str(e))
		except socket.error,e:
			self.close()
			raise Failure('Problem while reading data from the network:  %s ' % str(e))

	def write (self,data):
		if not self.io:
			# We alrady returned a Failure
			# It must be a write attempted during the closing of the peering session
			# Make sure it does not hold the cleanup.
			return True
		if not self.ready():
			return False
		try:
			logger.wire(LazyFormat("%15s SENT " % self.peer,hexa,data))
			# we can not use sendall as in case of network buffer filling
			# it does raise and does not let you know how much was sent
			while data:
				try:
					sent = self.io.send(data)
					data = data[sent:]
				except socket.error,e:
					if e.args[0] in errno_block:
						logger.wire("%15s BACKING OFF as writing on socket failed with errno EAGAIN" % self.peer)
						time.sleep(0.01)
						continue
					else:
						raise e
			#self.io.sendall(data)
			self.last_write = time.time()
			return True
		except socket.error, e:
			# Must never happen as we are performing a select before the write
			#failure = getattr(e,'errno',None)
			#if failure in errno_block:
			#	return False
			self.close()
			logger.wire("%15s %s" % (self.peer,trace()))
			raise Failure('Problem while writing data to the network: %s' % str(e))

	def close (self):
		try:
			logger.wire("Closing connection to %s" % self.peer)
			if self.io:
				self.io.close()
		except socket.error:
			pass

