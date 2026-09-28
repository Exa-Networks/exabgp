"""A link bandwidth extended community prints as the configuration writes it.

It printed `bandwith:<asn>:<speed>`, a word no parser reads: the route shown by exabgp,
or written back by it, could not be given to it again.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.community.extended.bandwidth import Bandwidth
from exabgp.configuration.core.parser import Tokeniser
from exabgp.configuration.static.parser import extended_community


def test_bandwidth_prints_its_name() -> None:
    assert str(Bandwidth.make_bandwidth(65000, 1000.0)) == 'bandwidth:65000:1000'


def test_what_bandwidth_prints_reads_back_as_the_same_community() -> None:
    community = Bandwidth.make_bandwidth(65000, 1000.0)
    tokeniser = Tokeniser()
    tokeniser.replenish([str(community)])

    read = extended_community(tokeniser).communities[0]

    assert bytes(read.community) == bytes(community.community)
