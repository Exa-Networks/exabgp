
"""labels.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack


# ======================================================================= Labels
# RFC 3107


def opt_raw_label(label, format=' (%d)'):
    return format % label if label else ''


class Labels:
    MAX = pow(2, 20) - 1

    NOLABEL: Labels | None = None

    def __init__(self, labels, bos=True, raw_labels=None):
        self.labels = labels
        self.raw_labels = raw_labels
        packed = []
        if raw_labels:
            for label in raw_labels:
                packed.append(pack('!L', label)[1:])
            # fill self.labels as well, not for packing, but to allow
            # consistent string representations
            if not self.labels:
                self.labels = [x >> 4 for x in self.raw_labels]
        else:
            for label in labels:
                # shift to 20 bits of the label to be at the top of three bytes and then truncate.
                packed.append(pack('!L', label << 4)[1:])
            # Mark the bottom of stack with the bit
            if packed and bos:
                packed.pop()
                packed.append(pack('!L', (label << 4) | 1)[1:])
            self.raw_labels = [None for _ in self.labels]
        self.packed = b''.join(packed)
        self._len = len(self.packed)

    def __eq__(self, other):
        return self.labels == other.labels

    def __neq__(self, other):
        return self.labels != other.labels

    def __lt__(self, other):
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def pack(self):
        return self.packed

    def __len__(self):
        return self._len

    def json(self):
        if len(self.labels) >= 1:
            return '"label": [ %s ]' % ', '.join(
                ['[%d%s]' % (label, opt_raw_label(raw, ', %d')) for (label, raw) in zip(self.labels, self.raw_labels)],
            )
        return ''

    def __str__(self):
        if len(self.labels) > 1:
            return ' label [ %s ]' % ' '.join(
                ['%d%s' % (label, opt_raw_label(raw)) for (label, raw) in zip(self.labels, self.raw_labels)],
            )
        if len(self.labels) == 1:
            return ' label %d%s' % (self.labels[0], opt_raw_label(self.raw_labels[0]))
        return ''

    def __repr__(self):
        if len(self.labels) > 1:
            return '[ %s ]' % ','.join(
                ['%d%s' % (label, opt_raw_label(raw)) for (label, raw) in zip(self.labels, self.raw_labels)],
            )
        if len(self.labels) == 1:
            return '%d%s' % (self.labels[0], opt_raw_label(self.raw_labels[0]))
        return '[ ]'

    @classmethod
    def unpack(cls, data):
        labels = []
        raw_labels = []
        while len(data):
            label = unpack('!L', bytes([0]) + data[:3])[0]
            data = data[3:]
            labels.append(label >> 4)
            raw_labels.append(label)
            if label & 0x001:
                break
        return cls(labels, raw_labels=raw_labels)


Labels.NOLABEL = Labels([])
