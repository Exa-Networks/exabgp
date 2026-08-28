"""listener.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import uuid
import copy
import socket
from typing import ClassVar, Generator, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor
    from exabgp.bgp.neighbor import Neighbor

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI

# from exabgp.util.coroutine import each
from exabgp.reactor.peer import Peer
from exabgp.reactor.network.tcp import md5
from exabgp.reactor.network.tcp import bind_to_device
from exabgp.reactor.network.tcp import min_ttl
from exabgp.reactor.network.tcp import min_ttlv6
from exabgp.reactor.network.error import error
from exabgp.reactor.network.error import errno
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.network.error import BindingError
from exabgp.reactor.network.error import AcceptError
from exabgp.reactor.network.incoming import Incoming

from exabgp.bgp.message.open.routerid import RouterID

from exabgp.logger import log, lazymsg

# Network port constants
MAX_PRIVILEGED_PORT: int = 1024  # Highest privileged port number (requires root on Unix)


def _bind_error(exc: OSError, local_ip: IP, local_port: int) -> NetworkError:
    """Name why a listening socket could not bind, so the log does not have to guess."""
    where = f'could not listen on {local_ip}:{local_port}'
    if exc.args[0] == errno.EADDRINUSE:
        return BindingError(f'{where}, the port may already be in use by another application')
    if exc.args[0] == errno.EADDRNOTAVAIL:
        return BindingError(f'{where}, this is an invalid address')
    if exc.args[0] == errno.EACCES:
        return BindingError(f'{where}, binding below port {MAX_PRIVILEGED_PORT} requires root')
    return NetworkError(str(exc))


class Listener:
    _family_AFI_map: ClassVar[dict[socket.AddressFamily, AFI]] = {
        socket.AF_INET: AFI.ipv4,
        socket.AF_INET6: AFI.ipv6,
    }

    # Singleton for stopped listener (initialized after class definition)
    STOPPED: ClassVar['Listener']

    @classmethod
    def _create_stopped(cls) -> 'Listener':
        """Create the STOPPED sentinel. Called once at module load."""
        instance = object.__new__(cls)
        instance.serving = False
        instance._sockets = {}
        instance._accepted = {}
        return instance

    def __init__(self, reactor: 'Reactor', backlog: int = 200) -> None:
        self.serving: bool = False

        self._reactor: 'Reactor' = reactor
        self._backlog: int = backlog
        self._sockets: dict[socket.socket, tuple[str, int, str, str | None, str]] = {}
        self._accepted: dict[socket.socket, socket.socket] = {}

    def _new_socket(self, ip: IP, source_interface: str = '') -> socket.socket:
        if ip.afi == AFI.ipv6:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        elif ip.afi == AFI.ipv4:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        else:
            raise NetworkError(f'Can not create socket for listening, family of IP {ip} is unknown')

        # A link-local address can not be bound until the socket names a link, and
        # the kernel must be told before bind(), not after.
        if source_interface:
            bind_to_device(sock, source_interface)
        return sock

    def _listen(
        self,
        local_ip: IP,
        peer_ip: IP,
        local_port: int,
        use_md5: str | None,
        md5_base64: bool,
        ttl_in: int | None,
        tcp_ao_keyid: int | None = None,
        tcp_ao_algorithm: str = '',
        tcp_ao_password: str = '',
        tcp_ao_base64: bool = False,
        source_interface: str = '',
    ) -> None:
        from exabgp.reactor.network.tcp import tcp_ao

        self.serving = True

        for sock, (local, port, peer, md, interface) in self._sockets.items():
            if local_ip.top() != local:
                continue
            if local_port != port:
                continue
            if source_interface != interface:
                continue
            # unconditional: an empty key clears a password removed by a reload (#1388)
            md5(sock, peer_ip.top(), 0, use_md5 or '', md5_base64)
            # TCP-AO (mutually exclusive with MD5)
            if tcp_ao_password and tcp_ao_keyid is not None:
                tcp_ao(sock, peer_ip.top(), 0, tcp_ao_password, tcp_ao_keyid, tcp_ao_algorithm, tcp_ao_base64)
            if ttl_in:
                if local_ip.ipv6():
                    min_ttlv6(sock, peer_ip.top(), ttl_in)
                else:
                    min_ttl(sock, peer_ip.top(), ttl_in)
            return

        try:
            sock = self._new_socket(local_ip, source_interface)
            # MD5 must match the peer side of the TCP, not the local one
            if use_md5:
                md5(sock, peer_ip.top(), 0, use_md5, md5_base64)
            # TCP-AO (mutually exclusive with MD5)
            if tcp_ao_password and tcp_ao_keyid is not None:
                tcp_ao(sock, peer_ip.top(), 0, tcp_ao_password, tcp_ao_keyid, tcp_ao_algorithm, tcp_ao_base64)
            if ttl_in:
                if local_ip.ipv6():
                    min_ttlv6(sock, peer_ip.top(), ttl_in)
                else:
                    min_ttl(sock, peer_ip.top(), ttl_in)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if local_ip.ipv6():
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            except (OSError, AttributeError):
                pass
            sock.setblocking(False)
            # s.settimeout(0.0)
            sock.bind((local_ip.top(), local_port))
            sock.listen(self._backlog)
            self._sockets[sock] = (local_ip.top(), local_port, peer_ip.top(), use_md5, source_interface)
        except OSError as exc:
            raise _bind_error(exc, local_ip, local_port) from None
        except NetworkError as exc:
            log.critical(lazymsg('{exc}', exc=str(exc)), 'network')
            raise exc

    def listen_on(
        self,
        local_addr: IP,
        remote_addr: IP | None,
        port: int,
        md5_password: str | None,
        md5_base64: bool,
        ttl_in: int | None,
        tcp_ao_keyid: int | None = None,
        tcp_ao_algorithm: str = '',
        tcp_ao_password: str = '',
        tcp_ao_base64: bool = False,
        source_interface: str = '',
    ) -> bool:
        try:
            if not remote_addr:
                remote_addr = IP.from_string('0.0.0.0') if local_addr.ipv4() else IP.from_string('::')
            self._listen(
                local_addr,
                remote_addr,
                port,
                md5_password,
                md5_base64,
                ttl_in,
                tcp_ao_keyid,
                tcp_ao_algorithm,
                tcp_ao_password,
                tcp_ao_base64,
                source_interface,
            )
            auth_type = 'tcp-ao' if tcp_ao_password else ('md5' if md5_password else 'none')
            log.debug(
                lazymsg(
                    'listener.started ip={addr} port={port} auth={auth}', addr=local_addr, port=port, auth=auth_type
                ),
                'network',
            )
            return True
        except NetworkError as exc:
            # the reason is the only line which is never a guess, so always print it:
            # a privileged port is one way to fail to listen, an MD5 key the kernel
            # will not install is another, and they need different answers
            log.critical(
                lazymsg('bind.failed ip={addr} port={port} reason={exc}', addr=local_addr, port=port, exc=exc),
                'network',
            )
            log.critical(lazymsg('listener.bind.hint action=unset_tcp_bind'), 'network')
            log.critical(lazymsg('listener.bind.hint action=check_port port={port}', port=port), 'network')
            return False

    def incoming(self) -> bool:
        if not self.serving:
            return False

        peer_connected: bool = False

        for sock in self._sockets:
            if sock in self._accepted:
                continue
            try:
                io, _ = sock.accept()
                self._accepted[sock] = io
                peer_connected = True
            except OSError as exc:
                if exc.errno in error.block:
                    continue
                log.critical(lazymsg('{exc}', exc=str(exc)), 'network')

        return peer_connected

    def _connected(self) -> Generator[Incoming, None, None]:
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
            log.critical(lazymsg('{exc}', exc=str(exc)), 'network')

    def new_connections(self) -> Generator[None, None, None]:
        if not self.serving:
            return
        yield None

        reactor: Reactor = self._reactor
        ranged_neighbor: list[Neighbor] = []

        for connection in self._connected():
            log.debug(lazymsg('new connection received {name}', name=connection.name()), 'network')
            for key in reactor.peers():
                neighbor = reactor.neighbor(key)
                if neighbor is None:
                    continue

                connection_local = IP.from_string(connection.local).address()
                assert neighbor.session.peer_address is not None  # Configured neighbors must have peer_address
                neighbor_peer_start = neighbor.session.peer_address.address()
                neighbor_peer_next = neighbor_peer_start + neighbor.range_size

                if not neighbor_peer_start <= connection_local < neighbor_peer_next:
                    continue

                connection_peer = IP.from_string(connection.peer).address()
                assert neighbor.session.local_address is not None  # Configured neighbors must have local_address
                neighbor_local = neighbor.session.local_address.address()

                if connection_peer != neighbor_local:
                    if not neighbor.session.auto_discovery:
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
                    log.debug(
                        lazymsg('refused connection from {name} due to the state machine', name=connection.name()),
                        'network',
                    )
                    break
                log.debug(lazymsg('accepted connection from {name}', name=connection.name()), 'network')
                break
            else:
                # we did not break (and nothign was found/done or we have group match)
                matched = len(ranged_neighbor)
                if matched > 1:
                    log.debug(
                        lazymsg(
                            'connection.rejected name={name} reason=multiple_neighbor_match', name=connection.name()
                        ),
                        'network',
                    )
                    reactor.asynchronous.schedule(
                        str(uuid.uuid1()),
                        'sending notification (6,5)',
                        connection.notification(
                            6, 5, b'could not accept the connection (more than one neighbor match)'
                        ),
                    )
                    return
                if not matched:
                    log.debug(lazymsg('no session configured for {name}', name=connection.name()), 'network')
                    reactor.asynchronous.schedule(
                        str(uuid.uuid1()),
                        'sending notification (6,3)',
                        connection.notification(6, 3, b'no session configured for the peer'),
                    )
                    return

                new_neighbor = copy.copy(ranged_neighbor[0])
                new_neighbor.range_size = 1
                new_neighbor.ephemeral = True
                new_neighbor.session.local_address = IP.from_string(connection.peer)
                new_neighbor.session.peer_address = IP.from_string(connection.local)
                if not new_neighbor.session.router_id:
                    new_neighbor.session.router_id = RouterID(connection.local)

                new_peer = Peer(new_neighbor, reactor)
                denied = new_peer.handle_connection(connection)
                if denied:
                    log.debug(
                        lazymsg('refused connection from {name} due to the state machine', name=connection.name()),
                        'network',
                    )
                    return

                reactor.register_peer(new_neighbor.name(), new_peer)
                return

    def stop(self) -> None:
        if not self.serving:
            return

        for sock, (ip, port, _, _, _) in self._sockets.items():
            sock.close()
            log.info(lazymsg('stopped listening on {ip}:{port}', ip=ip, port=port), 'network')

        self._sockets = {}
        self.serving = False


# Initialize the STOPPED singleton
Listener.STOPPED = Listener._create_stopped()
