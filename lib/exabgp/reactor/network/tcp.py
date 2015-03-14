# encoding: utf-8
"""
tcp.py

Created by Thomas Mangin on 2013-07-13.
Copyright (c) 2013-2015 Exa Networks. All rights reserved.
"""

import time
import socket
import select
import platform

from struct import pack,calcsize

from exabgp.util.errstr import errstr

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.reactor.network.error import errno
from exabgp.reactor.network.error import error

from exabgp.reactor.network.error import NotConnected
from exabgp.reactor.network.error import BindingError
from exabgp.reactor.network.error import MD5Error
from exabgp.reactor.network.error import NagleError
from exabgp.reactor.network.error import TTLError
from exabgp.reactor.network.error import AsyncError

from exabgp.logger import Logger


def create (afi):
	try:
		if afi == AFI.ipv4:
			io = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
		if afi == AFI.ipv6:
			io = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)
		try:
			io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		except (socket.error,AttributeError):
			pass
		try:
			io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # pylint: disable=E1101
		except (socket.error,AttributeError):
			pass
	except socket.error:
		raise NotConnected('Could not create socket')
	return io


def bind (io, ip, afi):
	try:
		if afi == AFI.ipv4:
			io.bind((ip,0))
		if afi == AFI.ipv6:
			io.bind((ip,0,0,0))
	except socket.error,exc:
		raise BindingError('Could not bind to local ip %s - %s' % (ip,str(exc)))


def connect (io, ip, port, afi, md5):
	try:
		if afi == AFI.ipv4:
			io.connect((ip,port))
		if afi == AFI.ipv6:
			io.connect((ip,port,0,0))
	except socket.error,exc:
		if exc.errno == errno.EINPROGRESS:
			return
		if md5:
			raise NotConnected('Could not connect to peer %s:%d, check your MD5 password (%s)' % (ip,port,errstr(exc)))
		raise NotConnected('Could not connect to peer %s:%d (%s)' % (ip,port,errstr(exc)))


# http://lxr.free-electrons.com/source/include/uapi/linux/tcp.h#L197
#
# #define TCP_MD5SIG_MAXKEYLEN    80
#
# struct tcp_md5sig {
# 	struct __kernel_sockaddr_storage tcpm_addr;     /* address associated */  128
# 	__u16   __tcpm_pad1;                            /* zero */                  2
# 	__u16   tcpm_keylen;                            /* key length */            2
# 	__u32   __tcpm_pad2;                            /* zero */                  4
# 	__u8    tcpm_key[TCP_MD5SIG_MAXKEYLEN];         /* key (binary) */         80
# }
#
# #define _K_SS_MAXSIZE   128
#
# #define _K_SS_ALIGNSIZE (__alignof__ (struct sockaddr *))
# /* Implementation specific desired alignment */
#
# typedef unsigned short __kernel_sa_family_t;
#
# struct __kernel_sockaddr_storage {
# 	__kernel_sa_family_t    ss_family;              /* address family */
# 	/* Following field(s) are implementation specific */
# 	char    __data[_K_SS_MAXSIZE - sizeof(unsigned short)];
# 	/* space to achieve desired size, */
# 	/* _SS_MAXSIZE value minus size of ss_family */
# } __attribute__ ((aligned(_K_SS_ALIGNSIZE)));   /* force desired alignment */

def MD5 (io, ip, port, md5):
	if md5:
		os = platform.system()
		if os == 'FreeBSD':
			if md5 != 'kernel':
				raise MD5Error(
					'FreeBSD requires that you set your MD5 key via ipsec.conf.\n'
					'Something like:\n'
					'flush;\n'
					'add <local ip> <peer ip> tcp 0x1000 -A tcp-md5 "password";'
					)
			try:
				TCP_MD5SIG = 0x10
				io.setsockopt(socket.IPPROTO_TCP, TCP_MD5SIG, 1)
			except socket.error:
				raise MD5Error(
					'FreeBSD requires that you rebuild your kernel to enable TCP MD5 Signatures:\n'
					'options         IPSEC\n'
					'options         TCP_SIGNATURE\n'
					'device          crypto\n'
				)
		elif os == 'Linux':
			try:
				# __kernel_sockaddr_storage
				n_af   = IP.toaf(ip)
				n_addr = IP.pton(ip)
				n_port = socket.htons(port)

				# pack 'x' is padding, so we want the struct
				# Do not use '!' for the pack, the network (big) endian switch in
				# struct.pack is fighting against inet_pton and htons (note the n)

				if IP.toafi(ip) == AFI.ipv4:
					# SS_MAXSIZE is 128 but addr_family, port and ipaddr (8 bytes total) are written independently of the padding
					SS_MAXSIZE_PADDING = 128 - calcsize('HH4s')  # 8
					sockaddr = pack('HH4s%dx' % SS_MAXSIZE_PADDING, socket.AF_INET, n_port, n_addr)
				else:
					SS_MAXSIZE_PADDING = 128 - calcsize('HI16sI')  # 28
					SIN6_FLOWINFO = 0
					SIN6_SCOPE_ID = 0
					sockaddr = pack('HHI16sI%dx' % SS_MAXSIZE_PADDING, n_af, n_port, SIN6_FLOWINFO, n_addr, SIN6_SCOPE_ID)

				TCP_MD5SIG_MAXKEYLEN = 80
				key = pack('2xH4x%ds' % TCP_MD5SIG_MAXKEYLEN, len(md5), md5)

				TCP_MD5SIG = 14
				io.setsockopt(socket.IPPROTO_TCP, TCP_MD5SIG, sockaddr + key)
			except socket.error,exc:
				raise MD5Error('This linux machine does not support TCP_MD5SIG, you can not use MD5 (%s)' % errstr(exc))
		else:
			raise MD5Error('ExaBGP has no MD5 support for %s' % os)


def nagle (io, ip):
	try:
		# diable Nagle's algorithm (no grouping of packets)
		io.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
	except (socket.error,AttributeError):
		raise NagleError("Could not disable nagle's algorithm for %s" % ip)


def TTL (io, ip, ttl):
	# None (ttl-security unset) or zero (maximum TTL) is the same thing
	if ttl:
		try:
			io.setsockopt(socket.IPPROTO_IP,socket.IP_TTL, 20)
		except socket.error,exc:
			raise TTLError('This OS does not support IP_TTL (ttl-security) for %s (%s)' % (ip,errstr(exc)))


def async (io, ip):
	try:
		io.setblocking(0)
	except socket.error,exc:
		raise AsyncError('could not set socket non-blocking for %s (%s)' % (ip,errstr(exc)))


def ready (io):
	logger = Logger()
	warned = False
	start = time.time()

	while True:
		try:
			_,w,_ = select.select([],[io,],[],0)
			if not w:
				if not warned and time.time()-start > 1.0:
					logger.network('attempting to accept connections, socket not ready','warning')
					warned = True
				yield False
				continue
			err = io.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
			if not err:
				if warned:
					logger.network('incoming socket ready','warning')
				yield True
				return
			elif err in error.block:
				logger.network('connect attempt failed, retrying, reason %s' % errno.errorcode[err],'warning')
				yield False
			else:
				yield False
				return
		except select.error:
			yield False
			return
