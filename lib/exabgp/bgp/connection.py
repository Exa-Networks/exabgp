# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

#import os
#import sys
import platform
import struct
import time
import socket
#import fcntl
import errno
import select
#import array

from exabgp.structure.environment import environment

from exabgp.structure.utils import dump,trace
from exabgp.protocol.family import AFI
from exabgp.bgp.message import Failure

from exabgp.structure.log import Logger,LazyFormat

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

# we could not connect to the peer
class NotConnected (Exception):
	pass

class Connection (object):
	def __init__ (self,peer,local,md5,ttl):
		# If the OS tells us we have data on the socket, we should never have to wait more than READ_TIMEOUT to be able to read it.
		# However real life says that on some OS we do ... So let the user control this value
		self.READ_TIMEOUT = environment.settings().tcp.timeout

		self.logger = Logger()
		self.io = None
		self.peer = peer
		self._loop_start = None

		self.logger.wire("Opening connection to %s" % self.peer)

		if peer.afi != local.afi:
			raise NotConnected('The local IP and peer IP must be of the same family (both IPv4 or both IPv6)')

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
				self.logger.warning("wire","Could not disable nagle's algorithm for %s" % self.peer,'network')
				pass
			self.io.settimeout(1)
			if peer.afi == AFI.ipv4:
				self.io.bind((local.ip,0))
			if peer.afi == AFI.ipv6:
				self.io.bind((local.ip,0,0,0))
		except socket.error,e:
			self.close()
			raise NotConnected('Could not bind to local ip %s - %s' % (local.ip,str(e)))

		if md5:
			os = platform.system()
			if os == 'FreeBSD':
				if md5 != 'kernel':
					raise NotConnected(
						'FreeBSD requires that you set your MD5 key via ipsec.conf.\n'
						'Something like:\n'
						'flush;\n'
						'add <local ip> <peer ip> tcp 0x1000 -A tcp-md5 "password";'
						)
				try:
					TCP_MD5SIG = 0x10
					self.io.setsockopt(socket.IPPROTO_TCP, TCP_MD5SIG, 1)
				except socket.error,e:
					self.close()
					raise NotConnected(
						'FreeBSD requires that you rebuild your kernel to enable TCP MD5 Signatures:\n'
						'options         IPSEC\n'
						'options         TCP_SIGNATURE\n'
						'device          crypto\n'
					)
			elif os == 'Linux':
				try:
					TCP_MD5SIG = 14
					TCP_MD5SIG_MAXKEYLEN = 80

					n_port = socket.htons(179)
					if peer.afi == AFI.ipv4:
						SS_PADSIZE = 120
						n_addr = socket.inet_pton(socket.AF_INET, peer.ip)
						tcp_md5sig = 'HH4s%dx2xH4x%ds' % (SS_PADSIZE, TCP_MD5SIG_MAXKEYLEN)
						md5sig = struct.pack(tcp_md5sig, socket.AF_INET, n_port, n_addr, len(md5), md5)
					if peer.afi == AFI.ipv6:
						SS_PADSIZE = 100
						SIN6_FLOWINFO = 0
						SIN6_SCOPE_ID = 0
						n_addr = socket.inet_pton(socket.AF_INET6, peer.ip)
						tcp_md5sig = 'HHI16sI%dx2xH4x%ds' % (SS_PADSIZE, TCP_MD5SIG_MAXKEYLEN)
						md5sig = struct.pack(tcp_md5sig, socket.AF_INET6, n_port, SIN6_FLOWINFO, n_addr, SIN6_SCOPE_ID, len(md5), md5)
					self.io.setsockopt(socket.IPPROTO_TCP, TCP_MD5SIG, md5sig)
				except socket.error,e:
					self.close()
					raise NotConnected('This linux machine does not support TCP_MD5SIG, you can not use MD5 : %s' % str(e))
			else:
				raise NotConnected('ExaBGP has no MD5 support for %s' % os)

		# None (ttl-security unset) or zero (maximum TTL) is the same thing
		if ttl:
			try:
				self.io.setsockopt(socket.IPPROTO_IP,socket.IP_TTL, 20)
			except socket.error,e:
				self.close()
				raise NotConnected('This OS does not support IP_TTL (ttl-security), you can not use MD5 : %s' % str(e))

		try:
			if peer.afi == AFI.ipv4:
				self.io.connect((peer.ip,179))
			if peer.afi == AFI.ipv6:
				self.io.connect((peer.ip,179,0,0))
			self.io.setblocking(0)
		except socket.error, e:
			self.close()
			raise NotConnected('Could not connect to peer (if you use MD5, check your passwords): %s' % str(e))

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
				if self._loop_start + self.READ_TIMEOUT < time.time():
					raise Failure('Waited for data on a socket for more than %d second(s)' % self.READ_TIMEOUT)
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
			if not r:
				# The socket was closed - no data is available anymore (the caller will call .close() on us)
				raise Failure('The TCP connection is closed')
			self.logger.wire(LazyFormat("Peer %15s RECV " % self.peer,dump,r))
			return r
		except socket.timeout,e:
			self.close()
			raise Failure('Timeout while reading data from the network:  %s ' % str(e))
		except socket.error,e:
			self.close()
			raise Failure('Problem while reading data from the network:  %s ' % str(e))

	def write (self,data):
		if not self.io:
			# We already returned a Failure
			# It must be a write attempted during the closing of the peering session
			# Make sure it does not hold the cleanup.
			return True
		if not self.ready():
			return False
		try:
			self.logger.wire(LazyFormat("Peer %15s SENT " % self.peer,dump,data))
			# we can not use sendall as in case of network buffer filling
			# it does raise and does not let you know how much was sent
			sent = 0
			length = len(data)
			while sent < length:
				try:
					nb = self.io.send(data[sent:])
					if not nb:
						self.logger.wire("%15s lost TCP session with peer" % self.peer)
						raise Failure('lost TCP session')
					sent += nb
				except socket.error,e:
					if e.args[0] in errno_block:
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
			#if failure in errno_block:
			#	return False
			self.close()
			self.logger.wire("%15s %s" % (self.peer,trace()))
			raise Failure('Problem while writing data to the network: %s' % str(e))

	def close (self):
		try:
			self.logger.wire("Closing connection to %s" % self.peer)
			if self.io:
				self.io.close()
		except socket.error:
			pass
