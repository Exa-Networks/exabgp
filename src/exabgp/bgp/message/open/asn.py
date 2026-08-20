"""asn.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.protocol.resource import Resource

# =================================================================== ASN


def _decimal(value):
    """True if the string is a plain ASCII decimal number (no sign, no separator)."""
    return bool(value) and value.isascii() and value.isdigit()


class ASN(Resource):
    MAX = pow(2, 16) - 1
    MAX_4BYTE = pow(2, 32) - 1

    DOTTED_PARTS = 2  # <high>.<low> notation has two components

    # ASN encoding size constants
    SIZE_4BYTE = 4  # 4-byte ASN encoding size
    SIZE_2BYTE = 2  # 2-byte ASN encoding size

    def asn4(self):
        return self > self.MAX

    def pack(self, negotiated=None):
        asn4 = negotiated if negotiated is not None else self.asn4()
        return pack('!L' if asn4 else '!H', self)

    @classmethod
    def unpack(cls, data, klass=None):
        kls = cls if klass is None else klass
        value = unpack('!L' if len(data) == cls.SIZE_4BYTE else '!H', data)[0]
        return kls(value)

    def __len__(self):
        return self.SIZE_4BYTE if self.asn4() else self.SIZE_2BYTE

    def extract(self):
        return [pack('!L', self)]

    def trans(self):
        if self.asn4():
            return AS_TRANS
        return self

    def __repr__(self):
        return '%ld' % int(self)

    def __str__(self):
        return '%ld' % int(self)

    @classmethod
    def from_string(cls, value):
        """Parse an ASN from its plain or dotted textual representation.

        Accepts "65001" (0 to 4294967295) and "1.1" (two components, each 0 to 65535).
        Anything else, a negative value, an out of range value, a wrong number of
        dotted components or a non decimal digit, raises ValueError.
        """
        if '.' in value:
            parts = value.split('.')
            if len(parts) != cls.DOTTED_PARTS:
                raise ValueError('"{}" is an invalid ASN, expecting <high>.<low> (for example 1.1)'.format(value))
            components = []
            for part in parts:
                if not _decimal(part):
                    raise ValueError('"{}" is an invalid ASN, "{}" is not a decimal number'.format(value, part))
                number = int(part)
                if number > cls.MAX:
                    raise ValueError('"{}" is an invalid ASN, each part must be 0 to {}'.format(value, cls.MAX))
                components.append(number)
            return cls((components[0] << 16) + components[1])

        if not _decimal(value):
            raise ValueError('"{}" is an invalid ASN, expecting a number or <high>.<low>'.format(value))

        as_number = int(value)
        if as_number > cls.MAX_4BYTE:
            raise ValueError('"{}" is an invalid ASN, must be 0 to {}'.format(value, cls.MAX_4BYTE))
        return cls(as_number)


AS_TRANS = ASN(23456)
