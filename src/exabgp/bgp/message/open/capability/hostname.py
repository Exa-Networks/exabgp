
"""
hostname.py

Created by Thomas Mangin on 2015-05-16.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# https://datatracker.ietf.org/doc/html/draft-walton-bgp-hostname-capability-02

from __future__ import annotations

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.util.dns import host, domain


@Capability.register()
class HostName(Capability):
    ID = Capability.CODE.HOSTNAME
    HOSTNAME_MAX_LEN = 64

    def __init__(self, host_name=host(), domain_name=domain()):
        self.host_name = host_name
        self.domain_name = domain_name

    def __str__(self):
        return 'Hostname(%s %s)' % (self.host_name, self.domain_name)

    def json(self):
        return '{ "host-name": "%s", "domain-name": "%s" }' % (self.host_name, self.domain_name)

    def extract(self):
        ret = b''

        if self.host_name:
            hostname = self.host_name.encode('utf-8')
            if len(hostname) > self.HOSTNAME_MAX_LEN:
                hostname = hostname[: self.HOSTNAME_MAX_LEN]
            ret += bytes([len(hostname)]) + hostname

            if self.domain_name:
                domainname = self.domain_name.encode('utf-8')
                if len(domainname) > self.HOSTNAME_MAX_LEN:
                    domainname = domainname[: self.HOSTNAME_MAX_LEN]
                ret += bytes([len(domainname)]) + domainname
            else:
                ret += bytes([0]) + b''

        return [ret]

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        l1 = data[0]
        instance.host_name = data[1 : l1 + 1].decode('utf-8')
        l2 = data[l1 + 1]
        instance.domain_name = data[l1 + 2 : l1 + 2 + l2].decode('utf-8')
        return instance
