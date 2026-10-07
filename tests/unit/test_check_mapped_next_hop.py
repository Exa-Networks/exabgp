"""The self-check reads an IPv4 next hop on an IPv6 route back as the IPv4-mapped address sent.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os

from exabgp.configuration.check import _as_mapped_next_hop, check_generation
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.ip import IP

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_an_ipv4_next_hop_sent_mapped_reads_back_mapped() -> None:
    text = 'dead::/128 next-hop 170.170.170.170'
    configured = IP.from_string('170.170.170.170')
    decoded = IP.from_string('::ffff:170.170.170.170')
    assert _as_mapped_next_hop(text, configured, decoded) == 'dead::/128 next-hop ::ffff:170.170.170.170'


def test_a_different_next_hop_is_not_hidden() -> None:
    text = 'dead::/128 next-hop 170.170.170.170'
    configured = IP.from_string('170.170.170.170')
    decoded = IP.from_string('::ffff:170.170.170.171')
    assert _as_mapped_next_hop(text, configured, decoded) == text


def test_the_extended_next_hop_example_validates() -> None:
    configuration = Configuration([os.path.join(ROOT, 'etc', 'exabgp', 'extended-nexthop.conf')])
    assert configuration.reload()
    assert check_generation(configuration.neighbors)
