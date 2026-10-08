"""sradjlan.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations


import json
from struct import pack
from typing import Any, ClassVar, TYPE_CHECKING

from exabgp.protocol.iso import ISO
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.update.attribute.bgpls.link.adjacencysid import SID_LABEL_MASK, decode_sids
from exabgp.protocol.ip import IPv4
from exabgp.util.types import Buffer
from exabgp.util.intvalue import json_number

# Minimum data length for SR Adjacency LAN SID TLV
# Flags (1) + Weight (1) + Reserved (2) + System-ID (6) = 10 bytes
SRADJ_LAN_MIN_LENGTH = 10
ISIS_NEIGHBOR_SIZE = 6  # an IS-IS System ID
OSPF_NEIGHBOR_SIZE = 4  # an OSPF Router-ID
# header (4) + an OSPF Router-ID (4) + a label (3) or an index (4), RFC 9085 2.2.2
OSPF_LAN_SIZES: tuple[int, int] = (11, 12)

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


class LanAdjacencySid(FlagLS):
    FLAGS: ClassVar = ['F', 'B', 'V', 'L', 'S', 'P', 'RSV', 'RSV']
    MERGE: ClassVar[bool] = True

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
            raise Notify.short(3, 5, 'SR Adjacency LAN SID', SRADJ_LAN_MIN_LENGTH, len(data))
        # The flags are read with the IS-IS layout: the Protocol-ID of the Link NLRI, which
        # RFC 9085 2.2.2 says decides, is not visible to the attribute (see the ledger).
        flags = cls.unpack_flags(data[0:1])
        weight = data[1]
        parsed: dict[str, Any] = {'flags': flags, 'weight': weight}
        # RFC 9085 2.2.2: "For IS-IS, it would be 13 or 14 octets ... For OSPF, it would be
        # 11 or 12 octets": the OSPF Neighbor ID is a four octet Router-ID, where IS-IS has a
        # six octet System ID.  Read as a System ID it took two octets of the SID with it.
        if len(data) in OSPF_LAN_SIZES:
            parsed['neighbor-id'] = str(IPv4.ntop(data[4:8]))
            sid_data = data[4 + OSPF_NEIGHBOR_SIZE :]
        else:
            parsed['system-id'] = ISO.unpack_sysid(data[4:10])
            sid_data = data[4 + ISIS_NEIGHBOR_SIZE :]
        sids, raw = decode_sids(sid_data, flags)
        # one SID per TLV in RFC 9085, so the last of several is the one reported, as before
        parsed['sid'] = sids[-1] if sids else 0
        parsed['undecoded'] = list(raw)
        return cls(data, [parsed])

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
            # RFC 9085 2.1.1: the label is the 20 rightmost bits of three octets.  It was
            # shifted four bits left, so it read back sixteen times larger.
            packed += pack('!L', sid & SID_LABEL_MASK)[1:]
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
        return f'"sr-adj-lan-sids": {json.dumps(self.sr_adj_lan_sids, default=json_number)}'

    def merge(self, other: BaseLS) -> None:
        if isinstance(other, LanAdjacencySid):
            self._sr_adj_lan_sids.extend(other.sr_adj_lan_sids)


LinkState.register_lsid(tlv=1100, json_key='sr-adj-lan', repr_name='LAN Adjacency SID')(LanAdjacencySid)
