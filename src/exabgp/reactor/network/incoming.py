from __future__ import annotations

import asyncio

from exabgp.util.errstr import errstr

from .connection import Connection
from .tcp import nagle
from .tcp import asynchronous
from .error import NetworkError
from .error import NotConnected

from exabgp.bgp.message import Notify
from exabgp.logger import log


class Incoming(Connection):
    direction = 'incoming'

    def __init__(self, afi, peer, local, io):
        Connection.__init__(self, afi, peer, local)

        log.debug('connection from %s' % self.peer, 'network')

        try:
            self.io = io
            asynchronous(self.io, self.peer)
            nagle(self.io, self.peer)
            self.success()
        except NetworkError as exc:
            self.close()
            raise NotConnected(errstr(exc))

    async def notification(self, code, subcode, message):
        """Send a notification message and close the connection"""
        try:
            notification = Notify(code, subcode, message).message()
            await self.writer(notification)
            self.close()
        except NetworkError:
            pass  # This is only be used when closing session due to unconfigured peers - so issues do not matter
