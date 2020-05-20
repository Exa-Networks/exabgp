# encoding: utf-8
"""
asn4.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.capability import Capability

# ========================================================================= ASN4
#


@Capability.register()
class ExtendedMessage(Capability):
    ID = Capability.CODE.EXTENDED_MESSAGE
    INITIAL_SIZE = 4096
    EXTENDED_SIZE = 65535

    def __str__(self):
        return 'Extended Message(%d)' % self.EXTENDED_SIZE

    def extract(self):
        return [b'']

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        return ExtendedMessage()

    def json(self):
        return '{ "name": "extended-message", "size": %d }' % self.EXTENDED_SIZE
