"""sradjlan.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import pack, unpack
from typing import Any, TYPE_CHECKING

from exabgp.util import hexstring
from exabgp.protocol.iso import ISO
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.util.types import Buffer

# Minimum data length for SR Adjacency LAN SID TLV
# Flags (1) + Weight (1) + Reserved (2) + System-ID (6) = 10 bytes
SRADJ_LAN_MIN_LENGTH = 10

if TYPE_CHECKING:
    pass


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |              Type             |            Length             |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |     Flags     |     Weight    |            Reserved           |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |             OSPF Neighbor ID / IS-IS System-ID                |
#   +                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                               |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                    SID/Label/Index (variable)                 |
#   +---------------------------------------------------------------+
# 		draft-gredler-idr-bgp-ls-segment-routing-ext-03

#  draft-ietf-isis-segment-routing-extensions - Adj-SID IS-IS Flags


@LinkState.register_lsid(tlv=1100, json_key='sr-adj-lan', repr_name='LAN Adjacency SID')
class LanAdjacencySid(FlagLS):
    FLAGS = ['F', 'B', 'V', 'L', 'S', 'P', 'RSV', 'RSV']
    MERGE = True

    def __init__(self, packed: Buffer, parsed_sids: list[dict[str, Any]] | None = None) -> None:
        """Initialize with packed bytes and optionally pre-parsed content."""
        self._packed = packed
        self._sr_adj_lan_sids: list[dict[str, Any]] = parsed_sids if parsed_sids else []

    @property
    def sr_adj_lan_sids(self) -> list[dict[str, Any]]:
        """Return the parsed SR adjacency LAN SIDs."""
        return self._sr_adj_lan_sids

    def __repr__(self) -> str:
        return f'sr-adj-lan-sids: {self.sr_adj_lan_sids}'

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> LanAdjacencySid:
        if len(data) < SRADJ_LAN_MIN_LENGTH:
            raise Notify(
                3, 5, f'SR Adjacency LAN SID: data too short, need {SRADJ_LAN_MIN_LENGTH} bytes, got {len(data)}'
            )
        original_data = data
        # We only support IS-IS flags for now.
        flags = cls.unpack_flags(data[0:1])
        # Parse adj weight
        weight = data[1]
        # Move pointer 4 bytes: Flags(1) + Weight(1) + Reserved(2)
        system_id = ISO.unpack_sysid(data[4:10])
        data = data[10:]
        # SID/Index/Label: according to the V and L flags, it contains
        # either:
        # *  A 3 octet local label where the 20 rightmost bits are used for
        # 	 encoding the label value.  In this case the V and L flags MUST
        # 	 be set.
        #
        # *  A 4 octet index defining the offset in the SID/Label space
        # 	 advertised by this router using the encodings defined in
        #  	 Section 3.1.  In this case V and L flags MUST be unset.
        sids = []
        raw = []
        sid = 0  # Default value in case no SID is parsed
        while data:
            # Range Size: 3 octet value indicating the number of labels in
            # the range.
            if int(flags['V']) and int(flags['L']):
                sid = unpack('!L', bytes([0]) + data[:3])[0]
                data = data[3:]
                sids.append(sid)
            elif (not flags['V']) and (not flags['L']):
                sid = unpack('!I', data[:4])[0]
                data = data[4:]
                sids.append(sid)
            else:
                raw.append(hexstring(data))
                break

        parsed = [{'flags': flags, 'weight': weight, 'system-id': system_id, 'sid': sid, 'undecoded': raw}]
        return cls(original_data, parsed)

    @classmethod
    def make_adjacencysidlan(
        cls,
        flags: dict[str, int],
        weight: int,
        system_id: str,
        sid: int,
    ) -> LanAdjacencySid:
        """Create LanAdjacencySid from semantic values.

        Args:
            flags: Dict with keys F, B, V, L, S, P (RSV bits ignored)
            weight: Weight value (0-255)
            system_id: IS-IS System-ID as hex string (e.g., "0102.0304.0506" or "010203040506")
            sid: SID value

        Returns:
            LanAdjacencySid instance with packed wire-format bytes
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

        # Pack System-ID (6 bytes) - remove dots if present
        sysid_hex = system_id.replace('.', '')
        packed += bytes.fromhex(sysid_hex)

        # Pack SID based on V and L flags
        v_flag = flags.get('V', 0)
        l_flag = flags.get('L', 0)
        if v_flag and l_flag:
            # 3-byte label: 20-bit label value in upper bits
            packed += pack('!L', sid << 4)[1:]  # Take last 3 bytes
        else:
            # 4-byte index
            packed += pack('!I', sid)

        # Create parsed form for JSON output
        parsed = [
            {
                'flags': flags,
                'weight': weight,
                'system-id': sysid_hex,
                'sid': sid,
                'undecoded': [],
            }
        ]
        return cls(packed, parsed)

    def json(self, compact: bool = False) -> str:
        return f'"sr-adj-lan-sids": {json.dumps(self.sr_adj_lan_sids)}'

    def merge(self, other: BaseLS) -> None:
        if isinstance(other, LanAdjacencySid):
            self._sr_adj_lan_sids.extend(other.sr_adj_lan_sids)
