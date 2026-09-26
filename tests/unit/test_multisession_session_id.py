#!/usr/bin/env python3
# encoding: utf-8
"""test_multisession_session_id.py

The MULTISESSION capability's Session Id was never decoded.

draft-ietf-idr-bgp-multisession-07 section 4 gives the capability value as one octet of
flags followed by the Session Id, "list of zero or more capability codes (1 octet each)
defined in BGP, whose values will be used to distinguish one group from another".
`MultiSession.unpack_capability` discarded its `data` argument, so every peer's Session Id
decoded to the empty list whatever the peer sent.  `Negotiated._negotiate` then replaced an
empty received set with the same hardcoded {MULTIPROTOCOL} default it uses for our own
empty set, so the two sides always compared equal and the refusal section 7 makes a MUST,

    "local BGP speaker MUST send NOTIFICATION message with Error Code set to 2 ("OPEN
    Message Error") and Error Sub-code set to 8 ("Grouping Conflict") and drop the session"

could not be reached: a peer whose Session Id was a different set was silently accepted.

The same block read `sent_capa[MULTISESSION]` on the branch which negotiated under the code
Cisco uses, and compared `recv_capa[capa]` for a capability the peer need not have
announced at all.  The second of those was live: a peer offering MULTISESSION and no
MULTIPROTOCOL raised KeyError out of the OPEN parser, resetting the session with no
NOTIFICATION sent.

License: 3-clause BSD. (See the COPYRIGHT file)
"""

import json

import pytest

from exabgp.bgp.message.open import ASN
from exabgp.bgp.message.open import HoldTime
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open import RouterID
from exabgp.bgp.message.open import Version
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI


# the MULTIPROTOCOL capability value for IPv4 unicast: AFI, reserved, SAFI
MP_IPV4_UNICAST = bytes([0x00, 0x01, 0x00, 0x01])


class FakeNeighbor(dict):
    """Only what Negotiated reads: the AIGP capability, and validate()'s four keys."""

    def __init__(self):
        super().__init__()
        self['capability'] = {'aigp': False}
        self['peer-as'] = None
        self['local-as'] = ASN(65001)
        self['router-id'] = RouterID('10.0.0.1')

    def ip_self(self, afi):
        return None


def wire(entries):
    """The optional parameters of an OPEN, in the shape Capabilities.pack() produces:
    one Capabilities (type 2) parameter per capability TLV.
    """
    parameters = b''
    for code, value in entries:
        encoded = bytes([code, len(value)]) + value
        parameters += bytes([2, len(encoded)]) + encoded
    return bytes([len(parameters)]) + parameters


def multiprotocol(families):
    capability = MultiProtocol()
    capability.extend(families)
    return capability


def our_capabilities(session_id=None, code=Capability.CODE.MULTISESSION):
    """What Capabilities.new() builds for a neighbour with multi-session enabled:
    MULTIPROTOCOL, and a MULTISESSION whose Session Id is [MULTIPROTOCOL].
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = multiprotocol([(AFI.ipv4, SAFI.unicast)])
    if session_id is None:
        session_id = [Capability.CODE.MULTIPROTOCOL]
    capabilities[code] = MultiSession().set(session_id)
    return capabilities


def as_open(capabilities, asn=65002, router_id='10.0.0.2'):
    return Open(Version(4), ASN(asn), HoldTime(180), RouterID(router_id), capabilities)


def negotiate(sent_capabilities, received_capabilities):
    negotiated = Negotiated(FakeNeighbor())
    negotiated.sent(as_open(sent_capabilities, 65001, '10.0.0.1'))
    negotiated.received(as_open(received_capabilities))
    return negotiated


# ==============================================================================
# the Session Id is read off the wire
# ==============================================================================


def test_the_session_id_is_read_from_the_capability_value():
    """Section 4: a flags octet, then one octet per capability code."""
    instance = MultiSession()
    value = bytes([0x00, Capability.CODE.MULTIPROTOCOL, Capability.CODE.FOUR_BYTES_ASN])

    result = MultiSession.unpack_capability(instance, value, Capability.CODE.MULTISESSION)

    assert result is instance
    assert list(result) == [Capability.CODE.MULTIPROTOCOL, Capability.CODE.FOUR_BYTES_ASN]


def test_the_session_id_survives_a_real_open_parameter_buffer():
    value = bytes([0x00, Capability.CODE.MULTIPROTOCOL, Capability.CODE.ROUTE_REFRESH])
    capabilities = Capabilities.unpack(
        wire(
            [
                (Capability.CODE.MULTIPROTOCOL, MP_IPV4_UNICAST),
                (Capability.CODE.MULTISESSION, value),
            ]
        )
    )

    session_id = capabilities[Capability.CODE.MULTISESSION]
    assert isinstance(session_id, MultiSession)
    assert set(session_id) == {Capability.CODE.MULTIPROTOCOL, Capability.CODE.ROUTE_REFRESH}


def test_the_session_id_is_read_under_the_cisco_code_too():
    value = bytes([0x00, Capability.CODE.FOUR_BYTES_ASN])
    capabilities = Capabilities.unpack(wire([(Capability.CODE.MULTISESSION_CISCO, value)]))

    assert set(capabilities[Capability.CODE.MULTISESSION_CISCO]) == {Capability.CODE.FOUR_BYTES_ASN}


@pytest.mark.parametrize('flags', [0x00, 0x80, 0x7F, 0xFF])
def test_the_flags_octet_is_never_a_session_id_code(flags):
    """Section 4: the G bit is deprecated and "Reserved - MUST be set to zero by sender,
    MUST be ignored by receiver".  Whatever the flags hold, they are not a capability code.
    """
    instance = MultiSession()

    MultiSession.unpack_capability(instance, bytes([flags, Capability.CODE.MULTIPROTOCOL]), None)

    assert list(instance) == [Capability.CODE.MULTIPROTOCOL]


@pytest.mark.parametrize('listed', [Capability.CODE.MULTISESSION, Capability.CODE.MULTISESSION_CISCO])
def test_multisession_listed_in_its_own_session_id_is_ignored(listed):
    """Section 4: "The Multisession capability code itself MUST NOT be listed; if listed
    it MUST be ignored upon receipt."
    """
    instance = MultiSession()

    MultiSession.unpack_capability(instance, bytes([0x00, listed, Capability.CODE.MULTIPROTOCOL]), None)

    assert list(instance) == [Capability.CODE.MULTIPROTOCOL]


def test_a_repeated_capability_keeps_the_first_session_id():
    """RFC 5492 section 5 lets a receiver keep one instance of a capability sent twice.
    Appending the second onto the first produced a Session Id which was neither of them.
    """
    capabilities = Capabilities.unpack(
        wire(
            [
                (Capability.CODE.MULTISESSION, bytes([0x00, Capability.CODE.MULTIPROTOCOL])),
                (Capability.CODE.MULTISESSION, bytes([0x00, Capability.CODE.FOUR_BYTES_ASN])),
            ]
        )
    )

    assert list(capabilities[Capability.CODE.MULTISESSION]) == [Capability.CODE.MULTIPROTOCOL]


def test_a_zero_length_value_is_an_empty_session_id_and_not_a_refusal():
    """The flags octet is mandatory, so a zero length value is malformed, but section 4
    makes an empty Session Id equal to {MULTIPROTOCOL}, which is the only one we generate.
    Answering a NOTIFICATION would drop a session which comes up today over an octet we do
    not need.
    """
    capabilities = Capabilities.unpack(
        wire(
            [
                (Capability.CODE.MULTIPROTOCOL, MP_IPV4_UNICAST),
                (Capability.CODE.MULTISESSION, b''),
            ]
        )
    )

    assert list(capabilities[Capability.CODE.MULTISESSION]) == []
    assert negotiate(our_capabilities(), capabilities).validate(FakeNeighbor()) is None


# ==============================================================================
# what the decoded Session Id is for: the Grouping Conflict refusal
# ==============================================================================


@pytest.mark.parametrize(
    'session_id',
    [
        [Capability.CODE.MULTIPROTOCOL, Capability.CODE.FOUR_BYTES_ASN],
        [Capability.CODE.ROUTE_REFRESH],
        [Capability.CODE.GRACEFUL_RESTART, Capability.CODE.ADD_PATH],
    ],
)
def test_a_session_id_which_is_not_ours_is_refused_with_grouping_conflict(session_id):
    """Section 7: a Session Id not matching our own MUST answer 2/8 and drop the session.
    Every one of these was accepted while the Session Id went undecoded.
    """
    value = bytes([0x00, *session_id])
    peer = Capabilities.unpack(
        wire(
            [
                (Capability.CODE.MULTIPROTOCOL, MP_IPV4_UNICAST),
                (Capability.CODE.MULTISESSION, value),
            ]
        )
    )

    error = negotiate(our_capabilities(), peer).validate(FakeNeighbor())

    assert error is not None
    assert error[0] == 2
    assert error[1] == 8


def test_an_empty_session_id_is_the_same_group_as_multiprotocol_alone():
    """Section 4: "Empty Session Id list and Session Id containing 1 (one, Multiprotocol
    Extensions) as the only value are considered equal".
    """
    peer = Capabilities.unpack(
        wire(
            [
                (Capability.CODE.MULTIPROTOCOL, MP_IPV4_UNICAST),
                (Capability.CODE.MULTISESSION, bytes([0x00])),
            ]
        )
    )

    assert negotiate(our_capabilities(), peer).validate(FakeNeighbor()) is None


def test_the_same_session_id_with_a_different_capability_value_is_refused():
    """The Session Id names the capabilities whose VALUES distinguish one group from
    another.  Same Session Id, different MULTIPROTOCOL families, is a conflict.
    """
    peer = Capabilities.unpack(
        wire(
            [
                (Capability.CODE.MULTIPROTOCOL, bytes([0x00, 0x02, 0x00, 0x01])),
                (Capability.CODE.MULTISESSION, bytes([0x00, Capability.CODE.MULTIPROTOCOL])),
            ]
        )
    )

    error = negotiate(our_capabilities(), peer).validate(FakeNeighbor())

    assert error is not None
    assert error[:2] == (2, 8)


def test_a_peer_naming_a_capability_it_never_announced_is_refused_not_a_crash():
    """The peer offers MULTISESSION and no MULTIPROTOCOL at all.  `recv_capa[capa]` raised
    KeyError from peer input, out of the OPEN parser, resetting the session with no
    NOTIFICATION.  It is a Grouping Conflict: the value which should distinguish the group
    is not there to compare.
    """
    peer = Capabilities.unpack(wire([(Capability.CODE.MULTISESSION, bytes([0x00, Capability.CODE.MULTIPROTOCOL]))]))

    error = negotiate(our_capabilities(), peer).validate(FakeNeighbor())

    assert error is not None
    assert error[:2] == (2, 8)


def test_negotiating_under_the_cisco_code_reads_the_cisco_session_id():
    """Both branches indexed the RFC code, so a session negotiated under 0x83 raised
    KeyError.  ExaBGP does not announce 0x83 itself today, so this is reached by building
    the capabilities rather than through the configuration.
    """
    ours = our_capabilities(code=Capability.CODE.MULTISESSION_CISCO)
    peer = Capabilities.unpack(
        wire(
            [
                (Capability.CODE.MULTIPROTOCOL, MP_IPV4_UNICAST),
                (Capability.CODE.MULTISESSION_CISCO, bytes([0x00, Capability.CODE.MULTIPROTOCOL])),
            ]
        )
    )

    assert negotiate(ours, peer).validate(FakeNeighbor()) is None


def test_the_cisco_code_alone_on_our_side_still_requires_grouping():
    """We asked for multi-session, the peer did not answer: 2/9 Grouping Required."""
    peer = Capabilities.unpack(wire([(Capability.CODE.MULTIPROTOCOL, MP_IPV4_UNICAST)]))

    error = negotiate(our_capabilities(code=Capability.CODE.MULTISESSION_CISCO), peer).validate(FakeNeighbor())

    assert error is not None
    assert error[:2] == (2, 9)


# ==============================================================================
# exabgp against exabgp: the encoder puts the flags octet and each Session Id code
# into separate one octet capabilities, which must keep negotiating
# ==============================================================================


def test_our_own_open_still_negotiates_against_itself():
    """extract() emits [0x00] and then one TLV per Session Id code, so our own OPEN arrives
    as several MULTISESSION capabilities whose bytes past the first one are flags.  Read as
    the draft describes, that is an empty Session Id, which section 4 makes equal to the
    {MULTIPROTOCOL} we compare against.  A decoder which concatenated the TLVs, or which
    treated the flags octet as a code, would refuse every ExaBGP peering with 2/8.
    """
    ours = our_capabilities()
    on_the_wire = ours.pack()

    assert on_the_wire.hex() == '12020601040001000102034401000203440101'

    peer = Capabilities.unpack(on_the_wire)
    assert list(peer[Capability.CODE.MULTISESSION]) == []
    assert negotiate(ours, peer).validate(FakeNeighbor()) is None


# ==============================================================================
# the published JSON keeps its shape
# ==============================================================================


def test_the_json_members_are_unchanged_by_decoding_the_session_id():
    instance = MultiSession()
    MultiSession.unpack_capability(instance, bytes([0x00, Capability.CODE.MULTIPROTOCOL]), None)
    instance.ID = Capability.CODE.MULTISESSION

    decoded = json.loads(instance.json())

    assert sorted(decoded.keys()) == ['capabilities', 'name', 'variant']
    assert decoded['name'] == 'multisession'
    assert decoded['variant'] == 'RFC'
    assert decoded['capabilities'] == ['multiprotocol']
    assert all(isinstance(entry, str) for entry in decoded['capabilities'])
