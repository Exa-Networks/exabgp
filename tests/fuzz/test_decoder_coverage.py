"""The fuzz suite must reach the decoders it claims to cover.

Three times in one series a sweep reported a clean run over code it never executed:

  - the registries fill by import side effect, so a module which imported only what it
    named parametrised from a half empty registry
  - a catch-all converted every escape into a Notify, so a decoder with no length checks of
    its own looked exactly like one which had them
  - a probe wrote a one byte length for a sub-TLV type RFC 9012 gives two, so everything
    above type 127 died in the framing and never reached its decoder

Each time the number said "clean" and meant "not run".  A count of what is actually entered
is the cheap check for the last of those, and the only one which can be automated: the rest
is the rule that a sweep is evidence only once it has been made to go red.
"""

from __future__ import annotations

import struct
from collections import Counter
from typing import Any

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.nlri import NLRI


def _counted(owner: Any, name: str, label: str, tally: Counter) -> None:
    """Wrap one decoder so entering it is recorded.

    getattr walks the MRO and setattr lands on the subclass, so a decoder which is
    inherited rather than overridden is still counted for the class which uses it.
    """
    original = getattr(owner, name, None)
    if original is None:
        return
    function = original.__func__ if hasattr(original, '__func__') else original
    tally.setdefault(label, 0)

    def counting(*arguments: Any, **keywords: Any) -> Any:
        tally[label] += 1
        return function(*arguments, **keywords)

    setattr(owner, name, classmethod(counting) if hasattr(original, '__func__') else counting)


@pytest.mark.fuzz
def test_every_bgpls_tlv_decoder_is_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    """A BGP-LS TLV needs a Type(2) Length(2) header before its decoder sees anything.

    Fuzzing attribute 29 with random bytes practically never builds one, which is how a
    corpus of twenty thousand inputs covered none of the forty seven TLV decoders while
    reporting no regressions.
    """
    tally: Counter = Counter()
    for code, klass in LinkState.registered_lsids.items():
        monkeypatch.setattr(klass, 'unpack_bgpls', klass.unpack_bgpls, raising=False)
        _counted(klass, 'unpack_bgpls', f'{code}', tally)

    attribute = Attribute.klass_by_id(Attribute.CODE.BGP_LS)
    assert attribute is not None
    for code in sorted(LinkState.registered_lsids):
        for length in range(0, 24):
            for fill in (b'\x00', b'\xff', b'\x30'):
                try:
                    attribute.unpack_attribute(struct.pack('!HH', code, length) + fill * length, Negotiated.UNSET)
                except Notify:
                    continue

    never = sorted(label for label, count in tally.items() if count == 0)
    assert not never, f'these TLV decoders were never entered: {never}'


@pytest.mark.fuzz
def test_every_registry_is_whole_at_collection() -> None:
    """The registries must be full before anything parametrises from them.

    PrefixSid held two of its four TLVs until sr/srv6/l2service and l3service were
    imported.  conftest imports the package for exactly this reason; if that stops
    happening, a sweep silently covers a fraction of the codes.
    """
    import importlib
    import pkgutil

    import exabgp.bgp.message.update.attribute as package

    before = {
        'attributes': len(Attribute.registered_attributes),
        'capabilities': len(Capability.registered_capability),
        'nlri': len(NLRI.registered_nlri),
        'bgpls': len(LinkState.registered_lsids),
    }
    for _finder, name, _is_package in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        try:
            importlib.import_module(name)
        except ImportError:
            continue
    after = {
        'attributes': len(Attribute.registered_attributes),
        'capabilities': len(Capability.registered_capability),
        'nlri': len(NLRI.registered_nlri),
        'bgpls': len(LinkState.registered_lsids),
    }
    assert before == after, f'a registry grew when its modules were imported: {before} -> {after}'


@pytest.mark.fuzz
def test_every_nlri_family_decoder_is_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every registered family must be entered by the bytes the suite feeds it."""
    tally: Counter = Counter()
    seen: set[int] = set()
    for family, klass in NLRI.registered_nlri.items():
        if id(klass) in seen:
            continue
        seen.add(id(klass))
        monkeypatch.setattr(klass, 'unpack_nlri', klass.unpack_nlri, raising=False)
        _counted(klass, 'unpack_nlri', klass.__name__, tally)

    for afi, safi in sorted(set(NLRI.known_families()), key=lambda f: (int(f[0]), int(f[1]))):
        for length in range(0, 24):
            try:
                NLRI.unpack_nlri(afi, safi, bytes([length]) + bytes(length), Action.ANNOUNCE, None, None)
            except Notify:
                continue
            except Exception:  # noqa: BLE001 - the property tests judge this, we only count
                continue

    never = sorted(label for label, count in tally.items() if count == 0)
    assert not never, f'these NLRI decoders were never entered: {never}'
