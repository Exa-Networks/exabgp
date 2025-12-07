"""labels.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import ClassVar

from exabgp.util.types import Buffer

# ======================================================================= Labels
# RFC 3107


def opt_raw_label(label: int | None, format: str = ' (%d)') -> str:
    return format % label if label else ''


class Labels:
    MAX = pow(2, 20) - 1

    NOLABEL: ClassVar['Labels']

    def __init__(self, packed: Buffer) -> None:
        if len(packed) % 3 != 0:
            raise ValueError(f'Labels packed data must be multiple of 3 bytes, got {len(packed)}')
        self._packed = packed

    @classmethod
    def make_labels(cls, labels: list[int], bos: bool = True) -> 'Labels':
        """Create Labels from list of label integers."""
        if not labels:
            return cls(b'')
        packed_parts = []
        for i, label in enumerate(labels):
            # shift to 20 bits of the label to be at the top of three bytes
            value = label << 4
            # Mark the bottom of stack with the bit on last label
            if bos and i == len(labels) - 1:
                value |= 1
            packed_parts.append(pack('!L', value)[1:])
        return cls(b''.join(packed_parts))

    @property
    def labels(self) -> list[int]:
        """Extract label values from packed bytes."""
        result = []
        data = self._packed
        while len(data) >= 3:
            raw = unpack('!L', bytes([0]) + data[:3])[0]
            result.append(raw >> 4)
            data = data[3:]
        return result

    @property
    def raw_labels(self) -> list[int]:
        """Extract raw 24-bit values (includes TC/S bits) from packed bytes."""
        result = []
        data = self._packed
        while len(data) >= 3:
            raw = unpack('!L', bytes([0]) + data[:3])[0]
            result.append(raw)
            data = data[3:]
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Labels):
            return False
        return self._packed == other._packed

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing Labels for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing Labels for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing Labels for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing Labels for ordering does not make sense')

    def pack_labels(self) -> Buffer:
        return self._packed

    def __len__(self) -> int:
        return len(self._packed)

    def json(self) -> str:
        labels = self.labels
        raw_labels = self.raw_labels
        if len(labels) >= 1:
            return '"label": [ {} ]'.format(
                ', '.join(
                    ['[%d%s]' % (label, opt_raw_label(raw, ', %d')) for (label, raw) in zip(labels, raw_labels)],
                )
            )
        return ''

    def __str__(self) -> str:
        labels = self.labels
        raw_labels = self.raw_labels
        if len(labels) > 1:
            return ' label [ {} ]'.format(
                ' '.join(
                    ['%d%s' % (label, opt_raw_label(raw)) for (label, raw) in zip(labels, raw_labels)],
                )
            )
        if len(labels) == 1:
            return ' label %d%s' % (labels[0], opt_raw_label(raw_labels[0]))
        return ''

    def __repr__(self) -> str:
        labels = self.labels
        raw_labels = self.raw_labels
        if len(labels) > 1:
            return '[ {} ]'.format(
                ','.join(
                    ['%d%s' % (label, opt_raw_label(raw)) for (label, raw) in zip(labels, raw_labels)],
                )
            )
        if len(labels) == 1:
            return '%d%s' % (labels[0], opt_raw_label(raw_labels[0]))
        return '[ ]'

    @classmethod
    def unpack_labels(cls, data: Buffer) -> 'Labels':
        """Unpack labels from data, stopping at bottom-of-stack bit."""
        packed_parts = []
        while len(data) >= 3:
            chunk = data[:3]
            packed_parts.append(chunk)
            data = data[3:]
            raw = unpack('!L', bytes([0]) + chunk)[0]
            if raw & 0x001:  # bottom-of-stack bit
                break
        return cls(b''.join(packed_parts))


Labels.NOLABEL = Labels(b'')
