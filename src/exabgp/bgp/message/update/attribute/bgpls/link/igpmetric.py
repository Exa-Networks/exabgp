"""igpmetric.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS


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

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> IgpMetric:
        if len(data) == IGP_METRIC_SIZE_OSPF:
            # OSPF
            return cls(unpack('!H', data)[0])

        if len(data) == IGP_METRIC_SIZE_ISIS_SMALL:
            # ISIS small metrics
            return cls(data[0])

        if len(data) == IGP_METRIC_SIZE_ISIS_WIDE:
            # ISIS wide metrics
            return cls(unpack('!L', bytes([0]) + data)[0])

        raise Notify(3, 5, 'Incorrect IGP Metric Size')
