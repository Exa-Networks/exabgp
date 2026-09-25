"""RFC 4760 makes MP_REACH_NLRI and MP_UNREACH_NLRI optional non-transitive.

With the transitive bit set the attribute misses the registry lookup in
`Attributes.parse`, and because neither code is in `Attributes.TREAT_AS_WITHDRAW` nor in
`Attributes.DISCARD` it used to fall through to the branch whose own comment reads
"unspecified (should not happen)" and continue to the next attribute.  The routes
vanished: no withdrawal, no NOTIFICATION, one debug line.

Which answer the RFC wants is the interesting part, because it is not the one the rest of
this branch reaches for.  RFC 7606 3(c) makes a flags conflict treat-as-withdraw, but
treat-as-withdraw is not available here: the NLRI are *inside* the attribute whose flags
stopped us recognising it, so there is nothing left to withdraw.  That is exactly why the
silent drop lost routes rather than releasing them.  RFC 7606 5.3 lists "the attribute
flags ... are inconsistent with those specified in [RFC4760]" as one of the four ways an
MP attribute is incorrect, and 3(j) says that when the MP attributes cannot be
successfully parsed, the session reset approach MUST be followed.

So: a Notify.  Subcode 0 because that is the subcode mprnlri.py and mpurnlri.py already
raise for an MP attribute they cannot read, and an MP flags fault should not be reported
differently depending on which line noticed it.
"""

from __future__ import annotations

import importlib.util
import pathlib
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Open
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability, Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.protocol.family import AFI, SAFI

OPTIONAL = 0x80
OPTIONAL_TRANSITIVE = 0xC0

MP_CODES = [Attribute.CODE.MP_REACH_NLRI, Attribute.CODE.MP_UNREACH_NLRI]
MP_IDS = ['mp-reach-nlri', 'mp-unreach-nlri']


@pytest.fixture(autouse=True)
def _logger() -> Any:
    """The parser logs every attribute it sees, and the logger is not set up under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


@pytest.fixture(autouse=True)
def _no_parse_cache() -> Any:
    """Attributes memoises the last parse on the class, so one test would feed the next."""
    Attributes.cached = None
    Attributes.previous = ''
    yield
    Attributes.cached = None
    Attributes.previous = ''


@pytest.fixture(scope='module')
def session() -> Any:
    """A negotiated session, so a well formed MP attribute really does decode."""
    spec = importlib.util.spec_from_file_location('decode_fixtures', pathlib.Path(__file__).parent / 'test_decode.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    neighbor = module.FakeNeighbor()
    capabilities = Capabilities().new(neighbor, False)
    capabilities[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    negotiated = Negotiated(neighbor)
    negotiated.sent(Open(Version(4), ASN(neighbor['local-as']), HoldTime(180), RouterID('10.0.0.1'), capabilities))
    negotiated.received(Open(Version(4), ASN(neighbor['peer-as']), HoldTime(180), RouterID('10.0.0.2'), capabilities))
    return negotiated


def mp_reach_value() -> bytes:
    """One IPv4 unicast prefix, announced through MP_REACH_NLRI."""
    return bytes([0, AFI.ipv4, SAFI.unicast, 4, 10, 0, 0, 1, 0, 24, 10, 0, 0])


def mp_unreach_value() -> bytes:
    """One IPv4 unicast prefix, withdrawn through MP_UNREACH_NLRI."""
    return bytes([0, AFI.ipv4, SAFI.unicast, 24, 10, 0, 0])


VALUE = {
    Attribute.CODE.MP_REACH_NLRI: mp_reach_value,
    Attribute.CODE.MP_UNREACH_NLRI: mp_unreach_value,
}


def attribute(flag: int, code: int, value: bytes) -> bytes:
    return bytes([flag, code, len(value)]) + value


@pytest.mark.parametrize('code', MP_CODES, ids=MP_IDS)
def test_a_transitive_mp_attribute_resets_the_session(code: int, session: Any) -> None:
    """Not a silent drop: the NLRI are inside the attribute, so they cannot be withdrawn."""
    payload = attribute(OPTIONAL_TRANSITIVE, code, VALUE[code]())

    with pytest.raises(Notify) as raised:
        Attributes.unpack(payload, Direction.IN, session)

    assert raised.value.code == 3, 'RFC 7606 3(j) asks for a session reset over an UPDATE error'


@pytest.mark.parametrize('code', MP_CODES, ids=MP_IDS)
def test_the_same_bytes_with_the_right_flag_still_decode(code: int, session: Any) -> None:
    """Otherwise the assertion above would be satisfied by refusing every MP attribute."""
    payload = attribute(OPTIONAL, code, VALUE[code]())

    parsed = Attributes.unpack(payload, Direction.IN, session)

    assert code in parsed, 'a well formed MP attribute was refused'
    assert parsed[code].nlris, 'the MP attribute decoded no NLRI'


def test_a_non_mp_attribute_with_the_wrong_flag_keeps_its_own_answer(session: Any) -> None:
    """The reset is for the MP attributes only, not for the whole wrong-flag branch.

    MED is optional non-transitive too, and RFC 7606 7.4 gives it treat-as-withdraw.  That
    answer works for MED because its route is in the UPDATE where we can still reach it,
    which is the whole reason the MP attributes need a different one.
    """
    payload = attribute(OPTIONAL_TRANSITIVE, Attribute.CODE.MED, bytes(4))

    parsed = Attributes.unpack(payload, Direction.IN, session)

    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in parsed
    assert Attribute.CODE.MED not in parsed
