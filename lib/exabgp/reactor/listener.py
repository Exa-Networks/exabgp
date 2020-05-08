# encoding: utf-8
"""
listener.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import uuid
import copy
import socket

from exabgp.util.errstr import errstr

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI

# from exabgp.util.coroutine import each
from exabgp.reactor.peer import Peer
from exabgp.reactor.network.tcp import MD5
from exabgp.reactor.network.tcp import MIN_TTL
from exabgp.reactor.network.error import error
from exabgp.reactor.network.error import errno
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.network.error import BindingError
from exabgp.reactor.network.error import AcceptError
from exabgp.reactor.network.incoming import Incoming

from exabgp.bgp.message.open.routerid import RouterID

from exabgp.logger import Logger


class Listener(object):
    _family_AFI_map = {
        socket.AF_INET: AFI.ipv4,
        socket.AF_INET6: AFI.ipv6,
    }

    def __init__(self, reactor, backlog=200):
        self.serving = False
        self.logger = Logger()

        self._reactor = reactor
        self._backlog = backlog
        self._sockets = {}
        self._accepted = {}

    def _new_socket(self, ip):
        if ip.afi == AFI.ipv6:
            return socket.socket(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        if ip.afi == AFI.ipv4:
            return socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        raise NetworkError('Can not create socket for listening, family of IP %s is unknown' % ip)

    def _listen(self, local_ip, peer_ip, local_port, md5, md5_base64, ttl_in):
        self.serving = True

        for sock, (local, port, peer, md) in self._sockets.items():
            if local_ip.top() != local:
                continue
            if local_port != port:
                continue
            MD5(sock, peer_ip.top(), 0, md5, md5_base64)
            if ttl_in:
                MIN_TTL(sock, peer_ip, ttl_in)
            return

        try:
            sock = self._new_socket(local_ip)
            # MD5 must match the peer side of the TCP, not the local one
            MD5(sock, peer_ip.top(), 0, md5, md5_base64)
            if ttl_in:
                MIN_TTL(sock, peer_ip, ttl_in)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if local_ip.ipv6():
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            except (socket.error, AttributeError):
                pass
            sock.setblocking(0)
            # s.settimeout(0.0)
            sock.bind((local_ip.top(), local_port))
            sock.listen(self._backlog)
            self._sockets[sock] = (local_ip.top(), local_port, peer_ip.top(), md5)
        except socket.error as exc:
            if exc.args[0] == errno.EADDRINUSE:
                raise BindingError(
                    'could not listen on %s:%d, the port may already be in use by another application'
                    % (local_ip, local_port)
                )
            elif exc.args[0] == errno.EADDRNOTAVAIL:
                raise BindingError('could not listen on %s:%d, this is an invalid address' % (local_ip, local_port))
            raise NetworkError(str(exc))
        except NetworkError as exc:
            self.logger.critical(str(exc), 'network')
            raise exc

    def listen_on(self, local_addr, remote_addr, port, md5_password, md5_base64, ttl_in):
        try:
            if not remote_addr:
                remote_addr = IP.create('0.0.0.0') if local_addr.ipv4() else IP.create('::')
            self._listen(local_addr, remote_addr, port, md5_password, md5_base64, ttl_in)
            self.logger.debug(
                'listening for BGP session(s) on %s:%d%s' % (local_addr, port, ' with MD5' if md5_password else ''),
                'network',
            )
            return True
        except NetworkError as exc:
            if os.geteuid() != 0 and port <= 1024:
                self.logger.critical(
                    'can not bind to %s:%d, you may need to run ExaBGP as root' % (local_addr, port), 'network'
                )
            else:
                self.logger.critical('can not bind to %s:%d (%s)' % (local_addr, port, str(exc)), 'network')
            self.logger.critical('unset exabgp.tcp.bind if you do not want listen for incoming connections', 'network')
            self.logger.critical('and check that no other daemon is already binding to port %d' % port, 'network')
            return False

    def incoming(self):
        if not self.serving:
            return False

        peer_connected = False

        for sock in self._sockets:
            if sock in self._accepted:
                continue
            try:
                io, _ = sock.accept()
                self._accepted[sock] = io
                peer_connected = True
            except socket.error as exc:
                if exc.errno in error.block:
                    continue
                self.logger.critical(str(exc), 'network')

        return peer_connected

    def _connected(self):
        try:
            for sock, io in list(self._accepted.items()):
                del self._accepted[sock]
                if sock.family == socket.AF_INET:
                    local_ip = io.getpeername()[0]  # local_ip,local_port
                    remote_ip = io.getsockname()[0]  # remote_ip,remote_port
                elif sock.family == socket.AF_INET6:
                    local_ip = io.getpeername()[0]  # local_ip,local_port,local_flow,local_scope
                    remote_ip = io.getsockname()[0]  # remote_ip,remote_port,remote_flow,remote_scope
                else:
                    raise AcceptError('unexpected address family (%d)' % sock.family)
                fam = self._family_AFI_map[sock.family]
                yield Incoming(fam, remote_ip, local_ip, io)
        except NetworkError as exc:
            self.logger.critical(str(exc), 'network')

    def new_connections(self):
        if not self.serving:
            return
        yield None

        reactor = self._reactor
        ranged_neighbor = []

        for connection in self._connected():
            self.logger.debug('new connection received %s' % connection.name(), 'network')
            for key in reactor.peers():
                neighbor = reactor.neighbor(key)

                connection_local = IP.create(connection.local).address()
                neighbor_peer_start = neighbor.peer_address.address()
                neighbor_peer_next = neighbor_peer_start + neighbor.range_size

                if not neighbor_peer_start <= connection_local < neighbor_peer_next:
                    continue

                connection_peer = IP.create(connection.peer).address()
                neighbor_local = neighbor.local_address.address()

                if connection_peer != neighbor_local:
                    if not neighbor.auto_discovery:
                        continue

                # we found a range matching for this connection
                # but the peer may already have connected, so
                # we need to iterate all individual peers before
                # handling "range" peers
                if neighbor.range_size > 1:
                    ranged_neighbor.append(neighbor)
                    continue

                denied = reactor.handle_connection(key, connection)
                if denied:
                    self.logger.debug(
                        'refused connection from %s due to the state machine' % connection.name(), 'network'
                    )
                    break
                self.logger.debug('accepted connection from %s' % connection.name(), 'network')
                break
            else:
                # we did not break (and nothign was found/done or we have group match)
                matched = len(ranged_neighbor)
                if matched > 1:
                    self.logger.debug(
                        'could not accept connection from %s (more than one neighbor match)' % connection.name(),
                        'network',
                    )
                    reactor.asynchronous.schedule(
                        str(uuid.uuid1()),
                        'sending notification (6,5)',
                        connection.notification(6, 5, 'could not accept the connection (more than one neighbor match)'),
                    )
                    return
                if not matched:
                    self.logger.debug('no session configured for %s' % connection.name(), 'network')
                    reactor.asynchronous.schedule(
                        str(uuid.uuid1()),
                        'sending notification (6,3)',
                        connection.notification(6, 3, 'no session configured for the peer'),
                    )
                    return

                new_neighbor = copy.copy(ranged_neighbor[0])
                new_neighbor.range_size = 1
                new_neighbor.generated = True
                new_neighbor.local_address = IP.create(connection.peer)
                new_neighbor.peer_address = IP.create(connection.local)
                if not new_neighbor.router_id:
                    new_neighbor.router_id = RouterID.create(connection.local)

                new_peer = Peer(new_neighbor, reactor)
                denied = new_peer.handle_connection(connection)
                if denied:
                    self.logger.debug(
                        'refused connection from %s due to the state machine' % connection.name(), 'network'
                    )
                    return

                reactor.register_peer(new_neighbor.name(), new_peer)
                return

    def stop(self):
        if not self.serving:
            return

        for sock, (ip, port, _, _) in self._sockets.items():
            sock.close()
            self.logger.info('stopped listening on %s:%d' % (ip, port), 'network')

        self._sockets = {}
        self.serving = False
