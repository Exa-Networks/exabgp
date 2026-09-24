"""RFC 4271 sections 4.2 and 6.2: what an OPEN has to say before a session may start.

The version is checked while the OPEN is decoded, so those tests call the decoder.  The
peer AS, the BGP Identifier and the Hold Time are checked after both OPENs have been
exchanged, in `Negotiated.validate`, which returns the (code, subcode, text) the reactor
raises; those tests build two real OPEN messages and call it.  The Optional Parameters
are parsed by `Capabilities.unpack`, which takes the block including its leading length
octet.

The finding here is `test_an_unrecognised_optional_parameter_is_unsupported`: we answer
2/0 Unspecific, which RFC 4271 6.2 reserves for the *next* case down, a parameter we do
recognise and which is malformed.  A peer cannot tell the two apart.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message import Message, Notify, Open
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notification
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability import ASN4, Capability
from exabgp.bgp.message.open.capability.capabilities import Parameter
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB

OPEN_MESSAGE_ERROR = 2
UNSUPPORTED_VERSION_NUMBER = 1
BAD_PEER_AS = 2
BAD_BGP_IDENTIFIER = 3
UNSUPPORTED_OPTIONAL_PARAMETER = 4
UNACCEPTABLE_HOLD_TIME = 6
UNSPECIFIC = 0

AS_TRANS = 23456
ROUTE_REFRESH = 2


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def open_body(
    version: int = 4,
    asn: int = 65002,
    hold_time: int = 180,
    identifier: bytes = bytes([192, 0, 2, 2]),
) -> bytes:
    """The ten fixed octets of an OPEN, with no Optional Parameters."""
    return bytes([version]) + pack('!H', asn) + pack('!H', hold_time) + identifier + bytes([0])


def negotiate(
    local_as: int = 65001,
    configured_peer_as: int = 65002,
    open_asn: int = 65002,
    our_hold_time: int = 180,
    peer_hold_time: int = 180,
    our_identifier: str = '192.0.2.1',
    peer_identifier: str = '192.0.2.2',
    asn4: int = 0,
) -> tuple[Negotiated, Neighbor]:
    """Two OPEN messages exchanged, ready for validate() to pass judgement on.

    `asn4` non-zero puts the four octet ASN capability on both sides carrying that value,
    which is how a peer whose OPEN says AS_TRANS names its real ASN.
    """
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(local_as)
    neighbor.session.peer_as = ASN(configured_peer_as)
    neighbor.session.router_id = RouterID(our_identifier)

    ours = Capabilities()
    theirs = Capabilities()
    if asn4:
        ours[Capability.CODE.FOUR_BYTES_ASN] = ASN4(local_as)
        theirs[Capability.CODE.FOUR_BYTES_ASN] = ASN4(asn4)

    negotiated = Negotiated.make_negotiated(neighbor, Direction.IN)
    negotiated.sent(Open.make_open(Version(4), ASN(local_as), HoldTime(our_hold_time), RouterID(our_identifier), ours))
    negotiated.received(
        Open.make_open(Version(4), ASN(open_asn), HoldTime(peer_hold_time), RouterID(peer_identifier), theirs)
    )
    return negotiated, neighbor


def judgement(
    local_as: int = 65001,
    configured_peer_as: int = 65002,
    open_asn: int = 65002,
    peer_hold_time: int = 180,
    peer_identifier: str = '192.0.2.2',
    asn4: int = 0,
) -> tuple[int, int, str] | None:
    """What the reactor would raise for this pair of OPENs, or None if it would not."""
    negotiated, neighbor = negotiate(
        local_as=local_as,
        configured_peer_as=configured_peer_as,
        open_asn=open_asn,
        peer_hold_time=peer_hold_time,
        peer_identifier=peer_identifier,
        asn4=asn4,
    )
    return negotiated.validate(neighbor)


def parameter(kind: int, value: bytes) -> bytes:
    return bytes([kind, len(value)]) + value


def capability(code: int, value: bytes = b'') -> bytes:
    return bytes([code, len(value)]) + value


def optional_parameters(*parameters: bytes) -> bytes:
    """The Optional Parameters field, preceded by its one octet length, as Open passes it."""
    body = b''.join(parameters)
    return bytes([len(body)]) + body


# ------------------------------------------------------------------------- 6.2 the version


@pytest.mark.parametrize('version', [0, 1, 3, 5, 255], ids=lambda value: f'version {value}')
@pytest.mark.rfc('rfc4271#6.2-unsupported-version-number')
def test_a_version_we_do_not_support_is_refused_as_such(version: int) -> None:
    with pytest.raises(Notify) as caught:
        Message.unpack(int(Message.CODE.OPEN), open_body(version=version), Negotiated.UNSET)

    assert caught.value.code == OPEN_MESSAGE_ERROR
    assert caught.value.subcode == UNSUPPORTED_VERSION_NUMBER


@pytest.mark.rfc('rfc4271#6.2-unsupported-version-number', polarity='negative')
def test_version_four_is_accepted() -> None:
    """Without this a decoder which refused every OPEN would pass the test above."""
    message = Message.unpack(int(Message.CODE.OPEN), open_body(), Negotiated.UNSET)

    assert isinstance(message, Open)
    assert message.version == 4


# -------------------------------------------------------------------------- 6.2 the peer AS


@pytest.mark.parametrize('open_asn', [1, 65001, 65003, 65535], ids=lambda value: f'as {value}')
@pytest.mark.rfc('rfc4271#6.2-bad-peer-as')
def test_an_asn_other_than_the_configured_one_is_a_bad_peer_as(open_asn: int) -> None:
    error = judgement(open_asn=open_asn)

    assert error is not None, f'an OPEN from AS{open_asn} was accepted on a session configured for AS65002'
    assert (error[0], error[1]) == (OPEN_MESSAGE_ERROR, BAD_PEER_AS)


@pytest.mark.rfc('rfc4271#6.2-bad-peer-as', polarity='negative')
def test_the_configured_asn_is_accepted() -> None:
    assert judgement(open_asn=65002) is None


@pytest.mark.rfc('rfc4271#6.2-bad-peer-as', polarity='negative')
def test_a_four_octet_asn_behind_as_trans_is_matched_on_its_real_value() -> None:
    """The OPEN can only carry two octets, so the comparison must use the capability.

    Refusing this peer would be refusing every speaker with an ASN above 65535.
    """
    assert judgement(configured_peer_as=65538, open_asn=AS_TRANS, asn4=65538) is None


# ------------------------------------------------------------------------ 6.2 the hold time


@pytest.mark.parametrize('hold_time', [1, 2], ids=['one second', 'two seconds'])
@pytest.mark.rfc('rfc4271#6.2-reject-hold-time-of-one-or-two')
def test_a_hold_time_of_one_or_two_seconds_is_rejected(hold_time: int) -> None:
    error = judgement(peer_hold_time=hold_time)

    assert error is not None, f'a hold time of {hold_time} was accepted'


@pytest.mark.parametrize('hold_time', [0, 3, 4, 90, 180, 65535], ids=lambda value: f'{value} seconds')
@pytest.mark.rfc('rfc4271#6.2-reject-hold-time-of-one-or-two', polarity='negative')
def test_every_other_hold_time_is_accepted(hold_time: int) -> None:
    """Zero either side of the boundary: three is legal and zero disables the timer."""
    assert judgement(peer_hold_time=hold_time) is None


@pytest.mark.parametrize('hold_time', [1, 2], ids=['one second', 'two seconds'])
@pytest.mark.rfc('rfc4271#6.2-unacceptable-hold-time')
def test_an_unacceptable_hold_time_is_named_as_one(hold_time: int) -> None:
    error = judgement(peer_hold_time=hold_time)

    assert error is not None
    assert (error[0], error[1]) == (OPEN_MESSAGE_ERROR, UNACCEPTABLE_HOLD_TIME)


@pytest.mark.rfc('rfc4271#6.2-unacceptable-hold-time', polarity='negative')
def test_an_open_error_which_is_not_about_the_hold_time_does_not_claim_to_be() -> None:
    """A subcode which is handed out for everything names nothing."""
    error = judgement(open_asn=65003)

    assert error is not None
    assert error[1] != UNACCEPTABLE_HOLD_TIME


# -------------------------------------------------------------------- 6.2 the BGP identifier


@pytest.mark.rfc('rfc4271#6.2-bad-bgp-identifier')
def test_a_zero_bgp_identifier_is_refused() -> None:
    """RFC 6286 2.2 replaced "a valid unicast IP host address" with "MUST be non-zero"."""
    error = judgement(peer_identifier='0.0.0.0')

    assert error is not None, '0.0.0.0 was accepted as a BGP Identifier'
    assert (error[0], error[1]) == (OPEN_MESSAGE_ERROR, BAD_BGP_IDENTIFIER)


@pytest.mark.rfc('rfc4271#6.2-bad-bgp-identifier')
def test_our_own_identifier_on_an_ibgp_session_is_refused() -> None:
    """A BGP Identifier has to be unique within an AS, so the collision is an error."""
    error = judgement(local_as=65001, configured_peer_as=65001, open_asn=65001, peer_identifier='192.0.2.1')

    assert error is not None, 'the same router-id on both sides of an IBGP session was accepted'
    assert (error[0], error[1]) == (OPEN_MESSAGE_ERROR, BAD_BGP_IDENTIFIER)


@pytest.mark.parametrize('identifier', ['192.0.2.2', '10.0.0.1', '255.255.255.254'], ids=lambda value: value)
@pytest.mark.rfc('rfc4271#6.2-bad-bgp-identifier', polarity='negative')
def test_a_non_zero_identifier_is_accepted(identifier: str) -> None:
    assert judgement(peer_identifier=identifier) is None


# ------------------------------------------------------------- 6.2 the optional parameters


@pytest.mark.parametrize('kind', [0, 3, 99, 255], ids=lambda value: f'parameter type {value}')
@pytest.mark.rfc('rfc4271#6.2-unsupported-optional-parameters')
@pytest.mark.xfail(
    strict=True,
    reason='Capabilities.unpack ends with raise Notify(2, 0, "Unknow OPEN parameter ...") for '
    'any parameter type other than 1 and 2, so an unrecognised Optional Parameter is answered '
    'Unspecific, which RFC 4271 6.2 reserves for a recognised parameter which is malformed',
)
def test_an_unrecognised_optional_parameter_is_unsupported(kind: int) -> None:
    with pytest.raises(Notify) as caught:
        Capabilities.unpack(optional_parameters(parameter(kind, b'')))

    assert caught.value.code == OPEN_MESSAGE_ERROR
    assert caught.value.subcode == UNSUPPORTED_OPTIONAL_PARAMETER


@pytest.mark.rfc('rfc4271#6.2-unsupported-optional-parameters', polarity='negative')
def test_a_recognised_optional_parameter_is_not_refused() -> None:
    """Parameter type 2 is the Capabilities parameter, and it has to get through."""
    capabilities = Capabilities.unpack(
        optional_parameters(parameter(Parameter.CAPABILITIES, capability(ROUTE_REFRESH)))
    )

    assert capabilities.announced(ROUTE_REFRESH), 'a well formed Capabilities parameter was dropped'


@pytest.mark.parametrize(
    'block',
    [
        bytes([3]) + bytes([Parameter.CAPABILITIES, 5, 0]),
        bytes([4]) + bytes([Parameter.CAPABILITIES, 2, ROUTE_REFRESH, 9]),
        bytes([2]) + bytes([Parameter.CAPABILITIES]),
    ],
    ids=['parameter length overruns', 'capability length overruns', 'parameter header truncated'],
)
@pytest.mark.rfc('rfc4271#6.2-malformed-parameter-is-unspecific')
def test_a_recognised_but_malformed_parameter_is_unspecific(block: bytes) -> None:
    with pytest.raises(Notify) as caught:
        Capabilities.unpack(block)

    assert caught.value.code == OPEN_MESSAGE_ERROR
    assert caught.value.subcode == UNSPECIFIC


@pytest.mark.rfc('rfc4271#6.2-malformed-parameter-is-unspecific', polarity='negative')
def test_a_well_formed_parameter_is_not_called_malformed() -> None:
    """Without this, a parser which refused every parameter would pass the test above."""
    assert Capabilities.unpack(optional_parameters()) == {}


# ------------------------------------------------------------------- 4.2 the hold time we send


def neighbours(*hold_times: str) -> Configuration:
    """One configuration, one neighbour per hold time given."""
    blocks = [
        f"""neighbor 192.0.2.{index + 10} {{
            router-id 192.0.2.1;
            local-address 192.0.2.1;
            local-as 65001;
            peer-as 65002;
            hold-time {hold_time};
            family {{ ipv4 unicast; }}
        }}"""
        for index, hold_time in enumerate(hold_times)
    ]
    return Configuration(['\n'.join(blocks)], text=True)


@pytest.mark.parametrize('hold_time', ['0', '3', '4', '90', '180'], ids=lambda value: f'{value} seconds')
@pytest.mark.rfc('rfc4271#4.2-holdtime-zero-or-at-least-three')
def test_a_hold_time_the_rfc_allows_is_accepted(hold_time: str) -> None:
    configuration = neighbours(hold_time)

    assert configuration.reload(), str(configuration.error)
    (neighbor,) = configuration.neighbors.values()
    assert int(neighbor.hold_time) == int(hold_time)


@pytest.mark.parametrize('hold_time', ['1', '2'], ids=lambda value: f'{value} seconds')
@pytest.mark.rfc('rfc4271#4.2-holdtime-zero-or-at-least-three', polarity='negative')
def test_a_hold_time_the_rfc_forbids_is_refused_before_it_can_be_sent(hold_time: str) -> None:
    """Refusing at configuration time is the only place it can be refused.

    Once the OPEN is built the value is already in it, and the peer, not us, would be the
    one enforcing RFC 4271 4.2.
    """
    configuration = neighbours(hold_time)

    assert not configuration.reload(), f'hold-time {hold_time} was accepted'
    assert 'hold-time' in str(configuration.error)


@pytest.mark.rfc('rfc4271#10-holdtimer-configurable-per-peer')
def test_two_neighbours_keep_their_own_hold_times() -> None:
    configuration = neighbours('90', '180')

    assert configuration.reload(), str(configuration.error)
    assert sorted(int(neighbor.hold_time) for neighbor in configuration.neighbors.values()) == [90, 180]


# ---------------------------------------------------------- 4.2 the hold time we negotiate


@pytest.mark.parametrize(
    'ours,theirs,expected',
    [(90, 30, 30), (30, 90, 30), (180, 180, 180), (90, 0, 0), (0, 90, 0)],
    ids=['ours larger', 'theirs larger', 'equal', 'they disable', 'we disable'],
)
@pytest.mark.rfc('rfc4271#4.2-holdtimer-is-the-smaller-of-the-two')
def test_the_hold_timer_is_the_smaller_of_the_two(ours: int, theirs: int, expected: int) -> None:
    negotiated, _ = negotiate(our_hold_time=ours, peer_hold_time=theirs)

    assert int(negotiated.holdtime) == expected


@pytest.mark.rfc('rfc4271#4.2-holdtimer-is-the-smaller-of-the-two', polarity='negative')
def test_the_hold_timer_is_neither_side_taken_on_its_own() -> None:
    """A speaker which always kept its own value would pass "ours larger" and fail here."""
    negotiated, _ = negotiate(our_hold_time=90, peer_hold_time=30)

    assert int(negotiated.holdtime) != 90, 'we kept our configured hold time and ignored the peer'

    negotiated, _ = negotiate(our_hold_time=30, peer_hold_time=90)

    assert int(negotiated.holdtime) != 90, 'we took the peer hold time and ignored our own'


def test_a_rejected_open_never_reaches_the_timer() -> None:
    """Unmarked: the ordering which makes the two hold time requirements consistent.

    validate() refuses a hold time of one or two seconds, and the negotiated value is
    computed before that.  So min(180, 1) == 1 exists for a moment; nothing uses it,
    because the session is closed.
    """
    negotiated, neighbor = negotiate(peer_hold_time=1)

    assert int(negotiated.holdtime) == 1
    assert negotiated.validate(neighbor) is not None


def test_validate_reports_open_errors_and_nothing_else() -> None:
    """Unmarked: every subcode validate() hands out belongs to the OPEN error code."""
    errors = [
        judgement(open_asn=65003),
        judgement(peer_identifier='0.0.0.0'),
        judgement(peer_hold_time=1),
    ]
    for error in errors:
        assert error is not None
        assert error[0] == OPEN_MESSAGE_ERROR
        rendered = str(Notification(bytes([error[0], error[1]])))
        assert 'unknow reason' not in rendered, f'{error[0]}/{error[1]} is a subcode with no name: {rendered}'
