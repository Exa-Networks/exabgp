# encoding: utf-8
"""
labels.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.util import character
from exabgp.util import concat_bytes_i


# ======================================================================= Labels
# RFC 3107


def opt_raw_label(label, format=' (%d)'):
    return format % label if label else ''


class Labels(object):
    MAX = pow(2, 20) - 1

    __slots__ = ['labels', 'packed', '_len', 'raw_labels']

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
        self.packed = concat_bytes_i(packed)
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
                ["[%d%s]" % (l, opt_raw_label(r, ', %d')) for (l, r) in zip(self.labels, self.raw_labels)]
            )
        else:
            return ''

    def __str__(self):
        if len(self.labels) > 1:
            return ' label [ %s ]' % ' '.join(
                ["%d%s" % (l, opt_raw_label(r)) for (l, r) in zip(self.labels, self.raw_labels)]
            )
        elif len(self.labels) == 1:
            return ' label %d%s' % (self.labels[0], opt_raw_label(self.raw_labels[0]))
        else:
            return ''

    def __repr__(self):
        if len(self.labels) > 1:
            return '[ %s ]' % ','.join(["%d%s" % (l, opt_raw_label(r)) for (l, r) in zip(self.labels, self.raw_labels)])
        elif len(self.labels) == 1:
            return '%d%s' % (self.labels[0], opt_raw_label(self.raw_labels[0]))
        else:
            return '[ ]'

    @classmethod
    def unpack(cls, data):
        labels = []
        raw_labels = []
        while len(data):
            label = unpack('!L', character(0) + data[:3])[0]
            data = data[3:]
            labels.append(label >> 4)
            raw_labels.append(label)
            if label & 0x001:
                break
        return cls(labels, raw_labels=raw_labels)


Labels.NOLABEL = Labels([])
