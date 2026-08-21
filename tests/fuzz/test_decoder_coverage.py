#!/usr/bin/env python3
# encoding: utf-8

"""The corpus must reach every decoder it claims to cover

Three times while hardening the decoders, a sweep reported clean over code it
had never run:

  - the registries fill by import side effect, so a module importing only what
    it names parametrises over half of them
  - a catch-all at the boundary answered for decoders which check nothing, so
    every input produced a tidy Notify and nothing looked wrong
  - the corpus fuzzed the BGP-LS attribute with random bytes, which practically
    never forms a valid Type(2) + Length(2) header, so not one TLV decoder body
    was ever entered

A clean result over a fraction of the codes is worse than a failure, because it
reads as coverage and nobody looks again. These tests fail if any registered
decoder is never entered.

Note the instrumentation walks the MRO: wrapping klass.__dict__['unpack'] skips
every class which inherits its decoder, and reports them as unreached when they
are not.
"""

from struct import pack

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

from .corpus import FILLS, seeds_for


def _entry_counter(owner, name, tag_of):
    """Wrap a decoder wherever it is actually defined, following the MRO"""
    for klass in owner.__mro__:
        if name in klass.__dict__:
            original = klass.__dict__[name]
            break
    else:  # pragma: no cover - a decoder must exist
        raise AssertionError(f'{owner.__name__} has no {name}')
    function = original.__func__ if hasattr(original, '__func__') else original
    return klass, name, function, tag_of


class TestEveryBgpLsTlvIsReached:
    def test_the_corpus_enters_every_tlv_decoder(self, monkeypatch) -> None:
        entered = set()
        wrapped = {}
        for scode, klass in LinkState.registered_lsids.items():
            for owner in klass.__mro__:
                if 'unpack' in owner.__dict__:
                    wrapped.setdefault(owner, owner.__dict__['unpack'])
                    break

        for owner, original in wrapped.items():
            function = original.__func__ if hasattr(original, '__func__') else original

            def counting(cls, data, _function=function):
                entered.add(cls.TLV)
                return _function(cls, data)

            monkeypatch.setattr(owner, 'unpack', classmethod(counting))

        for scode in LinkState.registered_lsids:
            for length in range(0, 33):
                for fill in FILLS:
                    payload = (fill * (length // len(fill) + 1))[:length]
                    try:
                        LinkState.unpack(pack('!HH', scode, length) + payload, None, None)
                    except Exception:  # noqa: BLE001 - the property tests judge the outcome
                        pass

        never = sorted(set(LinkState.registered_lsids) - entered)
        assert not never, f'the corpus never entered these TLV decoders: {never}'


class TestEveryNlriFamilyIsReached:
    @pytest.mark.parametrize('family', sorted(NLRI.registered_nlri))
    def test_the_corpus_produces_an_nlri(self, family) -> None:
        afi_name, safi_name = family.split('/')
        afi, safi = AFI.value(afi_name), SAFI.value(safi_name)
        klass = NLRI.registered_nlri[family]

        for payload in seeds_for(family):
            try:
                result = klass.unpack_nlri(afi, safi, payload, Action.ANNOUNCE, False)
            except Exception:  # noqa: BLE001
                continue
            nlri = result[0] if isinstance(result, tuple) else result
            if nlri is not None:
                return

        raise AssertionError(f'{family}: the corpus never decoded a single NLRI, so it proves nothing')


# Ratchets on the registries these sweeps walk. Both files parametrise over a
# registry, so a registry which import order left nearly empty collapses the
# parametrisation instead of failing: this file reported 22 passing tests over
# the full registry and 4 passing tests over a thinned one, and 4 green tests
# look exactly like 22 green tests in a summary line.
#
# "The suite went red" is not evidence the suite noticed, and "the suite went
# green" over a shrunken parametrisation is not evidence there was nothing to
# find. Assert the haystack before reporting on the needles.
NLRI_FAMILY_FLOOR = 18
LSID_FLOOR = 30


def test_the_nlri_registry_is_populated() -> None:
    registered = sorted(NLRI.registered_nlri)
    assert len(registered) >= NLRI_FAMILY_FLOOR, registered


def test_the_linkstate_registry_is_populated() -> None:
    assert len(LinkState.registered_lsids) >= LSID_FLOOR, sorted(LinkState.registered_lsids)
