"""labels.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations
from typing import List, Optional, Type

from struct import pack
from struct import unpack


# ======================================================================= Labels
# RFC 3107


def opt_raw_label(label: Optional[int], format: str = ' (%d)') -> str:
    return format % label if label else ''


class Labels:
    MAX = pow(2, 20) - 1

    NOLABEL: Optional[Labels] = None

    def __init__(self, labels: List[int], bos: bool = True, raw_labels: Optional[List[int]] = None) -> None:
        self.labels: List[int] = labels
        self.raw_labels: List[Optional[int]] = raw_labels if raw_labels else []
        packed = []
        if raw_labels:
            for label in raw_labels:
                packed.append(pack('!L', label)[1:])
            # fill self.labels as well, not for packing, but to allow
            # consistent string representations
            if not self.labels:
                self.labels = [x >> 4 for x in raw_labels]
        else:
            for label in labels:
                # shift to 20 bits of the label to be at the top of three bytes and then truncate.
                packed.append(pack('!L', label << 4)[1:])
            # Mark the bottom of stack with the bit
            if packed and bos:
                packed.pop()
                packed.append(pack('!L', (label << 4) | 1)[1:])
            self.raw_labels = [None for _ in self.labels]
        self.packed: bytes = b''.join(packed)
        self._len: int = len(self.packed)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Labels):
            return False
        return self.labels == other.labels

    def __neq__(self, other: object) -> bool:
        if not isinstance(other, Labels):
            return True
        return self.labels != other.labels

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def pack(self) -> bytes:
        return self.packed

    def __len__(self) -> int:
        return self._len

    def json(self) -> str:
        if len(self.labels) >= 1:
            return '"label": [ {} ]'.format(
                ', '.join(
                    [
                        '[%d%s]' % (label, opt_raw_label(raw, ', %d'))
                        for (label, raw) in zip(self.labels, self.raw_labels)
                    ],
                )
            )
        return ''

    def __str__(self) -> str:
        if len(self.labels) > 1:
            return ' label [ {} ]'.format(
                ' '.join(
                    ['%d%s' % (label, opt_raw_label(raw)) for (label, raw) in zip(self.labels, self.raw_labels)],
                )
            )
        if len(self.labels) == 1:
            return ' label %d%s' % (self.labels[0], opt_raw_label(self.raw_labels[0]))
        return ''

    def __repr__(self) -> str:
        if len(self.labels) > 1:
            return '[ {} ]'.format(
                ','.join(
                    ['%d%s' % (label, opt_raw_label(raw)) for (label, raw) in zip(self.labels, self.raw_labels)],
                )
            )
        if len(self.labels) == 1:
            return '%d%s' % (self.labels[0], opt_raw_label(self.raw_labels[0]))
        return '[ ]'

    @classmethod
    def unpack_labels(cls: Type[Labels], data: bytes) -> Labels:
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
