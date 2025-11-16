"""vpls.py

Created by Nikita Shirokov on 2014-06-16.
Copyright (c) 2014-2017 Nikita Shirokov. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from struct import pack
from typing import Any, Iterator, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


def _unique() -> Iterator[int]:
    value = 0
    while True:
        yield value
        value += 1


unique: Iterator[int] = _unique()


@NLRI.register(AFI.l2vpn, SAFI.vpls)
class VPLS(NLRI):
    # XXX: Should take AFI, SAFI and OUT.direction as parameter to match other NLRI
    def __init__(
        self,
        rd: RouteDistinguisher,
        endpoint: int,
        base: int,
        offset: int,
        size: int,
    ) -> None:
        NLRI.__init__(self, AFI.l2vpn, SAFI.vpls)
        self.action = Action.ANNOUNCE
        self.nexthop = None
        self.rd = rd
        self.base = base
        self.offset = offset
        self.size = size
        self.endpoint = endpoint
        self.unique = next(unique)

    def feedback(self, action: Action) -> str:
        if self.nexthop is None and action == Action.ANNOUNCE:
            return 'vpls nlri next-hop missing'
        if self.endpoint is None:
            return 'vpls nlri endpoint missing'
        if self.base is None:
            return 'vpls nlri base missing'
        if self.offset is None:
            return 'vpls nlri offset missing'
        if self.size is None:
            return 'vpls nlri size missing'
        if self.rd is None:
            return 'vpls nlri route-distinguisher missing'
        if self.base > (0xFFFFF - self.size):  # type: ignore[operator]  # 20 bits, 3 bytes
            return 'vpls nlri size inconsistency'
        return ''

    def assign(self, name: str, value: Any) -> None:
        setattr(self, name, value)

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        return (
            b'\x00\x11'  # pack('!H',17)
            + self.rd.pack_rd()
            + pack('!HHH', self.endpoint, self.offset, self.size)
            + pack('!L', (self.base << 4) | 0x1)[1:]  # setting the bottom of stack, should we ?
        )

    def pack_nlri(self, negotiated: Negotiated) -> bytes:  # type: ignore[assignment]
        # RFC 7911 ADD-PATH is possible for VPLS but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.l2vpn, SAFI.vpls)
        return self._pack_nlri_simple()

    def index(self) -> bytes:
        return Family.index(self) + self._pack_nlri_simple()

    # XXX: FIXME: we need an unique key here.
    # XXX: What can we use as unique key ?
    def json(self, compact: Optional[bool] = None) -> str:
        content = ', '.join(
            [
                self.rd.json(),
                '"endpoint": {}'.format(self.endpoint),
                '"base": {}'.format(self.base),
                '"offset": {}'.format(self.offset),
                '"size": {}'.format(self.size),
            ],
        )
        return '{{ {} }}'.format(content)

    def extensive(self) -> str:
        return 'vpls{} endpoint {} base {} offset {} size {} {}'.format(
            self.rd,
            self.endpoint,
            self.base,
            self.offset,
            self.size,
            '' if self.nexthop is None else 'next-hop {}'.format(self.nexthop),
        )

    def __str__(self) -> str:
        return self.extensive()

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: bytes, action: Action, addpath: Any, negotiated: Negotiated
    ) -> Tuple[VPLS, bytes]:
        # label is 20bits, stored using 3 bytes, 24 bits
        (length,) = unpack('!H', bgp[0:2])
        if len(bgp) != length + 2:
            raise Notify(3, 10, 'l2vpn vpls message length is not consistent with encoded bgp')
        rd = RouteDistinguisher(bgp[2:10])
        endpoint, offset, size = unpack('!HHH', bgp[10:16])
        base = unpack('!L', b'\x00' + bgp[16:19])[0] >> 4
        nlri = cls(rd, endpoint, base, offset, size)
        nlri.action = action
        # nlri.nexthop = IP.unpack_ip(nexthop)
        return nlri, bgp[19:]
