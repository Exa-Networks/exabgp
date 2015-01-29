#!/usr/bin/env python
# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2013-02-20.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import sys

import pwd
import socket
import select
import asyncore

from struct import unpack

from exabgp.reactor.network.error import error
from exabgp.reactor.api.encoding import JSON
from exabgp.bgp.message.update import Update

from exabgp.bmp.header import Header
from exabgp.bmp.message import Message
from exabgp.bmp.negotiated import FakeNegotiated


class BMPHandler (asyncore.dispatcher_with_send):
	wire = False
	update = True

	def announce (self, *args):
		print >> self.fd, self.ip, self.port, ' '.join(str(_) for _ in args) if len(args) > 1 else args[0]

	def setup (self, env, ip, port):
		self.handle = {
			Message.ROUTE_MONITORING:       self._route,
			Message.STATISTICS_REPORT:      self._statistics,
			Message.PEER_DOWN_NOTIFICATION: self._peer,
		}
		self.asn4 = env.bmp.asn4
		self.use_json = env.bmp.json
		self.fd = env.fd
		self.ip = ip
		self.port = port
		self.json = JSON('3.4.8')
		return self

	def _read_data (self, number):
		header = ''
		left = number
		while left:
			try:
				r,_,_ = select.select([self], [], [], 1.0)
			except select.error:
				return None

			if not r:
				continue

			try:
				data = self.recv(left)
			except socket.error,exc:
				if exc.args[0] in error.block:
					continue
				print "problem reading on socket", str(exc)
				return None

			left -= len(data)
			header += data

			if left and not data:
				# the TCP session is gone.
				print "TCP connection closed"
				self.close()
				return None
		return header

	def handle_read (self):
		data = self._read_data(44)
		if data is None:
			self.close()
			return
		header = Header(data)
		if not header.validate():
			print "closeing tcp connection following an invalid header"
			self.close()

		self.handle[header.message](header)

	def _route (self, header):
		bgp_header = self._read_data(19)
		if bgp_header is None:
			self.close()
			return
		length = unpack('!H',bgp_header[16:18])[0] - 19
		bgp_body = self._read_data(length)
		if bgp_body is None:
			self.close()
			return

		negotiated = FakeNegotiated(header,self.asn4)
		update = Update.unpack_message(bgp_body,negotiated)
		if self.use_json:
			print >> self.fd, self.json.bmp(self.ip,update)
		else:
			for route in update.routes:
				print >> self.fd, route.extensive()

	def _statistics (self, header):
		pass

	def _peer (self, header):
		pass


class BMPServer(asyncore.dispatcher):
	def __init__ (self, env):
		self.env = env
		host = env.bmp.host
		port = env.bmp.port
		asyncore.dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.set_reuse_addr()
		self.bind((host, port))
		self.listen(5)

	def handle_accept (self):
		pair = self.accept()
		if pair is not None:
			# The if prevent invalid unpacking
			sock, addr = pair  # pylint: disable=W0633
			print "new BGP connection from", addr
			BMPHandler(sock).setup(self.env,*addr)


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


from exabgp.configuration.environment import environment

_SPACE = {
	'space': ' '*33
}

HELP_STDOUT = """\
where logging should log
%(space)s syslog (or no setting) sends the data to the local syslog syslog
%(space)s host:<location> sends the data to a remote syslog server
%(space)s stdout sends the data to stdout
%(space)s stderr sends the data to stderr
%(space)s <filename> send the data to a file""" % _SPACE


environment.application = 'exabmp'
environment.configuration = {
	'pdb': {
		'enable': {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'on program fault, start pdb the python interactive debugger',
		},
	},
	'bmp': {
		'host': {
			'read':  environment.nop,
			'write': environment.nop,
			'value': 'localhost',
			'help':  'port for the daemon to listen on',
		},
		'port': {
			'read':  environment.integer,
			'write': environment.nop,
			'value': '1790',
			'help': 'port for the daemon to listen on',
		},
		'asn4': {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'are the route received by bmp in RFC4893 format',
		},
		'json': {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'use json encoding of parsed route',
		},
	},
	'log': {
		'enable':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'enable logging',
		},
		'level':  {
			'read':  environment.syslog_value,
			'write': environment.syslog_name,
			'value': 'INFO',
			'help':  'log message with at least the priority SYSLOG.<level>',
		},
		'destination':  {
			'read':  environment.unquote,
			'write': environment.quote,
			'value': 'stdout',
			'help':  HELP_STDOUT,
		},
		'all':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report debug information for everything',
		},
		'configuration':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report command parsing',
		},
		'reactor':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report signal received, command reload',
		},
		'daemon':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report pid change, forking, ...',
		},
		'processes':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report handling of forked processes',
		},
		'network':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'report networking information (TCP/IP, network state,...)',
		},
		'packets':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report BGP packets sent and received',
		},
		'rib':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report change in locally configured routes',
		},
		'message':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report changes in route announcement on config reload',
		},
		'timers':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report keepalives timers',
		},
		'routes':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report received routes',
		},
		'parser':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'report BGP message parsing details',
		},
		'short':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'false',
			'help':  'use short log format (not prepended with time,level,pid and source)',
		},
	},
	'cache': {
		'attributes':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'cache all attributes (configuration and wire) for faster parsing',
		},
		'nexthops':  {
			'read':  environment.boolean,
			'write': environment.lower,
			'value': 'true',
			'help':  'cache routes next-hops (deprecated: next-hops are always cached)',
		},
	},
}

env = environment.setup('')


def main ():
	try:
		os.dup2(2,3)
		env.fd = os.fdopen(3, "w+")
	except Exception:
		print "can not setup a descriptor of FD 3 for route display"
		sys.exit(1)

	BMPServer(env)
	drop()

	try:
		asyncore.loop()
	except Exception:
		pass


if __name__ == '__main__':
	main()
