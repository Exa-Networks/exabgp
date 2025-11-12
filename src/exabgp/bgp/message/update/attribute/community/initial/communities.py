"""community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# ============================================================== Communities (8)
# https://www.iana.org/assignments/bgp-extended-communities

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator, List, Optional

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.initial.community import Community

from exabgp.bgp.message.notification import Notify

# Community size constant
COMMUNITY_SIZE = 4  # Each standard community is 4 bytes (2 bytes ASN + 2 bytes value)


@Attribute.register()
class Communities(Attribute):
    ID = Attribute.CODE.COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    def __init__(self, communities: Optional[List[Community]] = None) -> None:
        # Must be None as = param is only evaluated once
        if communities:
            self.communities: List[Community] = communities
        else:
            self.communities = []

    def add(self, data: Community) -> Communities:
        self.communities.append(data)
        self.communities.sort()
        return self

    def pack(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        if len(self.communities):
            return self._attribute(b''.join(c.pack() for c in self.communities))
        return b''

    def __iter__(self) -> Iterator[Community]:
        return iter(self.communities)

    def __repr__(self) -> str:
        lc = len(self.communities)
        if lc > 1:
            return '[ {} ]'.format(' '.join(repr(community) for community in sorted(self.communities)))
        if lc == 1:
            return repr(self.communities[0])
        return ''

    def json(self) -> str:
        return '[ {} ]'.format(', '.join(community.json() for community in self.communities))

    @staticmethod
    def unpack(data: bytes, direction: Any, negotiated: Negotiated) -> Communities:
        communities = Communities()
        while data:
            if data and len(data) < COMMUNITY_SIZE:
                raise Notify(3, 1, 'could not decode community {}'.format(str([hex(_) for _ in data])))
            communities.add(Community.unpack(data[:COMMUNITY_SIZE], direction, negotiated))
            data = data[COMMUNITY_SIZE:]
        return communities
