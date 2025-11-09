
"""listener.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import uuid
import copy
import socket

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI

# from exabgp.util.coroutine import each
from exabgp.reactor.peer import Peer
from exabgp.reactor.network.tcp import md5
from exabgp.reactor.network.tcp import min_ttl
from exabgp.reactor.network.error import error
from exabgp.reactor.network.error import errno
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.network.error import BindingError
from exabgp.reactor.network.error import AcceptError
from exabgp.reactor.network.incoming import Incoming

from exabgp.bgp.message.open.routerid import RouterID

from exabgp.logger import log


class Listener:
    _family_AFI_map = {
        socket.AF_INET: AFI.ipv4,
        socket.AF_INET6: AFI.ipv6,
    }

    def __init__(self, reactor, backlog=200):
        self.serving = False

        self._reactor = reactor
        self._backlog = backlog
        self._sockets = {}
        self._accepted = {}

    def _new_socket(self, ip):
        if ip.afi == AFI.ipv6:
            return socket.socket(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        if ip.afi == AFI.ipv4:
            return socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        raise NetworkError(f'Can not create socket for listening, family of IP {ip} is unknown')

    def _listen(self, local_ip, peer_ip, local_port, use_md5, md5_base64, ttl_in):
        self.serving = True

        for sock, (local, port, peer, md) in self._sockets.items():
            if local_ip.top() != local:
                continue
            if local_port != port:
                continue
            md5(sock, peer_ip.top(), 0, use_md5, md5_base64)
            if ttl_in:
                min_ttl(sock, peer_ip, ttl_in)
            return

        try:
            sock = self._new_socket(local_ip)
            # MD5 must match the peer side of the TCP, not the local one
            md5(sock, peer_ip.top(), 0, md5, md5_base64)
            if ttl_in:
                min_ttl(sock, peer_ip, ttl_in)
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
                    f'could not listen on {local_ip}:{local_port}, the port may already be in use by another application'
                ) from None
            elif exc.args[0] == errno.EADDRNOTAVAIL:
                raise BindingError(f'could not listen on {local_ip}:{local_port}, this is an invalid address') from None
            raise NetworkError(str(exc)) from None
        except NetworkError as exc:
            log.critical(lambda exc=exc: str(exc), 'network')
            raise exc

    def listen_on(self, local_addr, remote_addr, port, md5_password, md5_base64, ttl_in):
        try:
            if not remote_addr:
                remote_addr = IP.create('0.0.0.0') if local_addr.ipv4() else IP.create('::')
            self._listen(local_addr, remote_addr, port, md5_password, md5_base64, ttl_in)
            md5_suffix = ' with MD5' if md5_password else ''
            log.debug(
                f'listening for BGP session(s) on {local_addr}:{port}{md5_suffix}',
                'network',
            )
            return True
        except NetworkError as exc:
            if os.geteuid() != 0 and port <= 1024:
                log.critical(
                    f'can not bind to {local_addr}:{port}, you may need to run ExaBGP as root', 'network'
                )
            else:
                log.critical(lambda exc=exc: f'can not bind to {local_addr}:{port} ({exc})', 'network')
            log.critical(lambda: 'unset exabgp.tcp.bind if you do not want listen for incoming connections', 'network')
            log.critical(lambda: f'and check that no other daemon is already binding to port {port}', 'network')
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
                log.critical(lambda exc=exc: str(exc), 'network')

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
                    raise AcceptError(f'unexpected address family ({sock.family})')
                fam = self._family_AFI_map[sock.family]
                yield Incoming(fam, remote_ip, local_ip, io)
        except NetworkError as exc:
            log.critical(lambda exc=exc: str(exc), 'network')

    def new_connections(self):
        if not self.serving:
            return
        yield None

        reactor = self._reactor
        ranged_neighbor = []

        for connection in self._connected():
            log.debug(lambda connection=connection: f'new connection received {connection.name()}', 'network')
            for key in reactor.peers():
                neighbor = reactor.neighbor(key)

                connection_local = IP.create(connection.local).address()
                neighbor_peer_start = neighbor['peer-address'].address()
                neighbor_peer_next = neighbor_peer_start + neighbor.range_size

                if not neighbor_peer_start <= connection_local < neighbor_peer_next:
                    continue

                connection_peer = IP.create(connection.peer).address()
                neighbor_local = neighbor['local-address'].address()

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
                    log.debug(lambda connection=connection: f'refused connection from {connection.name()} due to the state machine', 'network')
                    break
                log.debug(lambda connection=connection: f'accepted connection from {connection.name()}', 'network')
                break
            else:
                # we did not break (and nothign was found/done or we have group match)
                matched = len(ranged_neighbor)
                if matched > 1:
                    log.debug(
                        f'could not accept connection from {connection.name()} (more than one neighbor match)',
                        'network',
                    )
                    reactor.asynchronous.schedule(
                        str(uuid.uuid1()),
                        'sending notification (6,5)',
                        connection.notification(6, 5, 'could not accept the connection (more than one neighbor match)'),
                    )
                    return
                if not matched:
                    log.debug(lambda connection=connection: f'no session configured for {connection.name()}', 'network')
                    reactor.asynchronous.schedule(
                        str(uuid.uuid1()),
                        'sending notification (6,3)',
                        connection.notification(6, 3, 'no session configured for the peer'),
                    )
                    return

                new_neighbor = copy.copy(ranged_neighbor[0])
                new_neighbor.range_size = 1
                new_neighbor.generated = True
                new_neighbor['local-address'] = IP.create(connection.peer)
                new_neighbor['peer-address'] = IP.create(connection.local)
                if not new_neighbor['router-id']:
                    new_neighbor['router-id'] = RouterID.create(connection.local)

                new_peer = Peer(new_neighbor, reactor)
                denied = new_peer.handle_connection(connection)
                if denied:
                    log.debug(lambda connection=connection: f'refused connection from {connection.name()} due to the state machine', 'network')
                    return

                reactor.register_peer(new_neighbor.name(), new_peer)
                return

    def stop(self):
        if not self.serving:
            return

        for sock, (ip, port, _, _) in self._sockets.items():
            sock.close()
            log.info(lambda ip=ip, port=port: f'stopped listening on {ip}:{port}', 'network')

        self._sockets = {}
        self.serving = False
