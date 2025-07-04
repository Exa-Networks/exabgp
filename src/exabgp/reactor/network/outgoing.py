from __future__ import annotations

import time

from exabgp.protocol.family import AFI
from .connection import Connection
from .tcp import create, bind
from .tcp import connect
from .tcp import md5

# from .tcp import nagle
from .tcp import ttl
from .tcp import ttlv6
from .tcp import asynchronous
from .tcp import ready
# from .error import NetworkError

from exabgp.logger import log


class Outgoing(Connection):
    direction = 'outgoing'

    def __init__(self, afi, peer, local, port=179, md5='', md5_base64=False, ttl=None, itf=None):
        Connection.__init__(self, afi, peer, local)

        self.ttl = ttl
        self.afi = afi
        self.md5 = md5
        self.md5_base64 = md5_base64
        self.port = port
        self.interface = itf

    def _setup(self):
        try:
            self.io = create(self.afi, self.interface)
            md5(self.io, self.peer, self.port, self.md5, self.md5_base64)
            if self.afi == AFI.ipv4:
                ttl(self.io, self.peer, self.ttl)
            elif self.afi == AFI.ipv6:
                ttlv6(self.io, self.peer, self.ttl)
            if self.local:
                bind(self.io, self.local, self.afi)
            asynchronous(self.io, self.peer)
            return None
        except Exception as exc:
            self.io.close()
            self.io = None
            return exc

    def _connect(self):
        if not self.io:
            setup_issue = self._setup()
            if setup_issue:
                return setup_issue
        try:
            connect(self.io, self.peer, self.port, self.afi, self.md5)
            return None
        except Exception as exc:
            self.io.close()
            self.io = None
            return exc

    def establish(self):
        last = time.time() - 2.0

        while True:
            notify = time.time() - last > 1.0
            if notify:
                last = time.time()

            if notify:
                log.debug('attempting connection to %s:%d' % (self.peer, self.port), self.session())

            connect_issue = self._connect()
            if connect_issue:
                if notify:
                    log.debug('connection to %s:%d failed' % (self.peer, self.port), self.session())
                    log.debug(str(connect_issue), self.session())
                yield False
                continue

            connected = False
            for r, message in ready(self.io):
                if not r:
                    yield False
                    continue
                connected = True

            if connected:
                self.success()
                if not self.local:
                    self.local = self.io.getsockname()[0]
                yield True
                return

            self._setup()

        # nagle(self.io,self.peer)
        # # Not working after connect() at least on FreeBSD TTL(self.io,self.peer,self.ttl)
        # yield True
