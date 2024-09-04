# encoding: utf-8
"""
graceful.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.vendoring import six

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes_i
from exabgp.util import concat_bytes

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.open.capability.capability import Capability

# =========================================================== Graceful (Restart)
# RFC 4727 - https://tools.ietf.org/html/rfc4727


@Capability.register()
class Graceful(Capability, dict):
    MAX = 0xFFFF
    ID = Capability.CODE.GRACEFUL_RESTART

    TIME_MASK = 0x0FFF
    FLAG_MASK = 0xF000

    # 0x8 is binary 1000
    RESTART_STATE = 0x08
    FORWARDING_STATE = 0x80

    def set(self, restart_flag, restart_time, protos):
        self.restart_flag = restart_flag
        self.restart_time = restart_time & Graceful.TIME_MASK
        for afi, safi, family_flag in protos:
            self[(afi, safi)] = family_flag & Graceful.FORWARDING_STATE
        return self

    def extract(self):
        restart = pack('!H', ((self.restart_flag << 12) | (self.restart_time & Graceful.TIME_MASK)))
        families = [(afi.pack(), safi.pack(), character(self[(afi, safi)])) for (afi, safi) in self.keys()]
        sfamilies = concat_bytes_i(concat_bytes(pafi, psafi, family) for (pafi, psafi, family) in families)
        return [concat_bytes(restart, sfamilies)]

    def __str__(self):
        families = [(str(afi), str(safi), hex(self[(afi, safi)])) for (afi, safi) in self.keys()]
        sfamilies = ' '.join(["%s/%s=%s" % (afi, safi, family) for (afi, safi, family) in families])
        return "Graceful Restart Flags %s Time %d %s" % (hex(self.restart_flag), self.restart_time, sfamilies)

    def json(self):
        d = {
            'name': '"graceful restart"',
            'time': self.restart_time,
            'address-family-flags': '{ %s}'
            % (
                ', '.join(
                    '"%s/%s": [%s ] ' % ('%s' % afi, safi, ' "restart"' if family & 0x80 else '')
                    for afi, safi, family in [(str(a), str(s), self[(a, s)]) for (a, s) in self.keys()]
                )
            ),
            'restart-flags': '[%s] ' % (' "forwarding" ' if self.restart_flag & 0x8 else ' '),
        }

        return '{ %s}' % ', '.join('"%s": %s' % (k, v) for k, v in six.iteritems(d))

    def families(self):
        return self.keys()

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        # XXX: FIXME: should raise if instance was already setup
        restart = unpack('!H', data[:2])[0]
        restart_flag = restart >> 12
        restart_time = restart & Graceful.TIME_MASK
        data = data[2:]
        families = []
        while data:
            afi = AFI.unpack(data[:2])
            safi = SAFI.unpack(data[2])
            flag_family = ordinal(data[3])
            families.append((afi, safi, flag_family))
            data = data[4:]
        return instance.set(restart_flag, restart_time, families)
