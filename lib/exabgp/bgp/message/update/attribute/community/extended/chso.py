from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# draft-fm-bess-service-chaining


@ExtendedCommunity.register
class ConsistentHashSortOrder(ExtendedCommunity):
    COMMUNITY_TYPE = 0x03
    COMMUNITY_SUBTYPE = 0x14
    DESCRIPTION = "consistentHashSortOrder"

    __slots__ = ['order', 'reserved']

    def __init__(self, order, reserved=0, community=None):
        self.order = order
        self.reserved = reserved

        ExtendedCommunity.__init__(
            self, community if community is not None else pack("!2sIH", self._subtype(), order, reserved)
        )

    def __repr__(self):
        return "%s:%d" % (self.DESCRIPTION, self.order)

    @staticmethod
    def unpack(data):
        order, reserved = unpack('!IH', data[2:8])
        return ConsistentHashSortOrder(order, reserved, data[:8])
