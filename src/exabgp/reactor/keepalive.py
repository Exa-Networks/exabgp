# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import asyncio

from exabgp.bgp.timer import SendTimer
from exabgp.bgp.message import Notify

from exabgp.reactor.network.error import NetworkError


# =========================================================================== KA
#


class KA(object):
    def __init__(self, session, proto):
        self.proto = proto
        self.send_timer = SendTimer(session, proto.negotiated.holdtime)
        self._sending = False

    async def __call__(self):
        """Check if keepalive needs to be sent and send if needed
        Returns True if sending/sent, False if not needed"""
        # Check if we need to send a keepalive
        need_ka = self.send_timer.need_ka()

        if need_ka and not self._sending:
            self._sending = True
            try:
                await self.proto.new_keepalive()
                self._sending = False
                return False  # Sent successfully
            except NetworkError:
                self._sending = False
                raise Notify(4, 0, 'problem with network while trying to send keepalive')

        return False  # No keepalive needed
