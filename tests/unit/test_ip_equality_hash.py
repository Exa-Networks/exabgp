"""Two addresses which compare equal hash alike, whatever class built them.

IP.__eq__ compared the packed bytes and IP.__hash__ hashed the class name with them, so an
IPv6 next hop and the NextHopWithLinkLocal decoded for the same address were equal yet
fell into different buckets: a set or a dict keyed on next hops held both, or missed one.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.mprnlri import NextHopWithLinkLocal
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP, IPSelf, IPv4, IPv6
from exabgp.protocol.ip.address import IPRange


def test_equal_addresses_of_different_classes_hash_alike() -> None:
    plain = IPv6.from_string('2001:db8::1')
    paired = NextHopWithLinkLocal(plain.pack_ip(), IPv6.from_string('fe80::1'))

    assert plain == paired
    assert hash(plain) == hash(paired)
    assert len({plain, paired}) == 1


def test_a_range_and_its_host_address_hash_alike_when_equal() -> None:
    host = IPv4.from_string('192.0.2.1')
    ranged = IPRange.make_range('192.0.2.1', 32)

    assert host == ranged
    assert hash(host) == hash(ranged)


def test_an_unresolved_next_hop_self_is_not_the_absence_of_a_next_hop() -> None:
    """Both packed to nothing, so they compared equal while hashing apart."""
    assert IPSelf(AFI.ipv4) != IP.NoNextHop
    assert IPSelf(AFI.ipv4) != IPSelf(AFI.ipv6)
    assert IPSelf(AFI.ipv4) == IPSelf(AFI.ipv4)
    assert hash(IPSelf(AFI.ipv4)) == hash(IPSelf(AFI.ipv4))


def test_different_addresses_are_not_equal() -> None:
    assert IPv4.from_string('192.0.2.1') != IPv4.from_string('192.0.2.2')
