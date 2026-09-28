"""A netmask knows the address family it belongs to, whatever other mask of its length was made.

Resource caches its instances by value, so every NetMask of one length was one object, and
make_netmask set `maximum` on it: 32 for IPv4, 128 for IPv6, the last caller winning. An
IPv6 /32 prefix therefore made an IPv4 /32 mask count 2**96 addresses. An IPv4 neighbor
announcing an IPv6 /32 route was refused, "can only use ip ranges for the peer address with
passive neighbors", and the host bits of an IPv4 prefix were checked against a 128 bit mask.
"""

from __future__ import annotations

from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IPRange
from exabgp.protocol.ip.netmask import NetMask


def test_an_ipv6_mask_leaves_the_ipv4_mask_of_its_length_alone() -> None:
    ipv4 = NetMask.make_netmask(32, AFI.ipv4)
    NetMask.make_netmask(32, AFI.ipv6)

    assert ipv4.size() == 1
    assert ipv4.hostmask() == 0


def test_an_ipv4_mask_leaves_the_ipv6_mask_of_its_length_alone() -> None:
    ipv6 = NetMask.make_netmask(24, AFI.ipv6)
    NetMask.make_netmask(24, AFI.ipv4)

    assert ipv6.size() == pow(2, 128 - 24)


def test_a_range_keeps_its_size_after_a_prefix_of_the_other_family() -> None:
    peer = IPRange.make_range('127.0.0.1', 32)
    IPRange.make_range('2001:db8::', 32)

    assert peer.mask.size() == 1


def test_a_copied_mask_keeps_its_family() -> None:
    import copy
    import pickle

    ipv4 = NetMask.make_netmask(16, AFI.ipv4)
    ipv6 = NetMask.make_netmask(16, AFI.ipv6)

    # rebuilt by value, the copies of both families would be one object again
    for duplicate in (copy.copy, copy.deepcopy, lambda mask: pickle.loads(pickle.dumps(mask))):
        copied_ipv4, copied_ipv6 = duplicate(ipv4), duplicate(ipv6)
        assert copied_ipv4.size() == pow(2, 16)
        assert copied_ipv6.size() == pow(2, 112)


def test_an_ipv4_neighbor_may_announce_an_ipv6_slash_32() -> None:
    text = (
        'neighbor 127.0.0.1 { router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002; '
        'static { route 2001:db8::/32 next-hop 2001:db8::1; } }'
    )
    configuration = Configuration([text], text=True)

    assert configuration.reload(), str(configuration.error)
