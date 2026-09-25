"""aggregator.py

Created by Thomas Mangin on 2012-07-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute

# =============================================================== AGGREGATOR (7)
#


@Attribute.register()
class Aggregator(Attribute):
    ID = Attribute.CODE.AGGREGATOR
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    # Not cacheable: unpack reads negotiated.asn4.
    # RFC 6793 4.2.2. AGGREGATOR is six octets on a session which has not negotiated four
    # octet AS numbers and eight on one which has, so the same bytes are two different
    # attributes depending on the session. A cache shared between sessions cannot hold it.
    CACHING = False

    def __init__(self, asn, speaker):
        self.asn = asn
        self.speaker = speaker
        self._str = None

    def __eq__(self, other):
        if not isinstance(other, Aggregator):
            return NotImplemented
        return (
            self.ID == other.ID and self.FLAG == other.FLAG and self.asn == other.asn and self.speaker == other.speaker
        )

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def pack(self, negotiated):
        if negotiated.asn4:
            return self._attribute(self.asn.pack(True) + self.speaker.pack())
        if self.asn.asn4():
            return self._attribute(self.asn.trans().pack() + self.speaker.pack()) + Aggregator4(
                self.asn,
                self.speaker,
            ).pack(negotiated)
        return self._attribute(self.asn.pack() + self.speaker.pack())

    def __len__(self):
        raise RuntimeError('size can be 6 or 8 - we can not say - or can we ?')

    def __repr__(self):
        if not self._str:
            self._str = '{}:{}'.format(self.asn, self.speaker)
        return self._str

    def json(self):
        return '{ "asn" : %d, "speaker" : "%d" }' % (self.asn, self.speaker)

    @classmethod
    def unpack(cls, data, direction, negotiated):
        expected = 8 if negotiated.asn4 else 6
        if len(data) != expected:
            raise Notify(3, 5, 'invalid AGGREGATOR, expected %d bytes, got %d' % (expected, len(data)))
        if negotiated.asn4:
            return cls(ASN.unpack(data[:4]), IPv4.unpack(data[-4:]))
        return cls(ASN.unpack(data[:2]), IPv4.unpack(data[-4:]))


# ============================================================== AGGREGATOR (18)
#


@Attribute.register()
class Aggregator4(Aggregator):
    ID = Attribute.CODE.AS4_AGGREGATOR

    # Four octets of AS number and four of speaker, always.
    SIZE = 8

    def pack(self, negotiated):
        return self._attribute(self.asn.pack(True) + self.speaker.pack())

    @classmethod
    def unpack(cls, data, direction, negotiated):
        # This inherited Aggregator.unpack, which sizes itself on negotiated.asn4 and reads a
        # two octet AS number when the session has not negotiated four.  RFC 6793 4.2.2 gives
        # AS4_AGGREGATOR a single form, four octets of AS number, and a speaker which
        # negotiated four octets is never sent the attribute at all, so the only session which
        # ever sees one answered a correctly formed attribute with a NOTIFICATION.
        if len(data) != cls.SIZE:
            raise Notify(3, 5, 'invalid AS4_AGGREGATOR, expected %d bytes, got %d' % (cls.SIZE, len(data)))
        return cls(ASN.unpack(data[:4]), IPv4.unpack(data[-4:]))
