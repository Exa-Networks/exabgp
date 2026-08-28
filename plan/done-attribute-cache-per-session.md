# Plan: the attribute cache was one slot for the whole process

**Status:** ✅ Implemented
**Created:** 2026-08-22
**Last Updated:** 2026-08-22
**Origin:** workspace review finding F3, verified by probe before any change was made

---

## What was wrong

`AttributeCollection.unpack` kept the last parsed collection in two `ClassVar`s:

```python
cached: ClassVar[AttributeCollection | None] = None
previous: ClassVar[Buffer] = b''
```

One slot, shared by every BGP session in the process, with the raw attribute bytes as the
only key. Several attributes do not decode to a function of their bytes alone — they decode
against what the session negotiated. AIGP is the plainest: `AIGP.unpack_attribute` returns
the attribute when `negotiated.aigp` is set and a `Discard` when it is not. AS_PATH and
AGGREGATOR read differently under ASN4.

`negotiated` was not part of the cache key, so two peers sending byte-identical attributes
had the second handed the first one's parsed object — including the first one's
interpretation. Identical attribute sections are the common case, not a contrived one:
ORIGIN, AS_PATH, NEXT_HOP and LOCAL_PREF repeat constantly across peers.

The slot was also never cleared when a session ended, so a collection parsed for one peer
outlived it.

## The verification, before the fix

Not taken on the review's word. Decoding the same AIGP attribute bytes under each session,
with the cache cleared in between, gives two different and both correct answers:

```
aigp=False decoded alone : {'internal-discard': 'discard due to aigp'}
aigp=True  decoded alone : {'aigp': '0x000000000000002a'}
```

Through the shared cache, the second session got the first one's:

```
peer A (aigp=True) : {'aigp': '0x000000000000002a'}
peer B (aigp=False): {'aigp': '0x000000000000002a'}   <- wrong, should be a discard
SAME OBJECT RETURNED: True
```

A peer which never negotiated AIGP received an AIGP attribute, because another peer had
sent the same bytes first. That is a wrong route, not a cosmetic defect.

## What was implemented

The cache moved from the class to the session it belongs to.

- `Negotiated.__init__` gains `attribute_cache` and `attribute_cache_packed`.
- `AttributeCollection.unpack` reads and writes those instead of the `ClassVar`s, which are
  gone.

`Protocol` builds one `Negotiated` per session (`protocol.py:50`) and a fresh `Protocol` is
built per session (`peer.py:416` incoming, `:448` outgoing) — the same fact established for
the read-cancellation fix. So the cache is per session by construction, and it is discarded
with the session rather than needing to be cleared on disconnect.

The cache is scoped, not removed: a table dump sends many UPDATEs carrying identical
attributes from one peer, which is what it is for, and that case still hits.

## What was checked and deliberately left alone

**The mutation risk the review raised is already handled.** A cached collection which is
mutated downstream would be served in its mutated state on the next hit. The only mutation
of a *received* collection in the tree is `collection.py:634-635`, which pops MP_REACH and
MP_UNREACH — and `unpack` already refuses to cache any collection containing those. Every
other `attributes.add()` is on a collection built from configuration, never a parsed one.
That guard was left as it was, with a comment saying why it is there.

## Tests

`tests/unit/test_attribute_cache_per_session.py`, six cases:

- the second session does not inherit the first one's decode (the AIGP case above)
- the same claim with the sessions swapped, so a cache merely primed by whoever went first
  cannot pass by accident
- two sessions are not handed the same object — identity, not equality, because a shared
  object is a shared mutation
- the cache still serves a repeat within one session (deleting the cache would satisfy
  every assertion above, so this pins that it was scoped rather than removed)
- different attributes in one session are not confused
- a new session starts with no cache

They build a **real** `Negotiated` rather than a `Mock`. A Mock accepts any attribute and
returns a Mock for any read, so a cache stored on one would appear to work no matter what
the implementation did — the test would be asserting against its own fixture.

Break-it check: the process-wide cache was temporarily reinstated alongside the new one,
and the same four tests went red. Then removed.

## Verification

| Check | Result |
|---|---|
| ruff format / check | clean |
| mypy --strict | 388 files, no issues |
| unit + fuzz | 5174 passed, 6 skipped |
| tiger-style | bare_except 0, input_assert 0, long_function 91, silent_except 100 |
| compat_gate | 10226 inputs, 0 regressions |
| functional decoding | 22/22 |
| configuration validate | exit 0 |
| functional encoding | baseline parity (see blockers) |

## Failures

**The auto-linter removed the `TYPE_CHECKING` import while it was briefly unused**, between
adding the import and adding the annotation that referenced it, leaving ruff F821 and a
mypy `name-defined`. Re-added once the reference existed.

**`'AttributeCollection' | None` does not work.** The file has
`from __future__ import annotations`, so the annotation is already a string; quoting the
name inside a union makes it a nested string literal that neither ruff nor mypy resolves.
Unquoted is correct here.

## Blockers

None.

## Resume point

Implemented and verified. Nothing outstanding for this finding.

One thing deliberately not done: the cache has no measured benefit recorded anywhere.
TIGER_STYLE says a performance claim without a number is an opinion, and the number for this
cache has never been taken. Scoping it per session preserves whatever it is worth without
needing that number; deciding whether it earns its place at all needs a benchmark and is a
separate question.

## Post-review fix: the UNSET sentinel (2026-08-22)

Review found `_create_unset()` was not given the new cache fields, so
`AttributeCollection.unpack(data, Negotiated.UNSET)` raised AttributeError (latent — no
current caller does, but the sentinel exists exactly for callers without a session). Fixed
by mirroring the fields, plus `attribute_cache_enabled` (True per session, False on UNSET):
a cache written onto the process-wide sentinel would be the shared-slot bug all over again,
so unpack now skips caching for it. Three tests added, including a drift guard asserting
`_create_unset()` mirrors every `__init__` field (neighbor/direction deliberately excepted).
