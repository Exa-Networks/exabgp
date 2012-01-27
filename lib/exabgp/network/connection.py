#!/usr/bin/env python
# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import os
import sys
import struct
import time
import socket
import fcntl
import errno
import select
import array

from exabgp.utils import hexa,trace
from exabgp.structure.address import AFI
from exabgp.message import Failure

from exabgp.log import Logger,LazyFormat
logger = Logger()

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
		self.last_read = 0
		self.last_write = 0
		self.peer = peer

		self._buffer = []

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
				logger.warning("wire","Could not diable nagle's algorithm for %s" % self.peer)
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

	def pending (self):
		try:
			r,_,_ = select.select([self.io,],[],[],0)
		except select.error,e:
			if getattr(e,'errno',None) in errno_block:
				return False
			raise
		if r: return True
		return False

	def ready (self):
		try:
			_,w,_ = select.select([],[self.io,],[],0)
		except select.error,e:
			if getattr(e,'errno',None) in errno_block:
				return False
			raise
		if w: return True
		return False

	def read (self,number):
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
		if not self.ready():
			return False
		try:
			logger.wire(LazyFormat("%15s SENT " % self.peer,hexa,data))
			self.io.sendall(data)
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
			self.io.close()
		except socket.error:
			pass

