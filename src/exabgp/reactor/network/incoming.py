from __future__ import annotations

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

        log.debug(lambda: 'connection from {}'.format(self.peer), 'network')

        try:
            self.io = io
            asynchronous(self.io, self.peer)
            nagle(self.io, self.peer)
            self.success()
        except NetworkError as exc:
            self.close()
            raise NotConnected(errstr(exc)) from None

    def notification(self, code, subcode, message):
        try:
            notification = Notify(code, subcode, message).message()
            for boolean in self.writer(notification):
                yield False
            self.close()
        except NetworkError as exc:
            # the only callers are the refusals of an inbound connection: no neighbour is
            # configured for it, more than one matches, or a session is already up. The
            # connection is going away whether or not the NOTIFICATION reaches the far
            # end, so this is not an error, but it is not nothing either: an operator
            # asking why a peer never saw a reason for being dropped has nowhere else to
            # find out that the reason never left the host.
            log.debug(
                lambda exc=exc: f'could not send the notification to {self.peer} ({errstr(exc)})',
                'network',
            )
