# One signature for Attribute.json()

**Status:** ✅ Done 2026-09-29
**Created:** 2026-09-29
**From:** `done-review-quality-sweep.md` item 21

## Why

`Attribute.json(self, *args: Any, **kwargs: Any)` makes every override legal whatever it
accepts, so mypy checks none of them against the base. The `json` definitions under
`src/exabgp/bgp/message/update/attribute/`, counted 2026-09-29:

| Signature | Count |
|---|---|
| `(self)` | 41 |
| `(self, compact: bool = False)` | 25 |
| `(self, compact: bool \| None = None)` | 10 |
| `(self, include_nexthop: bool = False, generic: bool = False)` | 1 (`AttributeCollection`, not an `Attribute`) |

Not all of the 41 `(self)` definitions are on `Attribute` subclasses: several are sub-TLVs
(SR Policy segment lists, tunnel encapsulation TLVs) with their own base. Sort them first.

Callers pass arguments three ways: none, `compact` (BGP-LS), and
`AttributeCollection._generate_json` passes a **name** positionally for the `multiple`
representation (`attribute.json(n)`), which is a different method wearing the same name.

mypyc: a typed signature lets mypyc call `json()` through its vtable with native
arguments, where `*args, **kwargs` builds a tuple and a dict on every call. JSON rendering
runs once per UPDATE per API process, so it is on the output path. Do this before phase 5
of `plan-mypyc.md` measures the compiled build.

## What step 1 found

- Every `Attribute` subclass fits `json(self, compact: bool = False) -> str`. Only
  `LinkState` reads `compact`; the only caller passing it an attribute is
  `tests/fuzz/test_bgpls_tlv_properties.py` (`LinkState.json(True)`).
- 17 overrides on `Attribute` subclasses: 15 took no argument, `PrefixSid` and
  `TunnelEncap` took `bool | None = None` and ignored it. Nothing tested for `None`.
- The `multiple` representation had no entry in `AttributeCollection.representation`, so
  both its branches (text and JSON) were dead, and the JSON one would have raised
  TypeError: no `json()` took a name. Deleted, and `name` narrowed to `str`.
- BaseLS TLVs, SR TLVs, tunnel sub-TLVs and the plain `Community` are not `Attribute`
  subclasses and were left alone.

## Steps

1. [x] List every override and caller
2. [x] The `multiple` caller: dead, deleted rather than given its own method
3. [x] Base signature `json(self, compact: bool = False) -> str`, every override matching
4. [x] mypy strict clean (386 files), `./qa/bin/test_everything`

## Progress

Done in one change: `attribute.py`, `collection.py` and the 15 files holding overrides.

## Failures

## Blockers

None.

## Resume Point

Done.
