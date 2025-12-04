"""srv6locator.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

# Minimum data length for SRv6 Locator TLV (RFC 9514 Section 5.1)
# Flags (1) + Algorithm (1) + Reserved (2) + Metric (4) = 8 bytes
SRV6_LOCATOR_MIN_LENGTH = 8

#    RFC 9514:  5.1.  SRv6 Locator TLV
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               Type            |          Length               |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |      Flags    |   Algorithm   |           Reserved            |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |                            Metric                             |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |   Sub-TLVs (variable) . . .
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                      Figure 4: SRv6 Locator TLV Format


@LinkState.register_lsid()
class Srv6Locator(FlagLS):
    TLV = 1162
    FLAGS = ['D'] + ['RSV' for _ in range(7)]
    registered_subsubtlvs: dict[int, type] = dict()

    def __init__(self, flags: dict[str, int], algorithm: int, metric: int, subtlvs: list[object]) -> None:
        self.flags = flags
        self.algorithm = algorithm
        self.metric = metric
        self.subtlvs = subtlvs

    def __repr__(self) -> str:
        return 'flags: {}, algorithm: {}, metric: {}'.format(self.flags, self.algorithm, self.metric)

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> Srv6Locator:
        if len(data) < SRV6_LOCATOR_MIN_LENGTH:
            raise Notify(3, 5, f'SRv6 Locator: data too short, need {SRV6_LOCATOR_MIN_LENGTH} bytes, got {len(data)}')
        flags = cls.unpack_flags(bytes(data[0:1]))
        algorithm = data[1]
        metric = unpack('!I', data[4:8])[0]
        subtlvs: list[object] = []  # No sub-TLVs defined in RFC 9514

        return cls(flags=flags, algorithm=algorithm, metric=metric, subtlvs=subtlvs)

    def json(self, compact: bool = False) -> str:
        return '"srv6-locator": ' + json.dumps(
            {
                'flags': self.flags,
                'algorithm': self.algorithm,
                'metric': self.metric,
            },
            indent=compact,
        )
