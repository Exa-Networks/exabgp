# encoding: utf-8
"""
message.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import socket
from struct import unpack
from collections import namedtuple

from exabgp.netlink.attributes import Attributes
from exabgp.netlink.netlink import NetLink


class Message(object):
    # to be defined by the subclasses
    format = namedtuple('Parent', 'to be subclassed')

    DEFAULT_FLAGS = NetLink.Flags.NLM_F_REQUEST | NetLink.Flags.NLM_F_DUMP

    # to be defined by the subclasses
    class Header(object):
        PACK = ''
        LEN = 0

    @classmethod
    def decode(cls, data):
        extracted = list(unpack(cls.Header.PACK, data[: cls.Header.LEN]))
        attributes = Attributes.decode(data[cls.Header.LEN :])
        extracted.append(dict(attributes))
        return cls.format(*extracted)

    @classmethod
    def extract(cls, format_type, control_flags=DEFAULT_FLAGS, family=socket.AF_UNSPEC, attributes=None):
        for data in NetLink.send(format_type, control_flags, family, attributes):
            yield cls.decode(data)
