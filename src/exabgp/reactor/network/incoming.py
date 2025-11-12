from __future__ import annotations

import socket
from typing import ClassVar, Iterator

from exabgp.util.errstr import errstr

from .connection import Connection
from .tcp import nagle
from .tcp import asynchronous
from .error import NetworkError
from .error import NotConnected

from exabgp.bgp.message import Notify
from exabgp.logger import log

from exabgp.protocol.family import AFI


class Incoming(Connection):
    direction: ClassVar[str] = 'incoming'

    def __init__(self, afi: AFI, peer: str, local: str, io: socket.socket) -> None:
        Connection.__init__(self, afi, peer, local)

        log.debug(lambda: 'connection from {}'.format(self.peer), 'network')

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
            notification = Notify(code, subcode, message).message()
            for boolean in self.writer(notification):
                yield False
            self.close()
        except NetworkError:
            pass  # This is only be used when closing session due to unconfigured peers - so issues do not matter
