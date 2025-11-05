# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import random
import socket
from struct import unpack

from exabgp.environment import getenv

from exabgp.util.errstr import errstr

from exabgp.logger import log
from exabgp.logger import logfunc
from exabgp.logger import lazyformat

from exabgp.bgp.message import Message

from exabgp.reactor.network.error import error
from exabgp.reactor.network.error import errno
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.network.error import TooSlowError
from exabgp.reactor.network.error import NotConnected
from exabgp.reactor.network.error import LostConnection
from exabgp.reactor.network.error import NotifyError

from exabgp.bgp.message.open.capability.extended import ExtendedMessage

# from .error import *


class Connection(object):
    direction = 'undefined'
    identifier = {}

    def __init__(self, afi, peer, local):
        self.msg_size = ExtendedMessage.INITIAL_SIZE
        self.defensive = getenv().debug.defensive

        self.afi = afi
        self.peer = peer
        self.local = local

        self.io = None
        self.established = False

        self.id = self.identifier.get(self.direction, 1)

    def success(self):
        identifier = self.identifier.get(self.direction, 1) + 1
        self.identifier[self.direction] = identifier
        return identifier

    # Just in case ..
    def __del__(self):
        self.close()

    def name(self):
        return '%s-%d %s-%s' % (self.direction, self.id, self.local, self.peer)

    def session(self):
        return '%s-%d' % (self.direction, self.id)

    def fd(self):
        if self.io:
            return self.io.fileno()
        # the socket is closed (fileno() == -1) or not open yet (io is None)
        return -1

    def close(self):
        try:
            log.warning('%s, closing connection' % self.name(), source=self.session())
            if self.io:
                self.io.close()
                self.io = None
            log.warning('connection to %s closed' % self.peer, self.session())
        except Exception:
            self.io = None

    async def _wait_readable(self):
        """Wait for the socket to be readable using asyncio"""
        if not self.io:
            return False
        loop = asyncio.get_event_loop()
        try:
            await loop.sock_recv(self.io, 0)  # This will wait until readable
            return True
        except (OSError, ConnectionError):
            return True  # Error means we should try to read to get the actual error

    async def _wait_writable(self):
        """Wait for the socket to be writable using asyncio"""
        if not self.io:
            return False
        loop = asyncio.get_event_loop()
        # For writable, we can use sock_sendall with empty bytes
        # Or better, just yield control and assume it's writable
        await asyncio.sleep(0)
        return True

    async def _reader(self, number):
        """Read exactly 'number' bytes from the socket"""
        if not self.io:
            self.close()
            raise NotConnected('Trying to read on a closed TCP connection')
        if number == 0:
            return b''

        loop = asyncio.get_event_loop()
        data = b''
        reported = ''

        while len(data) < number:
            try:
                if self.defensive and random.randint(0, 2):
                    raise socket.error(errno.EAGAIN, 'raising network error on purpose')

                # Use asyncio's sock_recv to read data asynchronously
                remaining = number - len(data)
                read = await loop.sock_recv(self.io, remaining)

                if not read:
                    self.close()
                    log.warning('%s %s lost TCP session with peer' % (self.name(), self.peer), self.session())
                    raise LostConnection('the TCP connection was closed by the remote end')

                data += read

            except socket.timeout as exc:
                self.close()
                log.warning('%s %s peer is too slow' % (self.name(), self.peer), self.session())
                raise TooSlowError('Timeout while reading data from the network (%s)' % errstr(exc))
            except socket.error as exc:
                if exc.args[0] in error.block:
                    message = '%s %s blocking io problem mid-way through reading a message %s, trying to complete' % (
                        self.name(),
                        self.peer,
                        errstr(exc),
                    )
                    if message != reported:
                        reported = message
                        log.debug(message, self.session())
                    # Yield control and retry
                    await asyncio.sleep(0)
                elif exc.args[0] in error.fatal:
                    self.close()
                    raise LostConnection('issue reading on the socket: %s' % errstr(exc))
                else:
                    log.critical('%s %s undefined error reading on socket' % (self.name(), self.peer), self.session())
                    raise NetworkError('Problem while reading data from the network (%s)' % errstr(exc))

        logfunc.debug(lazyformat('received TCP payload', data), self.session())
        return data

    async def writer(self, data):
        """Write all data to the socket"""
        if not self.io:
            # XXX: FIXME: Make sure it does not hold the cleanup during the closing of the peering session
            return True

        logfunc.debug(lazyformat('sending TCP payload', data), self.session())
        loop = asyncio.get_event_loop()

        while data:
            try:
                if self.defensive and random.randint(0, 2):
                    raise socket.error(errno.EAGAIN, 'raising network error on purpose')

                # Use sock_sendall which sends all data (returns None on success)
                # We need to chunk it ourselves to maintain the original behavior
                chunk_size = min(len(data), 4096)
                chunk = data[:chunk_size]

                # sock_sendall returns None on success
                await loop.sock_sendall(self.io, chunk)
                data = data[chunk_size:]

            except (BrokenPipeError, ConnectionResetError) as exc:
                self.close()
                log.warning('%s %s lost TCP connection with peer' % (self.name(), self.peer), self.session())
                raise LostConnection('lost the TCP connection')
            except socket.error as exc:
                if exc.args[0] in error.block:
                    log.debug(
                        '%s %s blocking io problem mid-way through writing a message %s, trying to complete'
                        % (self.name(), self.peer, errstr(exc)),
                        self.session(),
                    )
                    # Yield control and retry
                    await asyncio.sleep(0)
                elif exc.errno == errno.EPIPE:
                    # The TCP connection is gone.
                    self.close()
                    raise NetworkError('Broken TCP connection')
                elif exc.args[0] in error.fatal:
                    self.close()
                    log.critical(
                        '%s %s problem sending message (%s)' % (self.name(), self.peer, errstr(exc)), self.session()
                    )
                    raise NetworkError('Problem while writing data to the network (%s)' % errstr(exc))
                else:
                    log.critical('%s %s undefined error writing on socket' % (self.name(), self.peer), self.session())
                    await asyncio.sleep(0)

        return True

    async def reader(self):
        """Read a complete BGP message (header + body)"""
        # Read the BGP message header
        header = await self._reader(Message.HEADER_LEN)

        if not header:
            return 0, 0, b'', b'', None

        if not header.startswith(Message.MARKER):
            report = 'The packet received does not contain a BGP marker'
            return 0, 0, header, b'', NotifyError(1, 1, report)

        msg = header[18]
        length = unpack('!H', header[16:18])[0]

        if length < Message.HEADER_LEN or length > self.msg_size:
            report = '%s has an invalid message length of %d' % (Message.CODE.name(msg), length)
            return length, 0, header, b'', NotifyError(1, 2, report)

        validator = Message.Length.get(msg, lambda _: _ >= 19)
        if not validator(length):
            # MUST send the faulty length back
            report = '%s has an invalid message length of %d' % (Message.CODE.name(msg), length)
            return length, 0, header, b'', NotifyError(1, 2, report)

        number = length - Message.HEADER_LEN

        if not number:
            return length, msg, header, b'', None

        # Read the message body
        body = await self._reader(number)

        if not body:
            return 0, 0, b'', b'', None

        return length, msg, header, body, None
