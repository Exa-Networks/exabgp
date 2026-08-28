"""test_link_local_local_address.py

A link-local local-address becomes the next-hop of every route announced with
"next-hop self", and an address with link scope is only a legal next-hop with
the link-local next-hop capability, towards a peer sharing the link.

These tests cover the three places which refuse the combination: configuration
validation, Neighbor.ip_self() for routes which never saw the parser, and the
encoding invariant behind both.

License: 3-clause BSD
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
from exabgp.bgp.neighbor.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IPv6
from exabgp.util.enumeration import TriState

from unittest.mock import Mock


def _parse(cfg: str) -> tuple[bool, Configuration]:
    c = Configuration([cfg], text=True)
    ok = c.reload()
    return ok, c


def _neighbor(local_address: str = 'fe80::2', capability: str = '', extra: str = '') -> str:
    return f"""neighbor fe80::1 {{
    router-id 10.0.0.2;
    local-address {local_address};
    local-as 65500;
    peer-as 65500;
    {extra}
    capability {{
        {capability}
    }}
    family {{ ipv6 unicast; }}
    static {{ route 2001:db8:1::/48 next-hop self; }}
}}"""


# ==============================================================================
# Configuration validation
# ==============================================================================


def test_link_local_local_address_without_the_capability_is_refused() -> None:
    ok, c = _parse(_neighbor())

    assert not ok
    assert 'link-local-nexthop enable' in str(c.error)


def test_link_local_local_address_on_a_multihop_session_is_refused() -> None:
    ok, c = _parse(_neighbor(capability='link-local-nexthop enable;', extra='outgoing-ttl 10;'))

    assert not ok
    assert 'multihop' in str(c.error)


def test_link_local_local_address_with_the_capability_is_accepted() -> None:
    ok, c = _parse(_neighbor(capability='link-local-nexthop enable;'))

    assert ok, c.error
    neighbor = next(iter(c.neighbors.values()))
    assert neighbor.session.local_address.is_link_local()


def test_a_global_local_address_is_never_questioned() -> None:
    # local-link-local is the supported way to carry a link-local next-hop, and
    # it puts no constraint on the session itself.
    ok, c = _parse(_neighbor(local_address='2001:db8::2', extra='outgoing-ttl 10;').replace('fe80::1', '2001:db8::1'))

    assert ok, c.error


# ==============================================================================
# Neighbor.ip_self(), the path taken by routes injected through the API
# ==============================================================================


def _configured_neighbor() -> Neighbor:
    ok, c = _parse(_neighbor(capability='link-local-nexthop enable;'))
    assert ok, c.error
    return next(iter(c.neighbors.values()))


def test_ip_self_returns_the_link_local_address_when_the_capability_is_on() -> None:
    neighbor = _configured_neighbor()

    assert neighbor.ip_self(AFI.ipv6) == IPv6.from_string('fe80::2')


def test_ip_self_refuses_once_the_capability_is_turned_off() -> None:
    neighbor = _configured_neighbor()
    neighbor.capability.link_local_nexthop = TriState.FALSE

    with pytest.raises(TypeError, match='link-local next-hop capability is not enabled'):
        neighbor.ip_self(AFI.ipv6)


def test_ip_self_refuses_on_a_multihop_session() -> None:
    neighbor = _configured_neighbor()
    neighbor.session.outgoing_ttl = 10

    with pytest.raises(TypeError, match='multihop'):
        neighbor.ip_self(AFI.ipv6)


def test_ip_self_still_falls_back_to_the_router_id_for_ipv4() -> None:
    neighbor = _configured_neighbor()

    assert str(neighbor.ip_self(AFI.ipv4)) == '10.0.0.2'


# ==============================================================================
# Encoding invariant
# ==============================================================================


def _negotiated(linklocal_nexthop: bool, is_multihop: bool) -> Mock:
    negotiated = Mock()
    negotiated.linklocal_nexthop = linklocal_nexthop
    negotiated.link_local_address = Mock(return_value=None)
    negotiated.is_multihop = Mock(return_value=is_multihop)
    return negotiated


def test_encoding_a_link_local_next_hop_without_the_capability_is_a_bug() -> None:
    collection = MPNLRICollection([], {}, AFI.ipv6, SAFI.unicast)
    nexthop = IPv6(IPv6.pton('fe80::2'))

    with pytest.raises(RuntimeError, match='link-local next-hop capability'):
        collection._encode_nexthop(nexthop, (AFI.ipv6, SAFI.unicast), _negotiated(False, False))


def test_encoding_a_link_local_next_hop_for_a_multihop_peer_is_a_bug() -> None:
    collection = MPNLRICollection([], {}, AFI.ipv6, SAFI.unicast)
    nexthop = IPv6(IPv6.pton('fe80::2'))

    with pytest.raises(RuntimeError, match='multihop'):
        collection._encode_nexthop(nexthop, (AFI.ipv6, SAFI.unicast), _negotiated(True, True))


def test_a_global_next_hop_is_untouched_on_both_paths() -> None:
    collection = MPNLRICollection([], {}, AFI.ipv6, SAFI.unicast)
    nexthop = IPv6(IPv6.pton('2001:db8::2'))
    packed = nexthop.pack_ip()

    assert collection._encode_nexthop(nexthop, (AFI.ipv6, SAFI.unicast), _negotiated(False, False)) == packed
    assert collection._encode_nexthop(nexthop, (AFI.ipv6, SAFI.unicast), _negotiated(True, True)) == packed
