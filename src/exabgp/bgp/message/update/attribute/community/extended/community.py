"""community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute

from struct import pack

# ======================================================= ExtendedCommunity (16)
# XXX: Should subclasses register with transitivity ?


class ExtendedCommunityBase(Attribute):
    SIZE = 8  # overridden by the IPv6 flavour
    COMMUNITY_TYPE = 0x00  # MUST be redefined by subclasses
    COMMUNITY_SUBTYPE = 0x00  # MUST be redefined by subclasses
    NON_TRANSITIVE = 0x40

    # Need to be overwritten by sub-classes
    registered_extended = None

    @classmethod
    def register(cls, klass):
        cls.registered_extended[(klass.COMMUNITY_TYPE & 0x0F, klass.COMMUNITY_SUBTYPE)] = klass
        return klass

    # size of value for data (boolean: is extended)
    length_value = {False: 7, True: 6}
    name = {False: 'regular', True: 'extended'}

    def __init__(self, community):
        # Two top bits are iana and transitive bits
        self.community = community
        self.klass = None

    def __eq__(self, other):
        if not isinstance(other, ExtendedCommunityBase):
            return NotImplemented
        return self.ID == other.ID and self.FLAG == other.FLAG and self.community == other.community

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other):
        return self.community < other.community

    def __le__(self, other):
        return self.community <= other.community

    def __gt__(self, other):
        return self.community > other.community

    def __ge__(self, other):
        return self.community >= other.community

    def iana(self):
        return not not (self.community[0] & 0x80)

    def transitive(self):
        # bit set means "not transitive"
        # RFC4360:
        #   T - Transitive bit
        #     Value 0: The community is transitive across ASes
        #     Value 1: The community is non-transitive across ASes
        return not (self.community[0] & 0x40)

    def pack(self, negotiated=None):
        return self.community

    def _subtype(self, transitive=True):
        # if not transitive -> set the 'transitive' bit, as per RFC4360
        return pack(
            '!BB',
            self.COMMUNITY_TYPE if transitive else self.COMMUNITY_TYPE | self.NON_TRANSITIVE,
            self.COMMUNITY_SUBTYPE,
        )

    def json(self):
        h = 0x00
        for byte in self.community:
            h <<= 8
            h += byte
        s = self.klass.__repr__(self) if self.klass else ''
        return '{{ "value": {}, "string": "{}" }}'.format(h, s)

    def __repr__(self):
        # a registered class which defines no __repr__ of its own inherits this
        # one, so delegating to it unconditionally called straight back into
        # here and exhausted the stack.  TrafficRedirectASN4 and
        # TrafficRedirectIPv6 are both in that position, and both are FlowSpec
        # redirect communities a peer can send on a plain unicast UPDATE.
        klass = self.klass
        if klass is not None and klass.__repr__ is not ExtendedCommunityBase.__repr__:
            return klass.__repr__(self)
        # the width comes from the community, not from a constant: '0x{:016X}' is
        # eight bytes wide and dropped the leading zeros of a twenty byte IPv6 one
        return '0x' + bytes(self.community).hex().upper()

    def __hash__(self):
        return hash(self.community)

    @classmethod
    def unpack(cls, data, direction=None, negotiated=None):
        # 30/02/12 Quagga communities for soo and rt are not transitive when 4360 says they must be, hence the & 0x0FFF
        # every registered decoder reads the full fixed width of its community,
        # so checking it once here keeps struct.error out of all of them
        if len(data) < cls.SIZE:
            raise Notify(3, 5, 'invalid extended community, expected %d bytes, got %d' % (cls.SIZE, len(data)))
        community = (data[0] & 0x0F, data[1])
        if community in cls.registered_extended:
            klass = cls.registered_extended[community]
            instance = klass.unpack(data)
            instance.klass = klass
            return instance
        return cls(data)


class ExtendedCommunity(ExtendedCommunityBase):
    ID = Attribute.CODE.EXTENDED_COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    registered_extended = {}
    SIZE = 8

    def __len__(self):
        return self.SIZE


class ExtendedCommunityIPv6(ExtendedCommunityBase):
    ID = Attribute.CODE.IPV6_EXTENDED_COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    registered_extended = {}
    SIZE = 20  # RFC 5701

    def __len__(self):
        return self.SIZE
