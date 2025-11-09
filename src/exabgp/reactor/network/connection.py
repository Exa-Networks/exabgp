
"""network.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import random
import socket
import select
from struct import unpack

from exabgp.environment import getenv

from exabgp.util.errstr import errstr

from exabgp.logger import log
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


class Connection:
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
        self._rpoller = {}
        self._wpoller = {}

        self.id = self.identifier.get(self.direction, 1)

    def success(self):
        identifier = self.identifier.get(self.direction, 1) + 1
        self.identifier[self.direction] = identifier
        return identifier

    # Just in case ..
    def __del__(self):
        self.close()

    def name(self):
        return f'{self.direction}-{self.id} {self.local}-{self.peer}'

    def session(self):
        return f'{self.direction}-{self.id}'

    def fd(self):
        if self.io:
            return self.io.fileno()
        # the socket is closed (fileno() == -1) or not open yet (io is None)
        return -1

    def close(self):
        if not self.io:
            return
        message = f'{self.name()}, closing connection'
        log.warning(lambda: message, source=self.session())
        try:
            self.io.close()
            message = f'connection to {self.peer} closed'
        except Exception as exc:
            message = f'error while closing connection: {exc}'
        self.io = None
        log.warning(lambda: message, source=self.session())

    def reading(self):
        poller = self._rpoller.get(self.io, None)
        if poller is None:
            poller = select.poll()
            poller.register(self.io, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLNVAL | select.POLLERR)
            self._rpoller = {self.io: poller}

        ready = False
        for _, event in poller.poll(0):
            if event & select.POLLIN or event & select.POLLPRI:
                ready = True
            elif event & select.POLLHUP or event & select.POLLERR or event & select.POLLNVAL:
                self._rpoller = {}
                ready = True
        return ready

    def writing(self):
        poller = self._wpoller.get(self.io, None)
        if poller is None:
            poller = select.poll()
            poller.register(self.io, select.POLLOUT | select.POLLHUP | select.POLLNVAL | select.POLLERR)
            self._wpoller = {self.io: poller}

        ready = False
        for _, event in poller.poll(0):
            if event & select.POLLOUT:
                ready = True
            elif event & select.POLLHUP or event & select.POLLERR or event & select.POLLNVAL:
                self._wpoller = {}
                ready = True
        return ready

    def _reader(self, number):
        # The function must not be called if it does not return with no data with a smaller size as parameter
        if not self.io:
            self.close()
            raise NotConnected('Trying to read on a closed TCP connection')
        if number == 0:
            yield b''
            return

        while not self.reading():
            yield b''
        data = b''
        reported = ''
        while True:
            try:
                while True:
                    if self.defensive and random.randint(0, 2):
                        raise OSError(errno.EAGAIN, 'raising network error on purpose')

                    read = self.io.recv(number)
                    if not read:
                        self.close()
                        log.warning(lambda: f'{self.name()} {self.peer} lost TCP session with peer', self.session())
                        raise LostConnection('the TCP connection was closed by the remote end')
                    data += read

                    number -= len(read)
                    if not number:
                        log.debug(lazyformat('received TCP payload', data), self.session())
                        yield data
                        return

                    yield b''
            except socket.timeout as exc:
                self.close()
                log.warning(lambda: f'{self.name()} {self.peer} peer is too slow', self.session())
                raise TooSlowError(f'Timeout while reading data from the network ({errstr(exc)})') from None
            except OSError as exc:
                if exc.args[0] in error.block:
                    message = f'{self.name()} {self.peer} blocking io problem mid-way through reading a message {errstr(exc)}, trying to complete'
                    if message != reported:
                        reported = message
                        log.debug(lambda message=message: message, self.session())
                    yield b''
                elif exc.args[0] in error.fatal:
                    self.close()
                    raise LostConnection(f'issue reading on the socket: {errstr(exc)}') from None
                # what error could it be !
                else:
                    log.critical(lambda: f'{self.name()} {self.peer} undefined error reading on socket', self.session())
                    raise NetworkError(f'Problem while reading data from the network ({errstr(exc)})') from None

    def writer(self, data):
        if not self.io:
            # XXX: FIXME: Make sure it does not hold the cleanup during the closing of the peering session
            yield True
            return
        while not self.writing():
            yield False
        log.debug(lazyformat('sending TCP payload', data), self.session())
        # The first while is here to setup the try/catch block once as it is very expensive
        while True:
            try:
                while True:
                    if self.defensive and random.randint(0, 2):
                        raise OSError(errno.EAGAIN, 'raising network error on purpose')

                    # we can not use sendall as in case of network buffer filling
                    # it does raise and does not let you know how much was sent
                    number = self.io.send(data)
                    if not number:
                        self.close()
                        log.warning(lambda: f'{self.name()} {self.peer} lost TCP connection with peer', self.session())
                        raise LostConnection('lost the TCP connection')

                    data = data[number:]
                    if not data:
                        yield True
                        return
                    yield False
            except OSError as exc:
                if exc.args[0] in error.block:
                    log.debug(
                        lambda exc=exc: f'{self.name()} {self.peer} blocking io problem mid-way through writing a message {errstr(exc)}, trying to complete',
                        self.session(),
                    )
                    yield False
                elif exc.errno == errno.EPIPE:
                    # The TCP connection is gone.
                    self.close()
                    raise NetworkError('Broken TCP connection') from None
                elif exc.args[0] in error.fatal:
                    self.close()
                    log.critical(
                        lambda exc=exc: f'{self.name()} {self.peer} problem sending message ({errstr(exc)})', self.session(),
                    )
                    raise NetworkError(f'Problem while writing data to the network ({errstr(exc)})') from None
                # what error could it be !
                else:
                    log.critical(lambda: f'{self.name()} {self.peer} undefined error writing on socket', self.session())
                    yield False

    def reader(self):
        # _reader returns the whole number requested or nothing and then stops
        for header in self._reader(Message.HEADER_LEN):
            if not header:
                yield 0, 0, b'', b'', None

        if not header.startswith(Message.MARKER):
            report = 'The packet received does not contain a BGP marker'
            yield 0, 0, header, b'', NotifyError(1, 1, report)
            return

        msg = header[18]
        length = unpack('!H', header[16:18])[0]

        if length < Message.HEADER_LEN or length > self.msg_size:
            report = f'{Message.CODE.name(msg)} has an invalid message length of {length}'
            yield length, 0, header, b'', NotifyError(1, 2, report)
            return

        validator = Message.Length.get(msg, lambda _: _ >= 19)
        if not validator(length):
            # MUST send the faulty length back
            report = f'{Message.CODE.name(msg)} has an invalid message length of {length}'
            yield length, 0, header, b'', NotifyError(1, 2, report)
            return

        number = length - Message.HEADER_LEN

        if not number:
            yield length, msg, header, b'', None
            return

        for body in self._reader(number):
            if not body:
                yield 0, 0, b'', b'', None

        yield length, msg, header, body, None
