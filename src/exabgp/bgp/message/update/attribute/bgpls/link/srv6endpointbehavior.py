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

# Fixed data length for SRv6 Endpoint Behavior TLV (RFC 9514 Section 7.1)
# Endpoint Behavior (2) + Flags (1) + Algorithm (1) = 4 bytes
SRV6_ENDPOINT_BEHAVIOR_LEN = 4

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
    LEN = SRV6_ENDPOINT_BEHAVIOR_LEN

    @property
    def endpoint_behavior(self) -> int:
        """Unpack and return endpoint behavior from packed bytes."""
        value: int = unpack('!H', self._packed[0:2])[0]
        return value

    @property
    def flags(self) -> list[str]:
        """Return flags (none defined according to RFC 9514 and 9352)."""
        return []

    @property
    def algorithm(self) -> int:
        """Return algorithm from packed bytes."""
        return self._packed[3]

    @classmethod
    def make_srv6_endpoint_behavior(cls, endpoint_behavior: int, algorithm: int) -> Srv6EndpointBehavior:
        """Create Srv6EndpointBehavior from semantic values.

        Args:
            endpoint_behavior: 16-bit endpoint behavior code
            algorithm: 8-bit algorithm value

        Returns:
            Srv6EndpointBehavior instance
        """
        from struct import pack

        # Pack: Endpoint Behavior (2) + Flags (1, reserved=0) + Algorithm (1)
        packed = pack('!HBB', endpoint_behavior, 0, algorithm)
        return cls(packed)

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> Srv6EndpointBehavior:
        if len(data) < SRV6_ENDPOINT_BEHAVIOR_LEN:
            raise Notify(
                3,
                5,
                f'SRv6 Endpoint Behavior: data too short, need {SRV6_ENDPOINT_BEHAVIOR_LEN} bytes, got {len(data)}',
            )
        return cls(data)

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
