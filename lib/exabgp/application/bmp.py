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

from exabgp.version import version

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

		try:
			self.handle[header.message](header)
		except Exception,e:
			# Yep, this is not yet production quality code ..
			import pdb; pdb.set_trace()
			pass

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

from exabgp.structure.environment import environment

environment.configuration = {
	'pdb' : {
		'enable'        : (environment.boolean,environment.lower,'false',    'on program fault, start pdb the python interactive debugger'),
	},
# 	'daemon' : {
# #		'identifier'    : (environment.unquote,environment.nop,'ExaBGP',     'a name for the log (to diferenciate multiple instances more easily)'),
# 		'pid'           : (environment.unquote,environment.quote,'',         'where to save the pid if we manage it'),
# 		'user'          : (environment.user,environment.quote,'nobody',      'user to run as'),
# 		'daemonize'     : (environment.boolean,environment.lower,'false',    'should we run in the background'),
# 	},
	'log' : {
		'enable'        : (environment.boolean,environment.lower,'true',     'enable logging'),
		'level'         : (environment.syslog_value,environment.syslog_name,'INFO', 'log message with at least the priority SYSLOG.<level>'),
		'destination'   : (environment.unquote,environment.quote,'stdout', 'where logging should log\n' \
		                  '                                  syslog (or no setting) sends the data to the local syslog syslog\n' \
		                  '                                  host:<location> sends the data to a remote syslog server\n' \
		                  '                                  stdout sends the data to stdout\n' \
		                  '                                  stderr sends the data to stderr\n' \
		                  '                                  <filename> send the data to a file' \
		),
		'all'           : (environment.boolean,environment.lower,'false',    'report debug information for everything'),
		'configuration' : (environment.boolean,environment.lower,'false',    'report command parsing'),
		'supervisor'    : (environment.boolean,environment.lower,'true',     'report signal received, command reload'),
		'daemon'        : (environment.boolean,environment.lower,'true',     'report pid change, forking, ...'),
		'processes'     : (environment.boolean,environment.lower,'true',     'report handling of forked processes'),
		'network'       : (environment.boolean,environment.lower,'true',     'report networking information (TCP/IP, network state,...)'),
		'packets'       : (environment.boolean,environment.lower,'false',    'report BGP packets sent and received'),
		'rib'           : (environment.boolean,environment.lower,'false',    'report change in locally configured routes'),
		'message'       : (environment.boolean,environment.lower,'false',    'report changes in route announcement on config reload'),
		'timers'        : (environment.boolean,environment.lower,'false',    'report keepalives timers'),
		'routes'        : (environment.boolean,environment.lower,'false',    'report received routes'),
		'parser'        : (environment.boolean,environment.lower,'false',    'report BGP message parsing details'),
		'short'         : (environment.boolean,environment.lower,'false',    'use short log format (not prepended with time,level,pid and source)'),
	},
	'cache' : {
		'attributes'  :  (environment.boolean,environment.lower,'true', 'cache routes attributes (configuration and wire) for faster parsing'),
		'nexthops'    :  (environment.boolean,environment.lower,'true', 'cache routes next-hops'),
	},
	# 'api' : {
	# 	'encoder'  :  (environment.api,environment.lower,'text', '(experimental) encoder to use with with external API (text or json)'),
	# },
	# Here for internal use
	'internal' : {
		'name'    : (environment.nop,environment.nop,'ExaBMP', 'name'),
		'version' : (environment.nop,environment.nop,version,  'version'),
	},
	# # Here for internal use
	# 'debug' : {
	# 	'memory' : (environment.boolean,environment.lower,'false','command line option --memory'),
	# },
}

env = environment.setup('')

try:
	asyncore.loop()
except:
	pass
