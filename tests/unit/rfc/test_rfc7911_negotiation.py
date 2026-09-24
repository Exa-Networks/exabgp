"""RFC 7911 section 4 and 5: when ADD-PATH is on, and for which direction.

The decode side of RFC 7911 is covered by
tests/unit/test_addpath_path_identifier_is_consumed.py, which is what found eight
families reading the identifier as part of the NLRI. This file is the other half: the
rules that decide whether those four octets are there at all.

That decision is asymmetric and easy to get backwards. ADD-PATH is negotiated per
direction and per family, and a speaker may only SEND multiple paths for a family if it
advertised send AND the peer advertised receive. Getting it wrong in one direction does
not fail loudly: it produces an UPDATE the peer reads from the wrong offset, which is the
same damage the decode bug caused, arriving from the other end.
"""

from __future__ import annotations


import pytest

from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.negotiated import RequirePath
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI

IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)

DISABLED = 0
RECEIVE = 1
SEND = 2
SEND_RECEIVE = 3


class Opened:
    """The capabilities of one OPEN, which is all RequirePath.setup reads."""

    def __init__(self, send_receive: int | None) -> None:
        self.capabilities: dict[int, AddPath] = {}
        if send_receive is not None:
            self.capabilities[Capability.CODE.ADD_PATH] = AddPath([IPV4_UNICAST], send_receive)


def negotiate(ours: int | None, theirs: int | None) -> RequirePath:
    """What the two OPENs agree, from our point of view.

    `ours` is what our own OPEN advertised and `theirs` what the peer's did. RequirePath
    calls the peer's OPEN `received_open` and ours `sent_open`.
    """
    require = RequirePath()
    require.setup(Opened(theirs), Opened(ours))
    return require


# every combination of what the two ends can say, and what RFC 7911 5 makes of it
AGREEMENTS = [
    # ours, theirs, may we send, may we receive
    (SEND_RECEIVE, SEND_RECEIVE, True, True),
    (SEND, RECEIVE, True, False),
    (RECEIVE, SEND, False, True),
    (SEND, SEND, False, False),
    (RECEIVE, RECEIVE, False, False),
    (SEND_RECEIVE, RECEIVE, True, False),
    (SEND_RECEIVE, SEND, False, True),
    (SEND, SEND_RECEIVE, True, False),
    (RECEIVE, SEND_RECEIVE, False, True),
    (DISABLED, SEND_RECEIVE, False, False),
    (SEND_RECEIVE, DISABLED, False, False),
    (None, SEND_RECEIVE, False, False),
    (SEND_RECEIVE, None, False, False),
    (None, None, False, False),
]
AGREEMENT_IDS = ['ours={} theirs={}'.format(ours, theirs) for ours, theirs, _, _ in AGREEMENTS]


@pytest.mark.rfc('rfc7911#5-send-requires-both-directions')
@pytest.mark.parametrize('ours,theirs,may_send,may_receive', AGREEMENTS, ids=AGREEMENT_IDS)
def test_sending_needs_our_send_and_their_receive(
    ours: int | None, theirs: int | None, may_send: bool, may_receive: bool
) -> None:
    """Both halves have to be present, and each half has to come from the right end.

    The table is exhaustive rather than illustrative because the failure this guards
    against is a swap: reading our own advertisement where the peer's belongs gives the
    right answer for send/receive on both sides and the wrong one for every asymmetric
    pair, which is most of this table.
    """
    require = negotiate(ours, theirs)

    assert require.send(*IPV4_UNICAST) is may_send
    assert require.receive(*IPV4_UNICAST) is may_receive


@pytest.mark.rfc('rfc7911#5-send-requires-both-directions', polarity='negative')
def test_a_peer_which_only_sends_does_not_let_us_send() -> None:
    """The case an implementation gets wrong by treating the capability as one flag.

    A peer advertising send/receive 2 is saying it will send us multiple paths. It has
    said nothing about being able to read them. If we take that as agreement and start
    prefixing our NLRI with path identifiers, the peer reads the identifier as the start
    of the NLRI and every route in the UPDATE after it is garbage.
    """
    require = negotiate(SEND_RECEIVE, SEND)

    assert not require.send(*IPV4_UNICAST), 'we would send path identifiers to a peer which never said it reads them'


@pytest.mark.rfc('rfc7911#5-extended-encoding-only-when-negotiated')
def test_a_family_which_was_not_named_is_not_enabled_by_another_which_was() -> None:
    """ADD-PATH is negotiated per family. Agreement about one says nothing about another."""
    require = RequirePath()
    require.setup(Opened(SEND_RECEIVE), Opened(SEND_RECEIVE))

    assert require.send(*IPV4_UNICAST)
    assert not require.send(AFI.ipv6, SAFI.unicast)
    assert not require.receive(AFI.ipv6, SAFI.unicast)
    assert not require.send(AFI.l2vpn, SAFI.evpn)


@pytest.mark.rfc('rfc7911#5-extended-encoding-only-when-negotiated', polarity='negative')
def test_nothing_is_enabled_when_neither_end_offered_the_capability() -> None:
    """The overwhelmingly common session, and the one a default must not break."""
    require = negotiate(None, None)

    for afi, safi in ((AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast), (AFI.ipv4, SAFI.mpls_vpn)):
        assert not require.send(afi, safi)
        assert not require.receive(afi, safi)


@pytest.mark.rfc('rfc7911#4-single-capability-instance')
def test_every_family_travels_in_one_capability() -> None:
    """RFC 7911 4: one instance of the capability carries all the AFI/SAFI pairs.

    `extract_capability_bytes` returning a list is what makes this worth asserting: a
    capability which needs to be split, as MP-BGP is, returns one element per instance,
    and ADD-PATH must not.
    """
    families = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
        (AFI.ipv4, SAFI.nlri_mpls),
        (AFI.ipv6, SAFI.nlri_mpls),
        (AFI.ipv4, SAFI.mpls_vpn),
        (AFI.ipv6, SAFI.mpls_vpn),
    ]
    capability = AddPath(families, SEND_RECEIVE)

    extracted = capability.extract_capability_bytes()

    assert len(extracted) == 1, f'ADD-PATH was split into {len(extracted)} capability instances'
    assert len(extracted[0]) == 4 * len(families), 'the single instance does not carry all six families'


@pytest.mark.rfc('rfc7911#2-identifier-uniquely-identifies-a-path')
def test_two_paths_for_one_prefix_stay_apart() -> None:
    """RFC 7911 2: (prefix, path identifier) has to identify a path on its own.

    `index()` is what the RIB stores a route under, so two paths for one prefix colliding
    there is the whole mechanism failing: the second advertisement replaces the first,
    which is exactly what ADD-PATH exists to stop.
    """
    # CIDR takes the NLRI wire form, a mask octet then only the significant bytes
    cidr = CIDR(bytes([24]) + b'\x0a\x00\x00', AFI.ipv4)

    first = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, PathInfo(bytes([0, 0, 0, 1])))
    second = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, PathInfo(bytes([0, 0, 0, 2])))
    again = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, PathInfo(bytes([0, 0, 0, 1])))

    assert first.index() != second.index(), 'two paths for one prefix share a RIB key'
    assert first.index() == again.index(), 'the same path taken twice does not land on the same key'
