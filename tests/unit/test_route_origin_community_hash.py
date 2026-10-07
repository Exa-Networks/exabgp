"""A route-origin extended community can be held in a set and used as a dictionary key.

Origin defined __eq__ and no __hash__, and Python answers that by setting __hash__ to None,
so every route-origin community (RFC 4360 3.1, 3.2 and RFC 5668's four octet form) was
unhashable. Route-target, written the same way, carries a __hash__ in each subclass and was
not affected. Anything which deduplicated communities through a set or keyed a cache on
them raised TypeError the first time it met a route-origin.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.community.extended.origin import (
    OriginASN2Number,
    OriginASN4Number,
    OriginIPASN,
)


def test_every_route_origin_form_is_hashable() -> None:
    for community in (
        OriginASN2Number.make_origin(65000, 100),
        OriginIPASN.make_origin('192.0.2.1', 100),
        OriginASN4Number.make_origin(4200000000, 100),
    ):
        assert isinstance(hash(community), int)


def test_equal_route_origins_collapse_in_a_set() -> None:
    first = OriginASN2Number.make_origin(65000, 100)
    again = OriginASN2Number.make_origin(65000, 100)
    other = OriginASN2Number.make_origin(65000, 101)
    assert first == again
    assert hash(first) == hash(again)
    assert len({first, again, other}) == 2
