#!/usr/bin/env python
# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2013-02-20.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import os

import pwd
import socket
import select
import errno
import asyncore

from struct import unpack

from exabgp.structure.api import JSON
from exabgp.bgp.message.update import Update

from exabgp.bmp.header import Header
from exabgp.bmp.message import Message
from exabgp.bmp.negotiated import FakeNegotiated

class BMPHandler (asyncore.dispatcher_with_send):
	wire = False
	update = True

	def announce (self,*args):
		print self.ip, self.port, ' '.join(str(_) for _ in args) if len(args) > 1 else args[0]

	def setup (self,ip,port):
		self.handle = {
			Message.ROUTE_MONITORING : self._route,
			Message.STATISTICS_REPORT : self._statistics,
			Message.PEER_DOWN_NOTIFICATION : self._peer,
		}
		self.ip = ip
		self.port = port
		self.json = JSON('2.0')
		return self

	def _read_data (self,number):
		header = ''
		left = number
		while left:
			try:
				r,_,_ = select.select([self], [], [], 1.0)
			except select.error,e:
				return None

			if not r:
				continue

			try:
				data = self.recv(left)
			except socket.error, e:
				if e.args[0] in (errno.EWOULDBLOCK,errno.EAGAIN):
					continue
				raise e

			left -= len(data)
			header += data

			if left and not data:
				# the TCP session is gone.
				self.announce("TCP connection closed")
				self.close()
				return None
		return header

	def handle_read (self):
		header = Header(self._read_data(44))
		if not header.validate():
			print "closeing tcp connection following an invalid header"
			self.close()
		self.handle[header.message](header)

		# for h in dir(header):
		# 	if h.startswith('_'):
		# 		continue
		# 	print h, getattr(header,h)

	def _route (self,header):
		bgp_header = self._read_data(19)
		length = unpack('!H',bgp_header[16:18])[0] - 19
		bgp_body = self._read_data(length)

		asn4 = True
		negotiated = FakeNegotiated(header,asn4)
		update = Update().factory(negotiated,bgp_body)
		if False:
			for route in update.routes:
				print 'decoded route %s' % route.extensive(),'parser'
		else:
			print self.json.update(update.routes)

	def _statistics (self,header):
		pass

	def _peer (self,header):
		pass

class BMPServer(asyncore.dispatcher):
	def __init__(self, host, port):
		asyncore.dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.set_reuse_addr()
		self.bind((host, port))
		self.listen(5)

	def handle_accept(self):
		pair = self.accept()
		if pair is not None:
			sock, addr = pair
			print "new BGP connection from", addr
			handler = BMPHandler(sock).setup(*addr)

def drop ():
	uid = os.getuid()
	gid = os.getgid()

	if uid and gid:
		return

	for name in ['nobody',]:
		try:
			user = pwd.getpwnam(name)
			nuid = int(user.pw_uid)
			ngid = int(user.pw_uid)
		except KeyError:
			pass

	if not gid:
		os.setgid(ngid)
	if not uid:
		os.setuid(nuid)

server = BMPServer('localhost', 1790)
drop()

from exabgp.structure.environment import load
env = load('')

try:
	asyncore.loop()
except:
	pass
