#!/usr/bin/env python
# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""
import sys
import traceback

import time
import struct
import socket
import select

from bgp.structure.message import Failure

class Network (object):
	
	def __init__ (self,peer,local,asn=''):
		self.last_read = 0
		self.last_write = 0
		self.peer = peer
		self.asn = asn
		
		if peer.version != local.version:
			raise Failure('The local IP and peer IP must be of the same family (both IPv4 or both IPv6)')
		
		try:
			if peer.version == 4:
				self._io = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			if peer.version == 6:
				self._io = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
			try:
				self._io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			except AttributeError:
				pass
			try:
				self._io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
			except AttributeError:
				pass
			self._io.settimeout(1)
			self._io.bind((str(local),-1))
		except socket.error,e:
			self.close()
			raise Failure('could not bind to local ip %s - %s' % (local,str(e)))
		try:
			if peer.version == 4:
				self._io.connect((str(peer),179))
			if peer.version == 6:
				self._io.connect((str(peer),179,0,0))
			self._io.setblocking(0)
		except socket.error, e:
			self.close()
			raise Failure('could not connect to peer: %s' % str(e))
		
	def pending (self):
		r,_,_ = select.select([self._io,],[],[],0)
		return True if r else False

	# File like interface

	def read (self,number):
		if number == 0: return ''
		try:
			r = self._io.recv(number)
			self.last_read = time.time()
			return r
		except socket.error,e:
			self.close()
			# XXX: use Display for the rendering
			traceback.print_exc(file=sys.stdout)
			raise Failure('problem attempting to read data from the network:  %s ' % str(e))

	def write (self,data):
		try:
			r = self._io.send(data)
			self.last_write = time.time()
			return r
		except socket.error, e:
			self.close()
			# XXX: use Display for the rendering
			traceback.print_exc(file=sys.stdout)
			raise Failure('problem attempting to write data to the network: %s' % str(e))

	def close (self):
		try:
			self._io.close()
		except socket.error:
			pass
	
