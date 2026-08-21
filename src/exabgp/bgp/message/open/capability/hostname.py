"""hostname.py

Created by Thomas Mangin on 2015-05-16.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# https://datatracker.ietf.org/doc/html/draft-walton-bgp-hostname-capability-02

from __future__ import annotations
import json

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.open.capability.capability import decode_utf8 as _decode_utf8
from exabgp.bgp.message.notification import Notify
from exabgp.util.dns import host, domain
from exabgp.util.types import Buffer


@Capability.register()
class HostName(Capability):
    ID = Capability.CODE.HOSTNAME
    HOSTNAME_MAX_LEN = 64

    def __init__(self, host_name: str | None = None, domain_name: str | None = None) -> None:
        """The names default to this host's, looked up when one is built.

        They used to be default *arguments*, so socket.gethostname() and socket.getfqdn()
        ran when this module was imported: 129ms on every start, a name frozen at import
        rather than read when it is used, and a resolver initialised in every process which
        merely imports exabgp. On macOS that last one makes the process unsafe to fork,
        which is why every mutmut worker died with SIGSEGV and mutation testing has never
        produced a verdict on this tree.
        """
        self.host_name: str = host() if host_name is None else host_name
        self.domain_name: str = domain() if domain_name is None else domain_name

    def __str__(self) -> str:
        return 'Hostname({} {})'.format(self.host_name, self.domain_name)

    def json(self) -> str:
        return '{{ "host-name": {}, "domain-name": {} }}'.format(
            json.dumps(self.host_name),
            json.dumps(self.domain_name),
        )

    def extract_capability_bytes(self) -> list[bytes]:
        # Return empty list (not [b'']) when no hostname - capability should not be sent
        if not self.host_name:
            return []

        hostname = self.host_name.encode('utf-8')
        if len(hostname) > self.HOSTNAME_MAX_LEN:
            hostname = hostname[: self.HOSTNAME_MAX_LEN]
        ret = bytes([len(hostname)]) + hostname

        if self.domain_name:
            domainname = self.domain_name.encode('utf-8')
            if len(domainname) > self.HOSTNAME_MAX_LEN:
                domainname = domainname[: self.HOSTNAME_MAX_LEN]
            ret += bytes([len(domainname)]) + domainname
        else:
            ret += bytes([0]) + b''

        return [ret]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, HostName)
        # Hostname capability: hostname_len(1) + hostname + domain_len(1) + domain
        if len(data) < 1:
            raise Notify(2, 0, 'Hostname capability too short: need at least 1 byte')
        l1 = data[0]
        if len(data) < l1 + 2:
            raise Notify(2, 0, f'Hostname capability truncated: need {l1 + 2} bytes for hostname, got {len(data)}')
        instance.host_name = _decode_utf8(data[1 : l1 + 1], 'host name')
        l2 = data[l1 + 1]
        if len(data) < l1 + 2 + l2:
            raise Notify(2, 0, f'Hostname capability truncated: need {l1 + 2 + l2} bytes total, got {len(data)}')
        instance.domain_name = _decode_utf8(data[l1 + 2 : l1 + 2 + l2], 'domain name')
        return instance
