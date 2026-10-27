from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import ClassVar

from exabgp.bgp.message import Notify
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI
from exabgp.util.errstr import errstr

from .connection import Connection
from .error import NetworkError, NotConnected
from .tcp import asynchronous, nagle


class Incoming(Connection):
    direction: ClassVar[str] = 'incoming'

    def __init__(self, afi: AFI, peer: str, local: str, io: socket.socket) -> None:
        Connection.__init__(self, afi, peer, local)

        log.debug(lazymsg('incoming.connection peer={peer}', peer=self.peer), 'network')

        try:
            self.io = io
            asynchronous(self.io, self.peer)
            nagle(self.io, self.peer)
            self.success()
        except NetworkError as exc:
            self.close()
            raise NotConnected(errstr(exc)) from None

    def notification(self, code: int, subcode: int, message: bytes) -> Iterator[bool]:
        try:
            # packing a NOTIFICATION does not use negotiated, but it's required by the signature
            # Create a minimal Negotiated object for this early connection stage
            negotiated = Negotiated.make_negotiated(Neighbor.EMPTY, Direction.IN)
            notification = Notify(code, subcode, message.decode('ascii')).notification.pack_message(negotiated)
            for boolean in self.writer(notification):
                yield False
            self.close()
        except NetworkError as exc:
            # the only caller is the refusal of a connection from an unconfigured peer, so
            # the session is going away whether or not the NOTIFICATION reaches it. Say
            # that it did not: an operator looking at why a peer never saw a reason for
            # being dropped has nowhere else to find out.
            log.debug(
                lazymsg('notification.unsent peer={peer} reason={reason}', peer=self.peer, reason=errstr(exc)),
                'network',
            )
