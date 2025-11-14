"""aggregator.py

Created by Thomas Mangin on 2012-07-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.update.attribute.attribute import Attribute

# =============================================================== AGGREGATOR (7)
#


@Attribute.register()
class Aggregator(Attribute):
    ID = Attribute.CODE.AGGREGATOR
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    CACHING = True

    def __init__(self, asn: ASN, speaker: IPv4) -> None:
        self.asn: ASN = asn
        self.speaker: IPv4 = speaker
        self._str: Optional[str] = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Aggregator):
            return False
        return (
            self.ID == other.ID and self.FLAG == other.FLAG and self.asn == other.asn and self.speaker == other.speaker
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack(self, negotiated: Negotiated) -> bytes:
        if negotiated.asn4:
            return self._attribute(self.asn.pack(True) + self.speaker.pack())  # type: ignore[arg-type]
        if self.asn.asn4():
            return self._attribute(self.asn.trans().pack() + self.speaker.pack()) + Aggregator4(
                self.asn,
                self.speaker,
            ).pack(negotiated)
        return self._attribute(self.asn.pack() + self.speaker.pack())

    def __len__(self) -> int:
        raise RuntimeError('size can be 6 or 8 - we can not say - or can we ?')

    def __repr__(self) -> str:
        if not self._str:
            self._str = '{}:{}'.format(self.asn, self.speaker)
        return self._str

    def json(self) -> str:
        return '{ "asn" : %d, "speaker" : "%d" }' % (self.asn, self.speaker)  # type: ignore[str-format]

    @classmethod
    def unpack(cls, data: bytes, direction: int, negotiated: Negotiated) -> Aggregator:
        if negotiated.asn4:
            return cls(ASN.unpack(data[:4]), IPv4.unpack(data[-4:]))
        return cls(ASN.unpack(data[:2]), IPv4.unpack(data[-4:]))


# ============================================================== AGGREGATOR (18)
#


@Attribute.register()
class Aggregator4(Aggregator):
    ID = Attribute.CODE.AS4_AGGREGATOR

    def pack(self, negotiated: Negotiated) -> bytes:
        return self._attribute(self.asn.pack(True) + self.speaker.pack())  # type: ignore[arg-type]
