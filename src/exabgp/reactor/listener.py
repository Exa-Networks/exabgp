"""listener.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import uuid
import copy
import socket
from typing import Any, ClassVar, Generator, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor
    from exabgp.bgp.neighbor import Neighbor

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI

# from exabgp.util.coroutine import each
from exabgp.reactor.peer import Peer
from exabgp.reactor.network.tcp import md5
from exabgp.reactor.network.tcp import bind_to_device
from exabgp.reactor.network.tcp import save_syn
from exabgp.reactor.network.tcp import saved_syn_ttl
from exabgp.reactor.network.tcp import sending_ttl
from exabgp.reactor.network.tcp import set_minimum_ttl
from exabgp.reactor.network.tcp import set_sending_ttl
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


def set_listener_options(sock: Any, ipv6: bool) -> None:
    """Set the two listening socket options, each on its own terms.

    SO_REUSEADDR and IPV6_V6ONLY used to share one try, so a platform refusing the first
    would have silently skipped the second. They are independent requests and are now
    made independently. No supported platform is known to refuse SO_REUSEADDR, and a
    connection which matches no neighbour is closed with NOTIFICATION 6/3 whatever the
    socket accepted, so this is about saying what happened rather than a fault seen.

    Neither is required to bind. SO_REUSEADDR only smooths a restart, and a kernel without
    it still binds; a bind which genuinely cannot happen fails loudly at bind() below. A
    refused IPV6_V6ONLY is worth a line in the log, because it changes which connections
    this socket will accept.
    """
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except (OSError, AttributeError):
        # only affects how quickly a restart can rebind, and bind() reports the real problem
        log.debug(lazymsg('listener.reuseaddr.unavailable'), 'network')

    if not ipv6:
        return

    try:
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    except (OSError, AttributeError):
        log.warning(
            lazymsg(
                'listener.v6only.unavailable reason={reason}',
                reason='this socket may accept IPv4-mapped connections which match no configured neighbor',
            ),
            'network',
        )


def set_accepted_ttl(connection: Incoming, neighbor: Neighbor) -> None:
    """Give an accepted connection the TTL its neighbour's configuration asks us to send with.

    The listening socket is shared by every neighbour on an address and port, so it can
    carry neither a per-neighbour sending TTL nor a per-neighbour minimum (admit_by_ttl).
    Until the neighbour is known that has to wait, and before this nothing set it at all:
    outgoing-ttl was ignored for every session the peer opened.  What happened instead was
    that the listener set IP_TTL to the incoming-ttl minimum, which accepted sockets inherited.
    """
    value = sending_ttl(neighbor.session.outgoing_ttl, neighbor.session.incoming_ttl)
    if value is None or connection.io is None:
        return
    try:
        set_sending_ttl(connection.io, connection.afi, connection.peer, value)
    except NetworkError as exc:
        # the session can still come up, and a peer running GTSM will then drop it, which
        # this line is what explains
        log.error(
            lazymsg(
                'connection.ttl.unset name={name} ttl={ttl} error={error}',
                name=connection.name(),
                ttl=value,
                error=str(exc),
            ),
            'network',
        )


def admit_by_ttl(connection: Incoming, neighbor: Neighbor) -> bool:
    """Apply the neighbour's GTSM minimum to a connection it opened, False if it is dropped.

    RFC 5082 section 3: GTSM MUST NOT drop Trusted or Unknown packets. The listening socket
    is shared by every neighbour on an address, port and interface, so a minimum installed
    there was whichever neighbour set it last: a neighbour without GTSM had its SYNs dropped
    by a minimum it never asked for, and two minimums dropped each other's. And the global
    listener, which every neighbour without `listen` uses, had none, so incoming-ttl was
    not enforced on any session such a peer opened.

    Now the minimum is per neighbour, applied once the connection is matched to one. The
    SYN is checked from the headers the listener asked the kernel to keep (Linux), and the
    minimum is installed on the accepted socket so the kernel checks every later segment.
    Where the SYN was not kept (not Linux, or a kernel before 4.2), the handshake itself is
    not checked: what the peer sends over it, starting with its OPEN, still is wherever the
    kernel has the minimum option, so a Dangerous peer cannot bring a session up there.
    Where it has neither (macOS), min_ttl already warns that nothing arriving is checked.
    """
    minimum = neighbor.session.incoming_ttl
    if not minimum or connection.io is None:
        return True
    arrived = saved_syn_ttl(connection.io)
    if arrived is not None and arrived < minimum:
        log.warning(
            lazymsg(
                'connection.ttl.dropped name={name} ttl={ttl} minimum={minimum}',
                name=connection.name(),
                ttl=arrived,
                minimum=minimum,
            ),
            'network',
        )
        return False
    try:
        set_minimum_ttl(connection.io, connection.afi, connection.peer, minimum)
    except NetworkError as exc:
        # an outgoing session fails the same way when the kernel refuses the minimum: a
        # session we were told to protect is not brought up unprotected
        log.error(
            lazymsg(
                'connection.ttl.minimum.unset name={name} minimum={minimum} error={error}',
                name=connection.name(),
                minimum=minimum,
                error=str(exc),
            ),
            'network',
        )
        return False
    return True


def _matches(neighbor: Neighbor, connection: Incoming) -> bool:
    """Whether the connection is one this neighbor, or its range, is configured for.

    Incoming names the addresses from the remote end: its `local` is the peer's address,
    its `peer` is ours.
    """
    assert neighbor.session.peer_address is not None, 'a configured neighbor has a peer address'
    assert neighbor.session.local_address is not None, 'a configured neighbor has a local address'
    peer_address = IP.from_string(connection.local).address()
    range_start = neighbor.session.peer_address.address()
    if not range_start <= peer_address < range_start + neighbor.range_size:
        return False
    if IP.from_string(connection.peer).address() == neighbor.session.local_address.address():
        return True
    return neighbor.session.auto_discovery


class Listener:
    _family_AFI_map: ClassVar[dict[socket.AddressFamily, AFI]] = {
        socket.AF_INET: AFI.ipv4,
        socket.AF_INET6: AFI.ipv6,
    }

    # Singleton for stopped listener (initialized after class definition)
    STOPPED: ClassVar['Listener']

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
            return

        try:
            sock = self._new_socket(local_ip, source_interface)
            # MD5 must match the peer side of the TCP, not the local one
            if use_md5:
                md5(sock, peer_ip.top(), 0, use_md5, md5_base64)
            # TCP-AO (mutually exclusive with MD5)
            if tcp_ao_password and tcp_ao_keyid is not None:
                tcp_ao(sock, peer_ip.top(), 0, tcp_ao_password, tcp_ao_keyid, tcp_ao_algorithm, tcp_ao_base64)
            # no minimum TTL here: see admit_by_ttl, which checks the SYN this keeps
            save_syn(sock)
            set_listener_options(sock, ipv6=local_ip.ipv6())
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

        for connection in self._connected():
            log.debug(lazymsg('new connection received {name}', name=connection.name()), 'network')
            self._dispatch(connection)

    def _dispatch(self, connection: Incoming) -> None:
        """Give the connection to the neighbor configured for it, or refuse it."""
        reactor: Reactor = self._reactor
        # the ranges this connection falls in, and only this one: a neighbor configured for
        # the address itself is preferred to a range, whatever the order of the peers
        ranged: list[Neighbor] = []

        for key in reactor.peers():
            neighbor = reactor.neighbor(key)
            if neighbor is None or not _matches(neighbor, connection):
                continue
            # the peer may already have connected, so every individual peer is tried before
            # a range is
            if neighbor.range_size > 1:
                ranged.append(neighbor)
                continue

            if not admit_by_ttl(connection, neighbor):
                connection.close()
                return
            set_accepted_ttl(connection, neighbor)
            if not self._refused(connection, reactor.handle_connection(key, connection)):
                log.debug(lazymsg('accepted connection from {name}', name=connection.name()), 'network')
            return

        if len(ranged) > 1:
            log.debug(
                lazymsg('connection.rejected name={name} reason=multiple_neighbor_match', name=connection.name()),
                'network',
            )
            reason = b'could not accept the connection (more than one neighbor match)'
            self._refuse(connection, connection.notification(6, 5, reason))
            return
        if not ranged:
            log.debug(lazymsg('no session configured for {name}', name=connection.name()), 'network')
            # RFC 4486 4 names this case for Connection Rejected: "the peer is not
            # configured locally".  It sent (6, 3) Peer De-configured, which is for a
            # peering the speaker had and decided to remove
            self._refuse(connection, connection.notification(6, 5, b'no session configured for the peer'))
            return
        self._accept_ranged(ranged[0], connection)

    def _refused(self, connection: Incoming, refusal: Iterator[bool] | None) -> bool:
        """Send the NOTIFICATION a peer refused the connection with, if it refused it.

        Peer.handle_connection answers a refusal with the writer of its NOTIFICATION. It was
        only tested for truth and dropped, so the peer was never told why: the socket closed
        when it was collected.
        """
        if refusal is None:
            return False
        log.debug(
            lazymsg('refused connection from {name} due to the state machine', name=connection.name()),
            'network',
        )
        self._refuse(connection, refusal)
        return True

    def _refuse(self, connection: Incoming, notification: Iterator[bool]) -> None:
        self._reactor.asynchronous.schedule(
            str(uuid.uuid1()),
            f'sending notification to {connection.name()}',
            notification,
        )

    def _accept_ranged(self, template: Neighbor, connection: Incoming) -> None:
        """A neighbor of its own for a peer of a configured range, then its session."""
        # a deep copy: a shallow one shared the Session and the RIB of the configured range,
        # so setting this peer's addresses rewrote the range, and every peer had one RIB
        neighbor = copy.deepcopy(template)
        neighbor.range_size = 1
        neighbor.ephemeral = True
        neighbor.session.local_address = IP.from_string(connection.peer)
        neighbor.session.peer_address = IP.from_string(connection.local)
        if not neighbor.session.router_id:
            neighbor.session.router_id = RouterID(connection.local)
        # named after the peer, now its addresses are its own
        neighbor.make_rib()
        assert neighbor.session is not template.session, 'a ranged peer must not change its range'
        assert neighbor.rib is not template.rib, 'a ranged peer must not share the RIB of its range'

        if not admit_by_ttl(connection, neighbor):
            connection.close()
            return
        peer = Peer(neighbor, self._reactor)
        set_accepted_ttl(connection, neighbor)
        if not self._refused(connection, peer.handle_connection(connection)):
            self._reactor.register_peer(neighbor.name(), peer)

    def close_unwanted(self, wanted: set[tuple[str, int]]) -> None:
        """Close every listening socket the configuration no longer asks for.

        _listen shares one socket per (address, port), so several neighbours can be behind
        the one entry here and the dict does not record how many. The caller therefore
        says which (address, port) pairs it still wants and this closes the rest, which
        cannot drift the way a count would.

        Without it the port of a neighbour removed by a reload stayed bound for the life
        of the process and kept accepting connections nothing would ever serve.
        """
        for sock in list(self._sockets):
            ip, port, _, _, _ = self._sockets[sock]
            if (ip, port) in wanted:
                continue
            sock.close()
            del self._sockets[sock]
            self._accepted.pop(sock, None)
            log.info(lazymsg('stopped listening on {ip}:{port}', ip=ip, port=port), 'network')

        self.serving = bool(self._sockets)

    def stop(self) -> None:
        if not self.serving:
            return

        for sock, (ip, port, _, _, _) in self._sockets.items():
            sock.close()
            log.info(lazymsg('stopped listening on {ip}:{port}', ip=ip, port=port), 'network')

        self._sockets = {}
        self.serving = False


class StoppedListener(Listener):
    """The listener of a reactor which listens on nothing, the STOPPED sentinel.

    A subclass rather than object.__new__(Listener): a compiled class can not be built
    that way. It has no reactor, as the sentinel never had one.
    """

    def __init__(self) -> None:
        # no Listener.__init__, which needs a reactor: only what the sentinel is asked
        self.serving = False
        self._sockets = {}
        self._accepted = {}


# Initialize the STOPPED singleton
Listener.STOPPED = StoppedListener()
