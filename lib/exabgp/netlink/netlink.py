# encoding: utf-8
"""
netlink.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import socket
from struct import pack
from struct import unpack
from struct import calcsize
from collections import namedtuple

from exabgp.netlink import NetLinkError
from exabgp.netlink.sequence import Sequence
from exabgp.netlink.attributes import Attributes


try:
    getattr(socket, 'AF_NETLINK')
except AttributeError:
    raise ImportError('This module only works on unix version with netlink support')


# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                                                               |
# |                   Netlink message header                      |
# |                                                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                                                               |
# |                  IP Service Template                          |
# |                                                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                                                               |
# |                  IP Service specific data in TLVs             |
# |                                                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

# The Netlink message header

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                          Length                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |            Type              |           Flags              |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                      Sequence Number                        |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                      Process ID (PID)                       |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class NetLink(object):
    _IGNORE_SEQ_FAULTS = True

    NETLINK_ROUTE = 0

    format = namedtuple('Message', 'format_type control_flags sequence pid data')
    netlink = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_ROUTE)

    class Header(object):
        # linux/netlink.h
        PACK = 'IHHII'
        LEN = calcsize(PACK)

    class Command(object):
        NLMSG_NOOP = 0x01
        NLMSG_ERROR = 0x02
        NLMSG_DONE = 0x03
        NLMSG_OVERRUN = 0x04

    class Flags(object):
        NLM_F_REQUEST = 0x01  # It is query message.
        NLM_F_MULTI = 0x02  # Multipart message, terminated by NLMSG_DONE
        NLM_F_ACK = 0x04  # Reply with ack, with zero or error code
        NLM_F_ECHO = 0x08  # Echo this query

        # Modifiers to GET query
        NLM_F_ROOT = 0x100  # specify tree root
        NLM_F_MATCH = 0x200  # return all matching
        NLM_F_DUMP = NLM_F_ROOT | NLM_F_MATCH
        NLM_F_ATOMIC = 0x400  # atomic GET

        # Modifiers to NEW query
        NLM_F_REPLACE = 0x100  # Override existing
        NLM_F_EXCL = 0x200  # Do not touch, if it exists
        NLM_F_CREATE = 0x400  # Create, if it does not exist
        NLM_F_APPEND = 0x800  # Add to end of list

    errors = {
        Command.NLMSG_ERROR: 'netlink error',
        Command.NLMSG_OVERRUN: 'netlink overrun',
    }

    @classmethod
    def encode(cls, format_type, sequence, control_flags, pid, body, attributes):
        attrs = Attributes.encode(attributes)
        length = cls.Header.LEN + len(attrs) + len(body)
        return pack(cls.Header.PACK, length, format_type, control_flags, sequence, pid) + body + attrs

    @classmethod
    def decode(cls, data):
        while data:
            length, format_type, control_flags, sequence, pid = unpack(cls.Header.PACK, data[: cls.Header.LEN])
            if len(data) < length:
                raise NetLinkError("Buffer underrun")
            yield cls.format(format_type, control_flags, sequence, pid, data[cls.Header.LEN : length])
            data = data[length:]

    # pack('Bxxx', family),
    # family=socket.AF_UNSPEC,

    @classmethod
    def send(cls, format_type, control_flags, family=socket.AF_UNSPEC, attributes=None):
        sequence = Sequence()
        pid = os.getpid()

        if attributes is None:
            attributes = {}

        message = cls.encode(format_type, sequence, control_flags, pid, pack('Bxxx', family), attributes)

        cls.netlink.send(message)

        while True:
            response = cls.netlink.recv(640000)
            for response_type, response_flags, response_sequence, response_pid, response_data in cls.decode(response):
                if response_sequence != sequence:
                    if cls._IGNORE_SEQ_FAULTS:
                        continue
                    raise NetLinkError("netlink sequence mismatch")
                elif response_pid != pid:
                    raise NetLinkError("netlink pid mismatch")
                # elif response_flags != control_flags:
                # 	raise NetLinkError("netlink flags mismatch")
                elif response_type in cls.errors:
                    raise NetLinkError(cls.errors[response_type], message, response)

                if response_type == NetLink.Command.NLMSG_DONE:
                    raise StopIteration()
                yield response_data
