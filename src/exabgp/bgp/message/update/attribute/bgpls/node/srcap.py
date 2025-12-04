"""srcap.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.notification import Notify

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#   0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |               Type            |               Length          |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |      Flags    |   RESERVED    |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                  Range Size                   |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   //                SID/Label Sub-TLV (variable)                 //
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#         SR Node Cap Flags
# 				+
#      One or more entries, each of which have the following format:
#
#         Range Size: 3 octet value indicating the number of labels in
#         the range.
#
#         SID/Label sub-TLV (as defined in Section 2.3.7.2).

# 	isis-segment-routing-extensions 3.1. SR-Capabilities Sub-TLV

# SR Capabilities constants
SRCAP_FLAGS_RESERVED_SIZE = 2  # Reserved bytes after flags
SRCAP_RANGE_SIZE_BYTES = 3  # Range size field is 3 octets
SRCAP_LABEL_SUB_TLV_TYPE = 1161  # SID/Label Sub-TLV type
SRCAP_LABEL_SIZE_3 = 3  # 20-bit label
SRCAP_LABEL_SIZE_4 = 4  # 32-bit SID
SRCAP_SUB_TLV_HEADER_SIZE = 4  # Type (2) + Length (2)
SRCAP_LABEL_MASK_20BIT = 0xFFFFF  # Mask for 20-bit label

# Minimum data length for SR Capabilities TLV
# Flags (1) + Reserved (1) = 2 bytes initial, then 7+ per SID entry
SRCAP_MIN_LENGTH = 2  # Minimum for flags + reserved
SRCAP_MIN_ENTRY_LENGTH = SRCAP_RANGE_SIZE_BYTES + SRCAP_SUB_TLV_HEADER_SIZE  # 7 bytes per entry header


@LinkState.register_lsid()
class SrCapabilities(FlagLS):
    REPR = 'SR Capability Flags'
    JSON = 'sr-capability-flags'
    TLV = 1034
    FLAGS = ['I', 'V', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']

    # flags property is inherited from FlagLS and unpacks from _packed[0:1]

    @property
    def sids(self) -> list[list[int]]:
        """Unpack and return the SIDs from packed bytes."""
        data = self._packed[SRCAP_FLAGS_RESERVED_SIZE:]
        sids = []

        while data:
            if len(data) < SRCAP_MIN_ENTRY_LENGTH:
                break
            range_size = unpack('!L', bytes([0]) + data[:SRCAP_RANGE_SIZE_BYTES])[0]
            sub_type, length = unpack(
                '!HH', data[SRCAP_RANGE_SIZE_BYTES : SRCAP_RANGE_SIZE_BYTES + SRCAP_SUB_TLV_HEADER_SIZE]
            )
            if sub_type != SRCAP_LABEL_SUB_TLV_TYPE:
                break
            total_entry_size = SRCAP_RANGE_SIZE_BYTES + SRCAP_SUB_TLV_HEADER_SIZE + length
            if len(data) < total_entry_size:
                break
            if length == SRCAP_LABEL_SIZE_3:
                start = SRCAP_RANGE_SIZE_BYTES + SRCAP_SUB_TLV_HEADER_SIZE
                sids.append(
                    [range_size, unpack('!I', bytes([0]) + data[start : start + length])[0] & SRCAP_LABEL_MASK_20BIT]
                )
            elif length == SRCAP_LABEL_SIZE_4:
                start = SRCAP_RANGE_SIZE_BYTES + SRCAP_SUB_TLV_HEADER_SIZE
                sids.append([range_size, unpack('!I', data[start : start + length])[0]])
            data = data[length + SRCAP_RANGE_SIZE_BYTES + SRCAP_SUB_TLV_HEADER_SIZE :]

        return sids

    def __repr__(self) -> str:
        return '{}: {}, sids: {}'.format(self.REPR, self.flags, self.sids)

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> SrCapabilities:
        if len(data) < SRCAP_MIN_LENGTH:
            raise Notify(3, 5, f'SR Capabilities: data too short, need {SRCAP_MIN_LENGTH} bytes, got {len(data)}')
        # Validate structure before storing
        offset = SRCAP_FLAGS_RESERVED_SIZE
        while offset < len(data):
            if len(data) - offset < SRCAP_MIN_ENTRY_LENGTH:
                raise Notify(3, 5, f'SR Capabilities: entry data too short, need {SRCAP_MIN_ENTRY_LENGTH} bytes')
            sub_type, length = unpack(
                '!HH',
                data[offset + SRCAP_RANGE_SIZE_BYTES : offset + SRCAP_RANGE_SIZE_BYTES + SRCAP_SUB_TLV_HEADER_SIZE],
            )
            if sub_type != SRCAP_LABEL_SUB_TLV_TYPE:
                raise Notify(3, 5, f'Invalid sub-TLV type: {sub_type}')
            total_entry_size = SRCAP_RANGE_SIZE_BYTES + SRCAP_SUB_TLV_HEADER_SIZE + length
            if len(data) - offset < total_entry_size:
                raise Notify(3, 5, 'SR Capabilities: SID/Label data too short')
            offset += total_entry_size
        return cls(data)

    def json(self, compact: bool = False) -> str:
        return f'{FlagLS.json(self)}, "sids": {self.sids}'
