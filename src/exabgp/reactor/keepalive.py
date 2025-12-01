"""keepalive.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from exabgp.bgp.timer import SendTimer
from exabgp.bgp.message import Notify

from exabgp.reactor.network.error import NetworkError

if TYPE_CHECKING:
    from exabgp.reactor.protocol import Protocol


# =========================================================================== KA
#


class KA:
    """Async keepalive handler.

    Tracks when keepalives need to be sent and provides an async method to send them.
    """

    def __init__(self, session: Any, proto: 'Protocol') -> None:
        self._proto = proto
        self.send_timer: SendTimer = SendTimer(session, proto.negotiated.holdtime)

    async def send_if_needed(self) -> bool:
        """Send keepalive if the timer indicates one is needed.

        Returns:
            True if a keepalive was sent, False otherwise.

        Raises:
            Notify: If there was a network error sending the keepalive.
        """
        if not self.send_timer.need_ka():
            return False

        try:
            await self._proto.new_keepalive()
            return True
        except NetworkError:
            raise Notify(4, 0, 'problem with network while trying to send keepalive') from None
