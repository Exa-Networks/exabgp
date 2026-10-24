"""originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute


# ============================================================== OriginatorID (3)


@Attribute.register()
class OriginatorID(Attribute, IPv4):
    ID = Attribute.CODE.ORIGINATOR_ID
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True

    def __eq__(self, other):
        # this compared the ID and the FLAG and never the address, so every
        # originator-id was equal to every other one, and overriding the base
        # class meant fixing the base class did not reach it
        if not isinstance(other, OriginatorID):
            return NotImplemented
        return self.ID == other.ID and self.FLAG == other.FLAG and self.ton() == other.ton()

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def pack(self, negotiated=None):
        return self._attribute(self.ton())

    @classmethod
    def unpack(cls, data, direction, negotiated):
        if len(data) != 4:
            raise Notify(3, 5, 'invalid ORIGINATOR_ID, expected 4 bytes, got %d' % len(data))
        return IPv4.unpack(data, cls)
