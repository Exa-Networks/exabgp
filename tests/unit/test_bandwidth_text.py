"""A link bandwidth extended community prints as the configuration writes it.

It printed `bandwith:<asn>:<speed>`, a word no parser reads: the route shown by exabgp,
or written back by it, could not be given to it again.

It was also only decoded as a link bandwidth when something had imported its module first:
the package which registers every extended community did not, so a received community, or
one read from the configuration, printed as bandwidth or as a bare extended community
depending on what else the process had loaded.
"""

from __future__ import annotations

import subprocess
import sys

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


def test_the_extended_community_package_registers_bandwidth() -> None:
    """In a fresh interpreter, where no test has imported the bandwidth module already."""
    probe = (
        'from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity\n'
        'packed = bytes([0x40, 0x04, 0xfd, 0xe8]) + bytes(4)\n'
        'print(type(ExtendedCommunity.unpack_attribute(packed, None)).__name__)\n'
    )
    result = subprocess.run([sys.executable, '-c', probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == 'Bandwidth', result.stdout + result.stderr
