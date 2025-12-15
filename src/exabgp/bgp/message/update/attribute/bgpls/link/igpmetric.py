"""igpmetric.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS, LinkState
from exabgp.util.types import Buffer

#   The IGP Metric TLV carries the metric for this link.  The length of
#   this TLV is variable, depending on the metric width of the underlying
#   protocol.  IS-IS small metrics have a length of 1 octet (the two most
#   significant bits are ignored).  OSPF link metrics have a length of 2
#   octets.  IS-IS wide metrics have a length of 3 octets.
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //      IGP Link Metric (variable length)      //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

# IGP Metric TLV size constants
IGP_METRIC_SIZE_OSPF: int = 2  # OSPF link metrics are 2 octets
IGP_METRIC_SIZE_ISIS_SMALL: int = 1  # IS-IS small metrics are 1 octet
IGP_METRIC_SIZE_ISIS_WIDE: int = 3  # IS-IS wide metrics are 3 octets


@LinkState.register_lsid()
class IgpMetric(BaseLS):
    TLV = 1095
    REPR = 'IGP Metric'
    JSON = 'igp-metric'

    @property
    def content(self) -> int:
        """Unpack and return the metric value from packed bytes.

        Variable length: 1-byte (IS-IS small), 2-byte (OSPF), or 3-byte (IS-IS wide).
        """
        data = self._packed
        if len(data) == IGP_METRIC_SIZE_OSPF:
            # OSPF
            value: int = unpack('!H', data)[0]
            return value

        if len(data) == IGP_METRIC_SIZE_ISIS_SMALL:
            # ISIS small metrics
            return data[0]

        if len(data) == IGP_METRIC_SIZE_ISIS_WIDE:
            # ISIS wide metrics
            wide_value: int = unpack('!L', bytes([0]) + data)[0]
            return wide_value

        # Shouldn't reach here if unpack_bgpls validated
        raise Notify(3, 5, 'Incorrect IGP Metric Size')

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> IgpMetric:
        if len(data) not in (IGP_METRIC_SIZE_ISIS_SMALL, IGP_METRIC_SIZE_OSPF, IGP_METRIC_SIZE_ISIS_WIDE):
            raise Notify(3, 5, 'Incorrect IGP Metric Size')
        return cls(data)
