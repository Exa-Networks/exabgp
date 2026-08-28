"""The attribute cache was one slot for the whole process, keyed only on the wire bytes.

AttributeCollection.unpack kept the last parsed collection in ClassVars:

    cached: ClassVar[AttributeCollection | None] = None
    previous: ClassVar[Buffer] = b''

One slot, shared by every BGP session in the process, with the raw attribute bytes as the
only key.  But several attributes decode differently depending on what the session
negotiated, and `negotiated` was not part of that key.  AIGP is the clearest: its decoder
returns the attribute when the session negotiated AIGP and a Discard when it did not.

So two peers sending byte-identical attributes -- which is the common case, not a contrived
one, since ORIGIN, AS_PATH, NEXT_HOP and LOCAL_PREF repeat constantly -- had the second
session handed the first session's parsed object, carrying the first session's
interpretation.  A peer which never negotiated AIGP received an AIGP attribute.

The slot was also never cleared when a session ended, so a collection outlived the peer it
was parsed for.

Both are fixed by keeping the cache on the Negotiated instance: Protocol builds one per
session (protocol.py:50) and a fresh Protocol is built per session (peer.py:416, :448), so
the cache is per session by construction and is discarded with it.

The tests below build a real Negotiated rather than a Mock on purpose.  A Mock accepts any
attribute and returns a Mock for any read, so a cache stored on one would appear to work
whatever the implementation did.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

from exabgp.bgp.message import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection

AIGP = int(Attribute.CODE.AIGP)
DISCARD = int(Attribute.CODE.INTERNAL_DISCARD)
ORIGIN = int(Attribute.CODE.ORIGIN)

OPTIONAL = 0x80
WELL_KNOWN_TRANSITIVE = 0x40

AIGP_TLV_TYPE = 1
AIGP_TLV_LENGTH_BYTES = 11
AIGP_ACCUMULATED_METRIC = 42

# An AIGP attribute: one TLV of type 1, eleven bytes, carrying the metric.
AIGP_ATTRIBUTE = (
    bytes([OPTIONAL, AIGP, AIGP_TLV_LENGTH_BYTES])
    + bytes([AIGP_TLV_TYPE])
    + pack('!H', AIGP_TLV_LENGTH_BYTES)
    + pack('!Q', AIGP_ACCUMULATED_METRIC)
)
ORIGIN_IGP = bytes([WELL_KNOWN_TRANSITIVE, ORIGIN, 1, 0])


def session(aigp_enabled: bool) -> Negotiated:
    """A real Negotiated, as one session's worth of negotiated state."""
    neighbor = Mock()
    neighbor.capability.aigp.is_enabled = Mock(return_value=aigp_enabled)
    negotiated = Negotiated(neighbor, Direction.IN)
    negotiated.asn4 = False
    negotiated.direction = Action.ANNOUNCE
    return negotiated


def decoded(data: bytes, negotiated: Negotiated) -> Any:
    return AttributeCollection.unpack(data, negotiated)


def test_a_second_session_does_not_inherit_the_first_sessions_decode() -> None:
    """The bug, stated as the wrong route it produces.

    The peer which did not negotiate AIGP must see the attribute discarded.  Before the
    fix it was handed the other peer's AIGP, so it carried a metric no peer had sent it.
    """
    with_aigp = decoded(AIGP_ATTRIBUTE, session(aigp_enabled=True))
    without_aigp = decoded(AIGP_ATTRIBUTE, session(aigp_enabled=False))

    assert AIGP in with_aigp, 'the session which negotiated AIGP lost it'
    assert AIGP not in without_aigp, 'a session which never negotiated AIGP was handed one'
    assert DISCARD in without_aigp, 'the attribute should have been discarded for that session'


def test_the_order_the_sessions_arrive_in_does_not_matter() -> None:
    """The same claim with the two sessions swapped.

    A cache which is merely primed by the first caller would pass the test above by
    accident whenever the first session happened to be the one being asserted about.
    """
    without_aigp = decoded(AIGP_ATTRIBUTE, session(aigp_enabled=False))
    with_aigp = decoded(AIGP_ATTRIBUTE, session(aigp_enabled=True))

    assert DISCARD in without_aigp
    assert AIGP in with_aigp, 'the second session inherited the first sessions discard'


def test_two_sessions_do_not_share_one_parsed_object() -> None:
    """Identity, not just equality: a shared object is a shared mutation.

    The collections are handed to the RIB and the API.  Two peers holding one object means
    anything done to it on behalf of one peer happens to the other.
    """
    first = decoded(ORIGIN_IGP, session(aigp_enabled=True))
    second = decoded(ORIGIN_IGP, session(aigp_enabled=True))

    assert first is not second, 'two sessions were handed the same AttributeCollection'


# --- the negative space: the cache still has to be a cache -----------------------------


def test_the_cache_still_serves_a_repeat_within_one_session() -> None:
    """Deleting the cache would satisfy every assertion above.

    A table dump sends many UPDATEs carrying identical attributes, which is what the cache
    is for.  This pins that the fix scoped the cache rather than removed it.
    """
    negotiated = session(aigp_enabled=True)

    first = decoded(ORIGIN_IGP, negotiated)
    second = decoded(ORIGIN_IGP, negotiated)

    assert first is second, 'a repeated identical attribute set was parsed twice in one session'


def test_different_attributes_in_one_session_are_not_confused() -> None:
    """The key is still the bytes, within the session."""
    negotiated = session(aigp_enabled=True)

    origin_only = decoded(ORIGIN_IGP, negotiated)
    aigp_only = decoded(AIGP_ATTRIBUTE, negotiated)

    assert ORIGIN in origin_only and AIGP not in origin_only
    assert AIGP in aigp_only and ORIGIN not in aigp_only


def test_a_new_session_starts_with_no_cache() -> None:
    """The cache dies with the session it belongs to, rather than outliving the peer."""
    first = session(aigp_enabled=True)
    decoded(ORIGIN_IGP, first)

    second = session(aigp_enabled=True)
    fresh = decoded(ORIGIN_IGP, second)

    assert ORIGIN in fresh
    assert fresh is not decoded(ORIGIN_IGP, first), 'the new session was served the old sessions object'


# --- the UNSET sentinel -----------------------------------------------------------------
#
# Negotiated.UNSET is one process-wide object, built by _create_unset() mirroring the
# session fields by hand.  It must keep decoding attributes when handed to unpack, and it
# must never hold a cache: a cache on the singleton is the shared-slot bug all over again.


def test_the_unset_sentinel_can_still_decode_attributes() -> None:
    """The cache fields were added to __init__ but not to _create_unset()."""
    collection = decoded(ORIGIN_IGP, Negotiated.UNSET)

    assert ORIGIN in collection, 'the UNSET sentinel could not decode a plain ORIGIN'


def test_the_unset_sentinel_never_caches() -> None:
    """Every caller of the sentinel must get its own collection, cache untouched."""
    first = decoded(ORIGIN_IGP, Negotiated.UNSET)
    second = decoded(ORIGIN_IGP, Negotiated.UNSET)

    assert Negotiated.UNSET.attribute_cache is None, 'the process-wide sentinel kept a session cache'
    assert Negotiated.UNSET.attribute_cache_packed == b''
    assert first is not second, 'two callers of the sentinel shared one collection'


def test_the_sentinel_mirrors_every_session_field() -> None:
    """Drift guard: a field added to __init__ must be added to _create_unset() too.

    neighbor and direction are deliberately absent from the sentinel: it exists for the
    callers which have neither.
    """
    real = session(aigp_enabled=True)

    missing = set(vars(real)) - set(vars(Negotiated.UNSET)) - {'neighbor', 'direction'}

    assert not missing, f'_create_unset() does not mirror __init__: {sorted(missing)}'


# --- the copy made before a treat-as-withdraw marker is added ---------------------------
#
# UpdateCollection.unpack_message may be holding this session's cached collection when it
# finds an announce missing a mandatory attribute.  The marker it adds describes that one
# UPDATE, not what the attribute bytes mean, so it goes onto a copy.  The copy has to be a
# real one: a new mapping over the same attributes, with the derived caches empty because
# it is about to stop matching them.


def test_copy_holds_the_same_attributes_in_a_separate_mapping() -> None:
    from exabgp.bgp.message.update.attribute.attribute import TreatAsWithdraw

    original = decoded(ORIGIN_IGP, session(aigp_enabled=False))
    duplicate = original.copy()

    assert list(duplicate) == list(original)
    assert duplicate[ORIGIN] is original[ORIGIN], 'immutable attributes are shared, not rebuilt'

    duplicate.add(TreatAsWithdraw())

    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in duplicate
    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in original, 'the copy shared the original mapping'


def test_copy_starts_with_empty_derived_caches() -> None:
    """str()/json()/index() are memoised on the collection they were rendered from."""
    original = decoded(ORIGIN_IGP, session(aigp_enabled=False))
    _ = str(original)
    _ = original.index()

    duplicate = original.copy()

    assert duplicate._str == ''
    assert duplicate._json == ''
    assert duplicate._idx == b''
