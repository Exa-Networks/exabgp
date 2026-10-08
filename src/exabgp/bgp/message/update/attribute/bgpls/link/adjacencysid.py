"""sradj.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import ClassVar

from struct import pack
from exabgp.util import hexstring

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.util.types import Buffer
from exabgp.util.intvalue import json_number

# Minimum data length for SR Adjacency SID TLV
# Flags (1) + Weight (1) + Reserved (2) = 4 bytes
SRADJ_MIN_LENGTH = 4
SID_LABEL_SIZE = 3  # a label, the 20 rightmost bits of three octets (RFC 9085 2.1.1)
SID_INDEX_SIZE = 4  # an index or a SID
SID_LABEL_MASK = 0xFFFFF


def decode_sids(data: Buffer, flags: dict[str, int]) -> tuple[list[int], tuple[str, ...]]:
    """The SIDs of an Adjacency or LAN Adjacency SID, and what could not be read as one.

    RFC 9085 2.2.1 and 2.2.2 carry one SID, "Either 7 or 8 octets depending on the label
    or index encoding of the SID", so three octets are a label and four an index.  The
    flags were asked first, read with the IS-IS layout because the attribute cannot see the
    Protocol-ID of the NLRI: an OSPF label (V and L are 0x60 in RFC 8665) read as IS-IS B
    and V, and was reported as undecoded.  The size is the same in every IGP, so it decides.
    Several SIDs, which the draft this was written from allowed, still follow the flags.
    """
    if len(data) == SID_LABEL_SIZE:
        return [int.from_bytes(data, 'big') & SID_LABEL_MASK], ()
    if len(data) == SID_INDEX_SIZE:
        return [int.from_bytes(data, 'big')], ()
    is_label = flags['V'] and flags['L']
    is_index = not flags['V'] and not flags['L']
    size = SID_LABEL_SIZE if is_label else SID_INDEX_SIZE
    sids: list[int] = []
    # each pass takes `size` octets or ends the loop, so it is bounded by the TLV
    while data:
        if not (is_label or is_index) or len(data) < size:
            return sids, (hexstring(data),)
        value = int.from_bytes(data[:size], 'big')
        sids.append(value & SID_LABEL_MASK if is_label else value)
        data = data[size:]
    return sids, ()


#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |               Type            |              Length           |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   | Flags         |     Weight    |             Reserved          |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                   SID/Label/Index (variable)                  |
#   +---------------------------------------------------------------+
#


class AdjacencySid(FlagLS):
    FLAGS: ClassVar = ['F', 'B', 'V', 'L', 'S', 'P', 'RSV', 'RSV']
    MERGE: ClassVar[bool] = True  # LinkState.json() groups into array

    # flags property is inherited from FlagLS and unpacks from _packed[0:1]

    @property
    def content(self) -> dict[str, object]:
        """Return dict representation for JSON grouping."""
        return {
            'flags': self.flags,
            'sids': self.sids,
            'weight': self.weight,
            'undecoded-sids': self.undecoded,
        }

    @property
    def weight(self) -> int:
        """Unpack and return the weight from packed bytes."""
        return self._packed[1]

    @property
    def sids(self) -> list[int]:
        """Unpack and return the SIDs from packed bytes."""
        return decode_sids(self._packed[4:], self.flags)[0]  # after Flags, Weight, Reserved

    @property
    def undecoded(self) -> tuple[str, ...]:
        """Unpack and return any undecoded SID data from packed bytes."""
        return decode_sids(self._packed[4:], self.flags)[1]

    def __repr__(self) -> str:
        return 'adj_flags: {}, sids: {}, undecoded_sid {}'.format(self.flags, self.sids, self.undecoded)

    def json(self, compact: bool = False) -> str:
        import json

        return f'"{self.JSON}": {json.dumps(self.content, default=json_number)}'

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> AdjacencySid:
        if len(data) < SRADJ_MIN_LENGTH:
            raise Notify.short(3, 5, 'SR Adjacency SID', SRADJ_MIN_LENGTH, len(data))
        return cls(data)

    @classmethod
    def make_adjacencysid(
        cls,
        flags: dict[str, int],
        weight: int,
        sids: list[int],
    ) -> AdjacencySid:
        """Create AdjacencySid from semantic values.

        Args:
            flags: Dict with keys F, B, V, L, S, P (RSV bits ignored)
            weight: Weight value (0-255)
            sids: List of SID values

        Returns:
            AdjacencySid instance with packed wire-format bytes
        """
        # Pack flags byte: F(7), B(6), V(5), L(4), S(3), P(2), RSV(1), RSV(0)
        flags_byte = (
            (flags.get('F', 0) << 7)
            | (flags.get('B', 0) << 6)
            | (flags.get('V', 0) << 5)
            | (flags.get('L', 0) << 4)
            | (flags.get('S', 0) << 3)
            | (flags.get('P', 0) << 2)
        )

        # Pack header: Flags(1) + Weight(1) + Reserved(2)
        packed = pack('!BBH', flags_byte, weight, 0)

        # Pack SIDs based on V and L flags
        v_flag = flags.get('V', 0)
        l_flag = flags.get('L', 0)
        for sid in sids:
            if v_flag and l_flag:
                # RFC 9085 2.1.1: the label is the 20 rightmost bits of three octets.  It
                # was shifted four bits left, so it read back sixteen times larger.
                packed += pack('!L', sid & SID_LABEL_MASK)[1:]
            else:
                # 4-byte index
                packed += pack('!I', sid)

        return cls(packed)


LinkState.register_lsid(tlv=1099, json_key='sr-adjs', repr_name='Adjacency SID')(AdjacencySid)
