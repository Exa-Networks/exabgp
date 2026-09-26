"""A BGP-LS prefix NLRI is not malformed for excluding an optional TLV.

RFC 7752 section 3.2 lists both Local Node Descriptors and IP Reachability Information as
mandatory, and this decoder answered a missing one of either with Notify(3, 10), which closes
the session. Only one of the two is load bearing:

- without IP Reachability the accessors have nothing to read and json() fails, so that one is
  still refused.
- Local Node Descriptors are read by nothing on this path. A prefix NLRI without them decoded
  and rendered before, so refusing it drops a route on upgrade for no gain. RFC 9552 8.2.2 is
  explicit that an NLRI is not to be called malformed over the inclusion or exclusion of
  optional TLVs, and `link.py` in the same package already accepts their absence
  (`self.local_node = local_node if local_node else []`).

main resolved it the same way and its comment records the same reasoning.
"""

from __future__ import annotations

from struct import pack
from typing import Any

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.bgpls.prefixv4 import PREFIXv4
from exabgp.bgp.message.update.nlri.bgpls.prefixv6 import PREFIXv6
from exabgp.environment import getenv
from exabgp.logger import log

log.init(getenv())

TLV_LOCAL_NODE_DESC = 256
TLV_IP_REACHABILITY = 265
TLV_OSPF_ROUTE_TYPE = 264

CLASSES = [PREFIXv4, PREFIXv6]
MEMBERS = ('flags', 'ls-nlri-type', 'l3-routing-topology', 'protocol-id')


def tlv(code: int, value: bytes) -> bytes:
    return pack('!HH', code, len(value)) + value


LOCAL_NODE = tlv(TLV_LOCAL_NODE_DESC, pack('!HH', 512, 4) + b'\x00\x00\xff\xfd')
IP_REACH_V4 = tlv(TLV_IP_REACHABILITY, bytes([24]) + bytes([10, 0, 0]))
IP_REACH_V6 = tlv(TLV_IP_REACHABILITY, bytes([32]) + bytes([0x20, 0x01, 0x0D, 0xB8]))
HEAD = b'\x03' + b'\x00' * 8


def reach(klass: Any) -> bytes:
    return IP_REACH_V4 if klass is PREFIXv4 else IP_REACH_V6


@pytest.mark.parametrize('klass', CLASSES)
def test_both_tlvs_present_still_decodes(klass: Any) -> None:
    """The control: the ordinary shape must be unaffected."""
    nlri = klass.unpack_nlri(HEAD + LOCAL_NODE + reach(klass), rd=None)

    assert nlri is not None
    assert nlri.local_node


@pytest.mark.parametrize('klass', CLASSES)
def test_no_local_node_descriptors_is_accepted(klass: Any) -> None:
    """The defect: this used to be Notify(3, 10) and a closed session."""
    nlri = klass.unpack_nlri(HEAD + reach(klass), rd=None)

    assert nlri is not None


@pytest.mark.parametrize('klass', CLASSES)
def test_an_nlri_without_local_node_descriptors_still_renders(klass: Any) -> None:
    """Accepting it is only useful if what we then do with it works."""
    nlri = klass.unpack_nlri(HEAD + reach(klass), rd=None)

    rendered = nlri.json()

    assert rendered.startswith('{')
    assert rendered.endswith('}')
    assert nlri.local_node == [] or not nlri.local_node
    assert str(nlri)


@pytest.mark.parametrize('klass', CLASSES)
def test_no_ip_reachability_is_still_refused(klass: Any) -> None:
    """The half which IS load bearing: without it the accessors have nothing to read."""
    with pytest.raises(Notify) as raised:
        klass.unpack_nlri(HEAD + LOCAL_NODE, rd=None)

    assert 'IP Reachability Information' in str(raised.value)


@pytest.mark.parametrize('klass', CLASSES)
def test_neither_tlv_is_refused_for_the_reachability_one(klass: Any) -> None:
    """With both absent the message must name the one that matters, not the other."""
    with pytest.raises(Notify) as raised:
        klass.unpack_nlri(HEAD, rd=None)

    assert 'IP Reachability Information' in str(raised.value)
    assert 'Local Node Descriptors' not in str(raised.value)


@pytest.mark.parametrize('klass', CLASSES)
def test_an_optional_tlv_alongside_is_no_obstacle(klass: Any) -> None:
    """An OSPF route type TLV with no local node descriptors is still a route."""
    body = HEAD + tlv(TLV_OSPF_ROUTE_TYPE, bytes([2])) + reach(klass)

    nlri = klass.unpack_nlri(body, rd=None)

    assert nlri is not None


@pytest.mark.parametrize('klass', CLASSES)
def test_the_two_shapes_do_not_share_a_rib_key(klass: Any) -> None:
    """Accepting a second shape must not make it indistinguishable from the first."""
    with_descriptors = klass.unpack_nlri(HEAD + LOCAL_NODE + reach(klass), rd=None)
    without = klass.unpack_nlri(HEAD + reach(klass), rd=None)

    assert with_descriptors.index() != without.index()
    assert with_descriptors != without
