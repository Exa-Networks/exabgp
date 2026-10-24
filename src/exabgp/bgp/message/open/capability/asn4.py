"""asn4.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.capability import Capability

# ========================================================================= ASN4
#


@Capability.register()
class ASN4(Capability, ASN):
    ID = Capability.CODE.FOUR_BYTES_ASN

    # This makes python2.6 complain !
    # def __init__ (self, value=0):
    # 	ASN.__init__(self,value)

    def __str__(self):
        return 'ASN4(%d)' % int(self)

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        # XXX: FIXME: if instance is not ASN(0) we have two ASN - raise
        # RFC 6793 section 3: the capability value is always a 4 octet AS number
        if len(data) != ASN.SIZE_4BYTE:
            raise Notify(2, 0, 'AS4 capability must be {} bytes long, got {}'.format(ASN.SIZE_4BYTE, len(data)))
        instance = ASN.unpack(data, ASN4)
        return instance

    def json(self):
        return '{ "name": "asn4", "asn4": %d }' % int(self)
