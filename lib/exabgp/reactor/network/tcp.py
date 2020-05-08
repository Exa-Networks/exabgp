# encoding: utf-8
"""
tcp.py

Created by Thomas Mangin on 2013-07-13.
Copyright (c) 2013-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import re
import base64
import socket
import select
import platform

from struct import pack, calcsize

from exabgp.util import bytes_ascii
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


def create(afi):
    try:
        if afi == AFI.ipv4:
            io = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        if afi == AFI.ipv6:
            io = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        try:
            io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except (socket.error, AttributeError):
            pass
        try:
            io.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # pylint: disable=E1101
        except (socket.error, AttributeError):
            pass
    except socket.error:
        raise NotConnected('Could not create socket')
    return io


def bind(io, ip, afi):
    try:
        if afi == AFI.ipv4:
            io.bind((ip, 0))
        if afi == AFI.ipv6:
            io.bind((ip, 0, 0, 0))
    except socket.error as exc:
        raise BindingError('Could not bind to local ip %s - %s' % (ip, str(exc)))


def connect(io, ip, port, afi, md5):
    try:
        if afi == AFI.ipv4:
            io.connect((ip, port))
        if afi == AFI.ipv6:
            io.connect((ip, port, 0, 0))
    except socket.error as exc:
        if exc.errno == errno.EINPROGRESS:
            return
        if md5:
            raise NotConnected(
                'Could not connect to peer %s:%d, check your MD5 password (%s)' % (ip, port, errstr(exc))
            )
        raise NotConnected('Could not connect to peer %s:%d (%s)' % (ip, port, errstr(exc)))


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


def MD5(io, ip, port, md5, md5_base64):
    platform_os = platform.system()
    if platform_os == 'FreeBSD':
        if md5:
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
    elif platform_os == 'Linux':
        try:
            md5_bytes = None
            if md5:
                if md5_base64 is True:
                    try:
                        md5_bytes = base64.b64decode(md5)
                    except TypeError:
                        raise MD5Error("Failed to decode base 64 encoded PSK")
                elif md5_base64 is None and not re.match('.*[^a-f0-9].*', md5):  # auto
                    options = [md5 + '==', md5 + '=', md5]
                    for md5 in options:
                        try:
                            md5_bytes = base64.b64decode(md5)
                            break
                        except TypeError:
                            pass

            # __kernel_sockaddr_storage
            n_af = IP.toaf(ip)
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
            TCP_MD5SIG = 14

            if md5_bytes:
                key = pack('2xH4x%ds' % TCP_MD5SIG_MAXKEYLEN, len(md5_bytes), md5_bytes)
                io.setsockopt(socket.IPPROTO_TCP, TCP_MD5SIG, sockaddr + key)
            elif md5:
                md5_bytes = bytes_ascii(md5)
                key = pack('2xH4x%ds' % TCP_MD5SIG_MAXKEYLEN, len(md5_bytes), md5_bytes)
                io.setsockopt(socket.IPPROTO_TCP, TCP_MD5SIG, sockaddr + key)
            # else:
            # 	key = pack('2xH4x%ds' % TCP_MD5SIG_MAXKEYLEN, 0, b'')
            # 	io.setsockopt(socket.IPPROTO_TCP, TCP_MD5SIG, sockaddr + key)

        except socket.error as exc:
            if exc.errno != errno.ENOENT:
                raise MD5Error('This linux machine does not support TCP_MD5SIG, you can not use MD5 (%s)' % errstr(exc))
    elif md5:
        raise MD5Error('ExaBGP has no MD5 support for %s' % platform_os)


def nagle(io, ip):
    try:
        # diable Nagle's algorithm (no grouping of packets)
        io.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except (socket.error, AttributeError):
        raise NagleError("Could not disable nagle's algorithm for %s" % ip)


def TTL(io, ip, ttl):
    # None (ttl-security unset) or zero (maximum TTL) is the same thing
    if ttl:
        try:
            io.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
        except socket.error as exc:
            raise TTLError('This OS does not support IP_TTL (ttl-security) for %s (%s)' % (ip, errstr(exc)))


def TTLv6(io, ip, ttl):
    if ttl:
        try:
            io.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_UNICAST_HOPS, ttl)
        except socket.error as exc:
            raise TTLError('This OS does not support unicast_hops (ttl-security) for %s (%s)' % (ip, errstr(exc)))


def MIN_TTL(io, ip, ttl):
    # None (ttl-security unset) or zero (maximum TTL) is the same thing
    if ttl:
        try:
            io.setsockopt(socket.IPPROTO_IP, socket.IP_MINTTL, ttl)
        except socket.error as exc:
            raise TTLError('This OS does not support IP_MINTTL (ttl-security) for %s (%s)' % (ip, errstr(exc)))
        except AttributeError:
            pass

        try:
            io.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
        except socket.error as exc:
            raise TTLError(
                'This OS does not support IP_MINTTL or IP_TTL (ttl-security) for %s (%s)' % (ip, errstr(exc))
            )


def asynchronous(io, ip):
    try:
        io.setblocking(0)
    except socket.error as exc:
        raise AsyncError('could not set socket non-blocking for %s (%s)' % (ip, errstr(exc)))


def ready(io):
    logger = Logger()

    poller = select.poll()
    poller.register(io, select.POLLOUT | select.POLLNVAL | select.POLLERR)

    found = False

    while True:
        try:
            for _, event in poller.poll(0):
                if event & select.POLLOUT or event & select.POLLIN:
                    found = True
                elif event & select.POLLHUP:
                    yield False, 'could not connect, retrying'
                    return
                elif event & select.POLLERR or event & select.POLLNVAL:
                    yield False, 'connect attempt failed, issue with reading on the network, retrying'
                    return

            if found:
                err = io.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if not err:
                    yield True, 'connection established'
                    return
                elif err in error.block:
                    yield False, 'connect attempt failed, retrying, reason %s' % errno.errorcode[err]
                    return
            yield False, 'waiting for socket to become ready'
        except select.error as err:
            yield False, 'error, retrying %s' % str(err)
            return
