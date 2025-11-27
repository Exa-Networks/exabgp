from __future__ import annotations

import asyncio
import time
from typing import ClassVar, Iterator

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

from exabgp.logger import log, lazymsg


class Outgoing(Connection):
    direction: ClassVar[str] = 'outgoing'

    def __init__(
        self,
        afi: AFI,
        peer: str,
        local: str,
        port: int = 179,
        md5: str = '',
        md5_base64: bool = False,
        ttl: int | None = None,
        itf: str | None = None,
    ) -> None:
        Connection.__init__(self, afi, peer, local)

        self.ttl: int | None = ttl
        self.afi: AFI = afi
        self.md5: str = md5
        self.md5_base64: bool = md5_base64
        self.port: int = port
        self.interface: str | None = itf

    def _setup(self) -> Exception | None:
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
            if self.io:
                self.io.close()
            self.io = None
            return exc

    def _connect(self) -> Exception | None:
        if not self.io:
            setup_issue = self._setup()
            if setup_issue:
                return setup_issue
        try:
            connect(self.io, self.peer, self.port, self.afi, self.md5)  # type: ignore[arg-type]
            return None
        except Exception as exc:
            if self.io:
                self.io.close()
            self.io = None
            return exc

    def establish(self) -> Iterator[bool]:
        last = time.time() - 2.0

        while True:
            notify = time.time() - last > 1.0
            if notify:
                last = time.time()

            if notify:
                log.debug(
                    lazymsg('connection.attempting peer={p} port={pt}', p=self.peer, pt=self.port), self.session()
                )

            connect_issue = self._connect()
            if connect_issue:
                if notify:
                    log.debug(
                        lazymsg('connection.failed peer={p} port={pt}', p=self.peer, pt=self.port), self.session()
                    )
                    log.debug(lazymsg('connection.error error={e}', e=str(connect_issue)), self.session())
                yield False
                continue

            connected = False
            for r, message in ready(self.io):  # type: ignore[arg-type]
                if not r:
                    yield False
                    continue
                connected = True

            if connected:
                self.success()
                if not self.local:
                    assert self.io is not None  # Must exist after successful connection
                    self.local = self.io.getsockname()[0]
                yield True
                return

            self._setup()

        # nagle(self.io,self.peer)
        # # Not working after connect() at least on FreeBSD TTL(self.io,self.peer,self.ttl)
        # yield True

    async def establish_async(self, timeout: float = 30.0, max_attempts: int = 50) -> bool:
        """Async version of establish() - establishes connection using asyncio

        Args:
            timeout: Maximum time in seconds to attempt connection (default: 30s)
            max_attempts: Maximum number of connection attempts (default: 50)

        Returns:
            True if connection successful, False otherwise

        Uses asyncio.sock_connect() which properly integrates with the event
        loop instead of polling with select.poll().
        """
        loop = asyncio.get_event_loop()
        start_time = time.time()
        attempts = 0
        last = time.time() - 2.0

        while time.time() - start_time < timeout and attempts < max_attempts:
            attempts += 1
            notify = time.time() - last > 1.0
            if notify:
                last = time.time()
                log.debug(
                    lazymsg(
                        'async.connection.attempt attempt={a} max={m} peer={p} port={pt} elapsed={e:.1f}s',
                        a=attempts,
                        m=max_attempts,
                        p=self.peer,
                        pt=self.port,
                        e=time.time() - start_time,
                    ),
                    self.session(),
                )

            # Setup socket if needed
            setup_issue = self._setup()
            if setup_issue:
                if notify:
                    log.debug(
                        lazymsg('connection.setup.failed peer={p} port={pt}', p=self.peer, pt=self.port), self.session()
                    )
                    log.debug(lazymsg('connection.error error={e}', e=str(setup_issue)), self.session())
                await asyncio.sleep(0.1)  # Brief delay before retry
                continue

            # Use asyncio to connect (non-blocking, event-driven)
            try:
                if self.afi == AFI.ipv4:
                    await loop.sock_connect(self.io, (self.peer, self.port))  # type: ignore[arg-type]
                elif self.afi == AFI.ipv6:
                    await loop.sock_connect(self.io, (self.peer, self.port, 0, 0))  # type: ignore[arg-type]

                # Connection successful
                self.success()
                if not self.local:
                    assert self.io is not None  # Must exist after successful connection
                    self.local = self.io.getsockname()[0]

                log.debug(
                    lazymsg('connection.established peer={p} port={pt}', p=self.peer, pt=self.port), self.session()
                )
                return True

            except OSError as exc:
                if notify:
                    log.debug(
                        lazymsg('connection.failed peer={p} port={pt}', p=self.peer, pt=self.port), self.session()
                    )
                    log.debug(lazymsg('connection.error error={e}', e=str(exc)), self.session())

                # Close and cleanup for retry
                if self.io:
                    self.io.close()
                self.io = None

                # Brief delay before retry
                await asyncio.sleep(0.1)
                continue

        # Timeout or max attempts reached - connection failed
        elapsed = time.time() - start_time
        log.debug(
            lambda: '[ASYNC] connection to %s:%d failed after %d attempts (%.1fs elapsed)'
            % (self.peer, self.port, attempts, elapsed),
            self.session(),
        )

        # Cleanup if socket is still open
        if self.io:
            self.io.close()
        self.io = None

        return False
