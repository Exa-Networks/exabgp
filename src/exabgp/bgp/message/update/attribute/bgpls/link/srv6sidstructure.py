"""srv6sidstructure.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.link.srv6endx import Srv6EndX
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.link.srv6lanendx import Srv6LanEndXISIS, Srv6LanEndXOSPF
from exabgp.util.types import Buffer

# Fixed data length for SRv6 SID Structure TLV (RFC 9514 Section 8)
# LB Length (1) + LN Length (1) + Function Length (1) + Argument Length (1) = 4 bytes
SRV6_SID_STRUCTURE_LEN = 4

#     RFC 9514 : 8.  SRv6 SID Structure TLV
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               Type            |          Length               |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |    LB Length  |  LN Length    | Fun. Length   |  Arg. Length  |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                      Figure 10: SRv6 SID Structure TLV


@Srv6EndX.register_subsubtlv()
@Srv6LanEndXISIS.register_subsubtlv()
@Srv6LanEndXOSPF.register_subsubtlv()
@LinkState.register_lsid(tlv=1252, json_key='srv6-sid-structure', repr_name='SRv6 SID Structure')
class Srv6SidStructure(BaseLS):
    LEN = SRV6_SID_STRUCTURE_LEN

    @property
    def loc_block_len(self) -> int:
        """Return locator block length from packed bytes."""
        return self._packed[0]

    @property
    def loc_node_len(self) -> int:
        """Return locator node length from packed bytes."""
        return self._packed[1]

    @property
    def func_len(self) -> int:
        """Return function length from packed bytes."""
        return self._packed[2]

    @property
    def arg_len(self) -> int:
        """Return argument length from packed bytes."""
        return self._packed[3]

    @classmethod
    def make_srv6_sid_structure(
        cls, loc_block_len: int, loc_node_len: int, func_len: int, arg_len: int
    ) -> Srv6SidStructure:
        """Create Srv6SidStructure from semantic values.

        Args:
            loc_block_len: Locator block length in bits
            loc_node_len: Locator node length in bits
            func_len: Function length in bits
            arg_len: Argument length in bits

        Returns:
            Srv6SidStructure instance
        """
        packed = bytes([loc_block_len, loc_node_len, func_len, arg_len])
        return cls(packed)

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> Srv6SidStructure:
        if len(data) < SRV6_SID_STRUCTURE_LEN:
            raise Notify(
                3, 5, f'SRv6 SID Structure: data too short, need {SRV6_SID_STRUCTURE_LEN} bytes, got {len(data)}'
            )
        return cls(data)

    def __str__(self) -> str:
        return 'sid-structure [%d,%d,%d,%d,]' % (
            self.loc_block_len,
            self.loc_node_len,
            self.func_len,
            self.arg_len,
        )

    def json(self, compact: bool = False) -> str:
        return '"srv6-sid-structure": ' + json.dumps(
            {
                'loc_block_len': self.loc_block_len,
                'loc_node_len': self.loc_node_len,
                'func_len': self.func_len,
                'arg_len': self.arg_len,
            },
            indent=compact,
        )
