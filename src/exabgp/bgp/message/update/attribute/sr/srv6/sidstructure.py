"""srv6/sidstructure.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

from __future__ import annotations

import json
from struct import pack
from typing import ClassVar

from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation

# 3.2.1.  SRv6 SID Structure Sub-Sub-TLV
#
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | SRv6 Service  |    SRv6 Service               | Locator Block |
# | Data Sub-Sub  |    Data Sub-Sub-TLV           | Length        |
# | -TLV Type=1   |    Length                     |               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Locator Node  | Function      | Argument      | Transposition |
# | Length        | Length        | Length        | Length        |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Transposition |
# | Offset        |
# +-+-+-+-+-+-+-+-+
#
#           Figure 5: SRv6 SID Structure Sub-Sub-TLV


@Srv6SidInformation.register()
class Srv6SidStructure:  # type: ignore[type-var]
    TLV: ClassVar[int] = 1
    LENGTH: ClassVar[int] = 6

    registered_subsubtlvs: ClassVar[dict[int, type]] = dict()

    def __init__(self, packed: bytes) -> None:
        if len(packed) != self.LENGTH:
            raise ValueError(f'Srv6SidStructure requires exactly {self.LENGTH} bytes, got {len(packed)}')
        self._packed: bytes = packed

    @classmethod
    def make_sid_structure(
        cls,
        loc_block_len: int,
        loc_node_len: int,
        func_len: int,
        arg_len: int,
        tpose_len: int,
        tpose_offset: int,
    ) -> 'Srv6SidStructure':
        """Factory method for semantic construction."""
        packed = pack('!BBBBBB', loc_block_len, loc_node_len, func_len, arg_len, tpose_len, tpose_offset)
        return cls(packed)

    @property
    def loc_block_len(self) -> int:
        return self._packed[0]

    @property
    def loc_node_len(self) -> int:
        return self._packed[1]

    @property
    def func_len(self) -> int:
        return self._packed[2]

    @property
    def arg_len(self) -> int:
        return self._packed[3]

    @property
    def tpose_len(self) -> int:
        return self._packed[4]

    @property
    def tpose_offset(self) -> int:
        return self._packed[5]

    @classmethod
    def unpack_attribute(cls, data: bytes, length: int) -> Srv6SidStructure:
        # Validation happens in __init__
        return cls(data[: cls.LENGTH])

    def pack_tlv(self) -> bytes:
        return pack('!B', self.TLV) + pack('!H', self.LENGTH) + self._packed

    def __str__(self) -> str:
        return 'sid-structure [%d,%d,%d,%d,%d,%d]' % (
            self.loc_block_len,
            self.loc_node_len,
            self.func_len,
            self.arg_len,
            self.tpose_len,
            self.tpose_offset,
        )

    def json(self, compact: bool | None = None) -> str:
        pairs: dict[str, int] = {
            'locator-block-length': self.loc_block_len,
            'locator-node-length': self.loc_node_len,
            'function-length': self.func_len,
            'argument-length': self.arg_len,
            'transposition-length': self.tpose_len,
            'transposition-offset': self.tpose_offset,
        }

        return '"structure": {}'.format(json.dumps(pairs))
