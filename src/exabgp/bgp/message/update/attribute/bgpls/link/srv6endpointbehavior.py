"""srv6endpointbehavior.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

# Minimum data length for SRv6 Endpoint Behavior TLV (RFC 9514 Section 7.1)
# Endpoint Behavior (2) + Flags (1) + Algorithm (1) = 4 bytes
SRV6_ENDPOINT_BEHAVIOR_MIN_LENGTH = 4

#     RFC 9514 : 7.1.  SRv6 Endpoint Behavior TLV
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               Type            |          Length               |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |        Endpoint Behavior      |      Flags    |   Algorithm   |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                     Figure 7: SRv6 Endpoint Behavior TLV


@LinkState.register_lsid()
class Srv6EndpointBehavior(BaseLS):
    TLV = 1250

    def __init__(
        self,
        endpoint_behavior: int,
        flags: list[str],
        algorithm: int,
    ) -> None:
        self.endpoint_behavior = endpoint_behavior
        self.flags = flags
        self.algorithm = algorithm

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> Srv6EndpointBehavior:
        if len(data) < SRV6_ENDPOINT_BEHAVIOR_MIN_LENGTH:
            raise Notify(
                3,
                5,
                f'SRv6 Endpoint Behavior: data too short, need {SRV6_ENDPOINT_BEHAVIOR_MIN_LENGTH} bytes, got {len(data)}',
            )
        flags: list[str] = []  # No flags defined according to RFC 9514 and 9352
        algorithm = data[3]
        endpoint_behavior = unpack('!H', data[0:2])[0]

        return cls(endpoint_behavior=endpoint_behavior, flags=flags, algorithm=algorithm)

    def __str__(self) -> str:
        return 'srv6-endpoint-behavior [0x%s, flags: %s, algorithm: %d]' % (
            self.endpoint_behavior,
            self.flags,
            self.algorithm,
        )

    def json(self, compact: bool = False) -> str:
        return '"srv6-endpoint-behavior": ' + json.dumps(
            {
                'endpoint-behavior': self.endpoint_behavior,
                'flags': self.flags,
                'algorithm': self.algorithm,
            },
            indent=compact,
        )
