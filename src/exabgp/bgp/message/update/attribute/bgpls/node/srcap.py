
"""
srcap.py

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


@LinkState.register()
class SrCapabilities(FlagLS):
    REPR = 'SR Capability Flags'
    JSON = 'sr-capability-flags'
    TLV = 1034
    FLAGS = ['I', 'V', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']

    def __init__(self, flags, sids):
        FlagLS.__init__(self, flags)
        self.sids = sids

    def __repr__(self):
        return '%s: %s, sids: %s' % (self.REPR, self.flags, self.sids)

    @classmethod
    def unpack(cls, data):
        # Extract node capability flags
        flags = cls.unpack_flags(data[0:1])
        # Move pointer past flags and reserved bytes
        data = data[2:]
        sids = []

        while data:
            # Range Size: 3 octet value indicating the number of labels in
            # the range.
            range_size = unpack('!L', bytes([0]) + data[:3])[0]

            # SID/Label: If length is set to 3, then the 20 rightmost bits
            # represent a label.  If length is set to 4, then the value
            # represents a 32 bit SID.
            sub_type, length = unpack('!HH', data[3:7])
            if sub_type != 1161:
                raise Notify(3, 5, f'Invalid sub-TLV type: {sub_type}')
            if length == 3:
                sids.append([range_size, unpack('!I', bytes([0]) + data[7 : length + 7])[0] & 0xFFFFF])
            elif length == 4:
                # XXX: really we are reading 7+ but then re-parsing it again ??
                sids.append([range_size, unpack('!I', data[7 : length + 7])[0]])
            data = data[length + 7 :]

        return cls(flags, sids)

    def json(self, compact=None):
        return f'{FlagLS.json(self)}, "sids": {self.sids}'
