"""peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import Any, Generator, Optional

from exabgp.bgp.timer import SendTimer
from exabgp.bgp.message import Notify

from exabgp.reactor.network.error import NetworkError


# =========================================================================== KA
#


class KA:
    def __init__(self, session: Any, proto: Any) -> None:
        self._generator: Generator[bool, None, None] = self._keepalive(proto)
        self.send_timer: SendTimer = SendTimer(session, proto.negotiated.holdtime)

    def _keepalive(self, proto: Any) -> Generator[bool, None, None]:
        need_ka: bool = False
        generator: Optional[Generator[Any, None, None]] = None

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
                next(generator)
                next(generator)
                # still running
                yield True
            except NetworkError:
                raise Notify(4, 0, 'problem with network while trying to send keepalive') from None
            except StopIteration:
                generator = None
                yield False

    def __call__(self) -> bool:
        #  True  if we need or are trying
        #  False if we do not need to send one
        try:
            return next(self._generator)
        except StopIteration:
            raise Notify(4, 0, 'could not send keepalive') from None
