# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

from exabgp.vendoring import six

from exabgp.bgp.timer import SendTimer
from exabgp.bgp.message import Notify

from exabgp.reactor.network.error import NetworkError


# =========================================================================== KA
#


class KA(object):
    def __init__(self, session, proto):
        self._generator = self._keepalive(proto)
        self.send_timer = SendTimer(session, proto.negotiated.holdtime)

    def _keepalive(self, proto):
        need_ka = False
        generator = None

        while True:
            # SEND KEEPALIVES
            need_ka |= self.send_timer.need_ka()

            if need_ka:
                if not generator:
                    generator = proto.new_keepalive()
                    need_ka = False

            if not generator:
                yield False
                continue

            try:
                # try to close the generator and raise a StopIteration in one call
                six.next(generator)
                six.next(generator)
                # still running
                yield True
            except NetworkError:
                raise Notify(4, 0, 'problem with network while trying to send keepalive')
            except StopIteration:
                generator = None
                yield False

    def __call__(self):
        #  True  if we need or are trying
        #  False if we do not need to send one
        try:
            return six.next(self._generator)
        except StopIteration:
            raise Notify(4, 0, 'could not send keepalive')
