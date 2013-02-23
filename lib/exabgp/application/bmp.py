#!/usr/bin/env python

import os
import sys

import pwd
import socket
import select
import errno
import asyncore

from struct import unpack

def dump (value):
	def spaced (value):
		even = None
		for v in value:
			if even is False:
				yield ' '
			yield '%02X' % ord(v)
			even = not even
	return ''.join(spaced(value))

class MessageType (int):
	ROUTE_MONITORING = 0
	STATISTICS_REPORT = 1
	PEER_DOWN_NOTIFICATION = 2

	_str = {
		0 : 'route monitoring', 
		1 : 'statistics report',
		2 : 'peer down notification',
	}

	def __str__ (self):
		return self._str.get(self,'unknow %d' % self)

class PeerType (int):
	_str = {
		0 : 'global', 
		1 : 'L3 VPN',
	}

	def __str__ (self):
		return self._str.get(self,'unknow %d' % self)

class PeerFlag (int):
	_v4v6 = 0b10000000

	def ipv4 (self):
		return not self & self._v4v6

	def ipv6 (self):
		return bool(self & self._v4v6)

stat = {
	0: "prefixes rejected by inbound policy",
	1: "(known) duplicate prefix advertisements",
	2: "(known) duplicate withdraws",
	3: "updates invalidated due to CLUSTER_LIST loop",
	4: "updates invalidated due to AS_PATH loop",
}

peer = {
	1: "Local system closed session, notification sent",
	2: "Local system closed session, no notification",
	3: "Remote system closed session, notification sent",
	4: "Remote system closed session, no notification",
}


class Header (object):
	def __init__ (self,data):
		self.version = ord(data[0])
		self.msg_type = MessageType(ord(data[1]))
		self.peer_type = PeerType(ord(data[2]))
		self.peer_flag = PeerFlag(ord(data[3]))
		self.peer_distinguisher = unpack('!L',data[4:8])[0]
		if self.peer_flag.ipv4(): self.peer_address = socket.inet_ntop(socket.AF_INET, data[24:28])
		if self.peer_flag.ipv6(): self.peer_address = peer_address = socket.inet_ntop(socket.AF_INET6, data[12:28])
		self.peer_as = unpack('!L',data[28:32])[0]
		self.peer_id = socket.inet_ntop(socket.AF_INET, data[32:36])
		self.time_sec = unpack('!L',data[36:40])[0]
		self.time_micro_sec = unpack('!L',data[40:44])[0]

	def validate (self):
		if self.version != 1: return False
		if self.msg_type not in (0,1,2): return False
		if self.peer_type not in (0,1): return False
		return True

class BMPHandler (asyncore.dispatcher_with_send):
	wire = False
	update = True

	def announce (self,*args):
		print self.ip, self.port, ' '.join(str(_) for _ in args) if len(args) > 1 else args[0]

	def setup (self,ip,port):
		self.handle = {
			MessageType.ROUTE_MONITORING : self._route,
			MessageType.STATISTICS_REPORT : self._statistics,
			MessageType.PEER_DOWN_NOTIFICATION : self._peer,
		}
		self.ip = ip
		self.port = port
		return self

	def _read_data (self,number):
		header = ''
		left = number
		while left:
			try:
				r,_,_ = select.select([self], [], [], 1.0)
			except select.error,e:
				raise KeyboardInterrupt('SIGNAL received in select')
				
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
				import pdb; pdb.set_trace()
				# the TCP session is gone.
				self.announce("TCP connection closed")
				self.close()
				return None
		return header

	def handle_read (self):
		header = Header(self._read_data(44))
		if not header.validate():
			print "invalid header"
			self.close()

		for h in dir(header):
			if h.startswith('_'):
				continue
			print h, getattr(header,h)

		self.handle[header.msg_type](header)

	def _route (self,header):
		bgp_header = self._read_data(19)
		length = unpack('!H',bgp_header[16:18])[0] - 19
		print "length",length
		bgp_body = self._read_data(length)
		print dump(bgp_header)
		print dump(bgp_body)

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
try:
	asyncore.loop()
except:
	pass