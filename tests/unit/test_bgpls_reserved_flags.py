#!/usr/bin/env python3
# encoding: utf-8

"""A reserved flag bit is ignored, not grounds for discarding the attribute

RFC 8667 2.2.1, and the same wording throughout the IGP specifications these
TLVs are carried from: "Other bits: MUST be zero when originated and ignored
when received."

unpack_flags did the opposite. It built the set of octets whose reserved
positions were zero and refused everything else:

    raise Notify(3, 5, 'Invalid SR flags mask')

LinkState is in DISCARD, so a peer setting a bit we are required to ignore lost
its ENTIRE BGP-LS attribute: the router-ids, the metrics and the SIDs, over a bit
with no meaning assigned yet. Thirteen registered TLVs behaved this way.

That is precisely the forward compatibility failure reserving bits exists to
prevent. On the day a later RFC assigns one of those positions, every peer
running this code discards the attribute rather than ignoring what it does not
understand.

Nothing tested any of it. Not one test in the tree referenced unpack_flags or
the refusal, which is why removing it broke nothing: the suite was green because
the behaviour was absent from it, not because it was right.

Found by the session working main, who reached it from the audit question this
series has been using: a gate tells you what is refused; ask separately what the
code does with the bytes the gate approved, and what it does with the ones it
did not.
"""

from unittest.mock import Mock

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState


@pytest.fixture(autouse=True)
def mocked_logger():
    from exabgp.logger.option import option

    saved = option.logger
    option.logger = Mock()
    yield
    option.logger = saved


def flag_classes():
    """Every registered TLV which defines a flag layout with reserved positions"""
    found = []
    for code, klass in sorted(LinkState.registered_lsids.items(), key=lambda kv: int(kv[0])):
        flags = getattr(klass, 'FLAGS', None)
        if flags and 'RSV' in flags:
            found.append(pytest.param(int(code), klass, id=f'{int(code)}-{klass.__name__}'))
    return found


FLAG_CLASSES = flag_classes()

# A ratchet. If the registry stops yielding these the sweep below asserts nothing,
# and a sweep over an empty list is green.
EXPECTED_FLAG_CLASSES = 13


def reserved_bit(klass):
    """An octet with only the lowest reserved position set"""
    return bytes([1 << (klass.FLAGS.count('RSV') - 1)])


class TestTheSweepCoversWhatItClaims:
    def test_every_flag_class_is_found(self) -> None:
        assert len(FLAG_CLASSES) == EXPECTED_FLAG_CLASSES, [p.id for p in FLAG_CLASSES]

    def test_each_one_really_has_a_reserved_position(self) -> None:
        for param in FLAG_CLASSES:
            _code, klass = param.values
            assert 'RSV' in klass.FLAGS


class TestAReservedBitIsAccepted:
    @pytest.mark.parametrize('code,klass', [p.values for p in FLAG_CLASSES], ids=[p.id for p in FLAG_CLASSES])
    def test_it_does_not_refuse(self, code, klass) -> None:
        # the whole BGP-LS attribute used to go with it
        assert klass.unpack_flags(reserved_bit(klass)) is not None

    @pytest.mark.parametrize('code,klass', [p.values for p in FLAG_CLASSES], ids=[p.id for p in FLAG_CLASSES])
    def test_and_the_reserved_position_reports_unset(self, code, klass) -> None:
        # ignoring a bit means behaving as though it were not set, and it keeps
        # the rendering identical for every input accepted before this change
        assert klass.unpack_flags(reserved_bit(klass))['RSV'] == 0

    @pytest.mark.parametrize('code,klass', [p.values for p in FLAG_CLASSES], ids=[p.id for p in FLAG_CLASSES])
    def test_every_reserved_position_not_just_the_lowest(self, code, klass) -> None:
        count = klass.FLAGS.count('RSV')
        for position in range(count):
            assert klass.unpack_flags(bytes([1 << position]))['RSV'] == 0


class TestTheDefinedFlagsStillDecode:
    """A gate which accepted everything and reported nothing would pass the above"""

    def test_the_top_bit_of_node_flags(self) -> None:
        node_flags = LinkState.registered_lsids[1024]
        decoded = node_flags.unpack_flags(bytes([0x80]))
        assert decoded['O'] == 1
        assert all(decoded[name] == 0 for name in ('T', 'E', 'B', 'R', 'V'))

    def test_an_empty_flag_octet(self) -> None:
        node_flags = LinkState.registered_lsids[1024]
        assert all(value == 0 for value in node_flags.unpack_flags(bytes([0x00])).values())

    def test_a_defined_bit_beside_a_reserved_one(self) -> None:
        # 0x81 is the defined top bit plus a reserved bottom bit: the defined one
        # must survive the reserved one being ignored
        node_flags = LinkState.registered_lsids[1024]
        decoded = node_flags.unpack_flags(bytes([0x81]))
        assert decoded['O'] == 1
        assert decoded['RSV'] == 0

    @pytest.mark.parametrize('code,klass', [p.values for p in FLAG_CLASSES], ids=[p.id for p in FLAG_CLASSES])
    def test_every_class_reports_all_its_named_flags(self, code, klass) -> None:
        decoded = klass.unpack_flags(bytes([0x00]))
        for name in klass.FLAGS:
            assert name in decoded


class TestAnEmptyFlagFieldIsStillRefused:
    """The widening must not swallow the length check underneath it"""

    @pytest.mark.parametrize('code,klass', [p.values for p in FLAG_CLASSES], ids=[p.id for p in FLAG_CLASSES])
    def test_no_octet_at_all(self, code, klass) -> None:
        with pytest.raises(Notify):
            klass.unpack_flags(b'')
