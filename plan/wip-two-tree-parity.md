# Two-tree parity: keep 5.0 production-safe, bring main's coverage up

**Status:** 🚧 In progress
**Started:** 2026-09-25
**Last Updated:** 2026-09-25
**Trees:** `main` (6.0.0, development) and `../5.0` (production). Separate clones, ~190 commits diverged.

## Why this file exists

Work has crossed between the two trees for several days and the state lives in commit
messages, agent reports and a compacted transcript. Anything not written here is lost.
Every item below is either done with a commit to point at, in flight, or waiting on a
decision. Nothing is "probably fine".

The divergence does not run the way a stable branch suggests. 5.0 is **ahead** of main on
the ASPath data model and on the fuzz corpus, and **behind** on the consumers of both.
Neither tree is a superset of the other, so parity has to be argued file by file.

---

## 1. Measured state, 2026-09-25

```
                 main    5.0
tests/unit       6676   2661
tests/fuzz        498   5063
tests/integration  16     16
tests/performance  59     59
                 ----   ----
                 7258   7826
```

5.0 does not have more tests. `tests/fuzz` accounts for the whole difference:

| fuzz file | main | 5.0 |
|---|---|---|
| `test_nlri_decoder_properties.py` | 105 | 2061 |
| `test_bgpls_tlv_properties.py` | absent | 1842 |
| `test_message_decoder_properties.py` | 152 | 737 |
| `test_attribute_decoder_properties.py` | 50 | 48 |

`tests/fuzz/corpus.py` exists only in 5.0. Without it a property test over a family whose
decoder needs a route distinguisher, or a length field agreeing with the buffer, sweeps
inputs rejected at the first byte and reports green while asserting nothing. main is in
that state today for every family the corpus seeds.

Unit test files: 62 shared by name, 114 only in main, 38 only in 5.0.

Ratchet floors: main `long_function: 81`, others 0. 5.0 lowered 2026-09-25 from
`long_function: 31` / `silent_except: 22` to **30 / 19**, once every agent had finished, since
lowering a shared ratchet mid-flight would fail the gate for whoever was still working.

Final state, 2026-09-25, both trees green:

```
main  9863 passed, 2 skipped, 7 xfailed, 0 failed   tests/fuzz 498 -> 2975
      check_exa_style / check_sweep_floors / check_rfc_compliance / ruff  ok
      compat_gate  10322 inputs compared, 0 regressions
5.0   8023 passed, 11 skipped, 8 xfailed, 0 failed
      check_tiger_style ok at the lowered floor, ruff ok
```

---

## 2. main: raise coverage

| # | task | status | note |
|---|---|---|---|
| 1.1 | port `tests/fuzz/corpus.py` from 5.0 | ✅ done 2026-09-25 | fuzz 498 → 2975. See §6. |
| 1.2 | port `test_bgpls_tlv_properties.py` from 5.0 | ✅ done 2026-09-25 | 2351 cases in main, wider than 5.0's 1842. See §8. |
| 1.3 | triage the 38 unit files only in 5.0; port behaviour, skip renames | ✅ done 2026-09-25 | 29 renames, 2 not-applicable, 5 real gaps, all ported. See §7. |
| 1.4 | audit every remaining `st.binary()` draw for luck-reachable cases | ✅ done 2026-09-25 | measured, not reasoned. See §13. |
| 1.5 | assert the corpus is *used*: a seeded family that stops being seeded must fail | ✅ done 2026-09-25 | `test_every_registered_family_carries_a_seed`, set equality both ways |

### Refused, with reasons

- 4 xfails stay. RFC 8669 ×2 (enforcing discards all SRv6 service routes: RFC 9252 Service
  TLVs 5 and 6 carry no Label-Index), RFC 6793 §4.1 (a fixture builds the peer's OPEN from
  our own capabilities), RFC 9552 §8.2.2 (violation is detected but answered with a reset
  rather than an NLRI discard).
- RFC 4271 §6.3 is marked not-applicable: the well-known-mandatory set is `{1,2,3,5,6}`,
  all registered, so the antecedent is empty.
- `_SEG_B_FLAG_S = 0x20` left alone: RFC 9831 §2.10 and §3.2 allocate it at bit 2 for
  Types C–K.

---

## 3. 5.0: production hardening

| # | task | status | note |
|---|---|---|---|
| 2.1 | sweep main's 114 unit-only files for bugs 5.0 still has | ✅ done 2026-09-25 | 8 more defects fixed, 7 confirmed and left. See §12. |
| 2.2 | `MPRNLRI` sends Cease over our *own* oversized attributes | ✅ fixed 2026-09-25 | and `MPURNLRI`, the same defect. See §9. |
| 2.3 | `Attributes.pack(with_default=False)` precedence bug | ✅ fixed both trees | `keys + (list(default) if ...)`; it was **hiding** 2.2 from the tests |
| 2.4 | `SRv6SID.pack()` TypeError | ✅ fixed 2026-09-25 | carried two worse bugs with it. See §9. |
| 2.5 | repeated BGP-LS attribute TLV emits a duplicate JSON key | ⚪ declined | see below |
| 2.9 | no sub-TLV length check at all in 5.0 | ✅ fixed 2026-09-25 | ported from main, overrun refused, remnant tolerated. See §11. |
| 2.6 | MP_REACH-first ordering not ported | ⏸ blocked | 91 captures need re-recording |
| 2.7 | dead `src/exabgp/cli/` VyOS prototype | ✅ removed 2026-09-25 | 6 files, `git rm`. `exabgp-cli` verified still working. |
| 2.8 | `src/exabgp/conf/yang/` now orphaned | ❓ decision | the deleted prototype was its only importer from outside |

### Already fixed and pushed (commits `2114ec208`, `a8683597e`)

Five crashes 5.0 had and main did not. None was in a commit being ported; each surfaced
because the agents read 5.0 rather than transplanting patches.

| where | failure |
|---|---|
| `merge_attributes` | `AttributeError` on any UPDATE carrying AS_PATH and AS4_PATH. Read `as2path.as_seq`; 5.0's `ASPath` holds `self.aspath`. Hit on every such UPDATE, at `attributes.py:394`. |
| `AS4Path.pack` | passed `True` where a `Negotiated` belongs |
| `Aggregator4` | inherited size-on-`negotiated.asn4`; a legal 8-octet AS4_AGGREGATOR was answered `Notify(3,5)` |
| `mprnlri.unpack` | two `IndexError` escapes to the reactor: `len(data) < 3` where main checks `< 5`, and an unbounded next-hop length |
| `cli reset` | sat out its own timeout, then blamed the reactor |

Also landed: BGP-LS Protocol-ID gates removed in five files; `GenericNodeDescriptor` added;
`unpack_descriptors` gained arity and ascending-order checks while keeping unknown-type
acceptance (it compares type codes only, never values); RFC 4760 reserved octet stepped
over; seven sites moved Notify 3/0 → 3/9.

### Refused, with reasons

- main's `[:-0]` AS_PATH fix **must never be backported**. It patches fields 5.0 does not
  have, in a function that cannot run there.
- 2.5: a fix was built and tested, then reverted. 5.0's own capture baseline enshrines the
  duplicate key and an existing test already records declining that compatibility break.
- The `$HOME` guard was skipped: mtime unchanged to the second, so the bug is absent.
- mypy `--strict` is a main/6.0 gate only, documented in both trees (5.0 `5f51f21c8`).
  5.0's source is unannotated tree-wide; the 5194 errors are not one file's imports.

---

## 4. Carried over, both trees

| # | item | status |
|---|---|---|
| 3.1 | respawn limiter shuts the daemon down on two reloads in one window | ✅ fixed both trees 2026-09-25, see §10 |
| 3.2 | `packed_reach_attributes` raises RuntimeError to the reactor (main) | 🔴 open |
| 3.3 | RIB yields one `UpdateCollection` per withdrawn NLRI | 🟡 open |
| 3.4 | `API/JSON-API-Reference.md` examples are structurally invented | 🟡 open |
| 3.5 | `doc/README.rst` stale | 🟢 open |
| 3.6 | 5.0 attribute cache is process-wide and keyed on wire bytes only | 🔴 confirmed, not fixed |
| 3.7 | 5.0: one peer's OPEN rewrites every other session's capability variant | 🔴 confirmed, not fixed |
| 3.8 | 5.0: a labelled NLRI with no S bit closes the session (RFC 8277 §2.2 says ignore it) | 🔴 confirmed, not fixed |
| 3.9 | 5.0 BGP-LS NODE/PREFIXv4/PREFIXv6 assign `self._pack` where the base reads `_packed` | 🔴 confirmed, not fixed |
| 3.10 | 5.0: a BGP-LS prefix NLRI with no Local Node Descriptors TLV ends the session | 🔴 confirmed, not fixed |
| 3.11 | 5.0 flow config silently drops an unparseable source/destination, giving discard-all | 🔴 confirmed, not fixed |
| 3.12 | 5.0 MULTISESSION Session ID never decoded, so the 2/8 refusal is dead code | 🟡 confirmed, not fixed |

Items 3.6 to 3.12 were each **reproduced by running**, not inferred, and deliberately left:
three agents were in the tree at once, 3.6 and 3.9 want doing together, and 3.8 has an interop
question worth a human. §12 carries the measured output for each.

The worst of them is 3.6. The cache is keyed on the wire bytes alone while AIGP decoding depends
on `negotiated.aigp` and AS_PATH reads 2 or 4 octets from `negotiated.asn4`. Measured: an
`asn4=True` session primes the cache and the next `asn4=False` session is handed
`as-path=( 65538 )` where it should treat-as-withdraw. **A route installed that should have been
withdrawn**, across sessions, in production. RFC 7311 §3.2 and RFC 6793 §4.2.2. The fix is small,
moving two slots onto `Negotiated`, one caller, and several 5.0 tests already reset them by hand
so nothing argues for the present behaviour.

**Hard constraint on all JSON work:** do not break parsers users run today. Additive only.
No rename, no removal, no retype of an existing key.

---

## 5. Waiting on Thomas

1. ~~Delete 5.0's `src/exabgp/cli/`~~ done. `src/exabgp/conf/yang/` (7 files) is now
   orphaned by it: imports cleanly, nothing references it. Delete or keep?
2. ~~Open an issue for the respawn limiter~~ fixed instead, §10.
3. **RFC 9552 §5.2 and the BGP-LS VPN route distinguisher.** The quotable sentence ("The
   Total NLRI Length field contains the cumulative length ... For VPN applications, it also
   includes the length of the Route Distinguisher.") carries **no RFC 2119 keyword**, so it
   needs a `level` decision before it can go in `qa/rfc/rfc9552.toml`, plus a baseline bump
   in `qa/rfc_compliance.json`. The code is fixed either way; this is about the ledger.
4. **main proves the RD-must-be-zero next-hop rule with one pattern** where 5.0 sweeps all
   eight byte positions. Source is right; only the sweep is thinner.
5. **main dropped `as_dict()` from the BGP-LS TLVs**, so 5.0's dual-renderer agreement sweep
   has nothing to attach to. Nothing owed if that was deliberate.

---

## 6. The fuzz corpus in main, 2026-09-25

`tests/fuzz` went 498 → 2975 collected. Honest attribution: +74 of it is the corpus in
`test_nlri_decoder_properties.py`, and 2351 is the separate `test_bgpls_tlv_properties.py`.

The measurement which justified it. main's drawn NLRI sweep decoded **nothing at all** for
seven of twenty-three families, 600 decodes each:

```
ipv4/flow 0/600   ipv4/flow-vpn 0/600   ipv6/flow 0/600   ipv6/flow-vpn 0/600
ipv4/sr-policy 0/600   ipv6/sr-policy 0/600   l2vpn/vpls 0/600
ipv4/mpls-vpn 3/600    bgp-ls 22/600     bgp-ls-vpn 22/600
```

A `framed()` strategy landed mid-task and helped MUP and EVPN while leaving the hard cases
alone: five families still decode nothing, four more are reached by luck. Those numbers are
in the corpus docstring so they can be re-derived rather than trusted.

Two seeds were deliberately **not** ported. 5.0 decodes a rule-less flow NLRI; main refuses
it with `Notify(3, 10, 'flow NLRI carries no component, which would match every packet')`.
main is stricter and right, so they went to `REFUSED_SEEDS` as negative coverage instead of
being dropped.

### Bug: VPLS kept the peer's length in front of a truncated payload

`unpack_nlri` accepts `length >= 17` on purpose, a sender may carry a field we do not know,
but it kept the two byte prefix saying 18 while retaining only 17 payload bytes:

```
pack_nlri() -> 00120000000000000000000000000000000000  (19 bytes, header claims 20)
re-unpack   -> Notify: Invalid Network Field / l2vpn vpls message length is not
               consistent with encoded bgp
```

76 corpus inputs hit it. The second effect is worse than the roundtrip: `index()` is
`_packed`, so one route framed at length 17 and at length 18 had **two** indexes, and a
withdraw framed differently from its announce missed in the RIB.

### Bug: BGP-LS VPN `pack_nlri` dropped the route distinguisher

Two VPN routes differing only in their RD packed to identical bytes and had identical
`index()`, while `__eq__` and `__hash__` reported them different. A withdraw for one took
the other out of the RIB.

Found by the corpus agent, which judged it too large to fix and left `xfail(strict=True)`
against RFC 9552 §5.2. The BGP-LS agent then landed `BGPLS._wire()`, the xfail turned
`XPASS(strict)` and failed the suite. That is exactly what strict is for, and it is the only
reason the two agents' work was reconciled rather than one silently masking the other.

---

## 7. The 38 files only in 5.0, resolved 2026-09-25

29 renames, 2 not-applicable, 5 real gaps. Two of the 29 were literal moves: main has
`tests/unit/{application,reactor,rfc,cli,bgp,configuration}/` subtrees, so comparing top
level filenames overstated the gap. The full row-by-row table is in the agent transcript.

Ported, 109 tests, all passing:

| new file in main | tests | outcome |
|---|---|---|
| `test_attribute_json_scalars.py` | 49 | **bug found and fixed** |
| `test_gate_exit_codes.py` | 15 | **bug found and fixed** |
| `test_bgpls_decode_boundary.py` | 11 | green, forced red first |
| `test_notification_direction.py` | 10 | green |
| `test_rib_refresh_snapshot.py` | 24 | green, forced red first |

The three green ports were each broken deliberately before being believed, per EXA_STYLE section 5
"a sweep is evidence only once it has gone red": widening `_decode_tlv`'s except tuple gave
2 failed, keying `refresh_routes` on enumeration instead of `route.index()` gave 22 failed.
Sources restored, `git diff` confirmed empty.

### Bug: `_as_json_scalar` emitted bare text no JSON parser accepts

`AttributeCollection._generate_json`, the `how == 'integer'` branch, reached by MED,
LOCAL_PREF, AIGP and OTC. It decided "is this a number" with `int(text)`, and Python's
`int()` accepts four shapes JSON forbids, all of which went out unquoted:

```
'010' -> '010'     '00' -> '00'     '1_000' -> '1_000'     '+5' -> '+5'
json.decoder.JSONDecodeError: Expecting ',' delimiter  s = '{"med": 1_000}'
```

Fixed by matching the RFC 8259 §6 integer grammar instead. **Latent, not live:** no
attribute renders one of those shapes today, which is precisely what the 5.0 test guards,
because the next attribute put on that branch inherits the trap. JSON constraint verified
rather than asserted: `./qa/bin/test_json` reports 296 passed, 0 failed, so no recorded
output moved. `med` and `local-preference` stay JSON numbers, `aigp` stays the quoted
`"0x00000000000000 0a"` string it already was.

### Bug: three CI gates answered 1, or 0, on a path where they had not run

`compat_gate` already answered 2 for a tree it could not read, pinned by
`test_gates_are_wired.py:194`. Three others did not:

| gate | before |
|---|---|
| `check_tests_run` | printed "pytest collected nothing at all, so this check proves nothing" then exited 1 |
| `check_sweep_floors` | returned 1 for "collected no tests at all, which cannot be right" |
| `check_exa_style` | **had no cannot-run path at all**: `rglob` over a missing tree yields nothing, every rule counts 0, it prints `ok` four times and **exits 0** |

The last is the one that matters. A clean bill of health over an empty walk, and nobody
investigates a green gate. This is the fourth instance of the pattern in §14 below. Each gate
now has `CANNOT_RUN = 2`, and `check_exa_style` a `MIN_SOURCE_FILES = 50` floor on the walk
against 392 today, so it cannot fire on a real checkout.

### Left open by this agent, for decision

- main dropped `as_dict()` from the BGP-LS TLVs, so 5.0's dual-renderer agreement sweep and
  its recorded `area-id` str/int disagreement have nothing to attach to. Nothing is owed if
  dropping it was deliberate.
- main proves the RD-must-be-zero next-hop check with one non-zero pattern where 5.0 sweeps
  all eight byte positions. `mprnlri.py:259` already slices all eight, so the source is
  right and only the sweep is thinner.

---

## 8. BGP-LS TLV properties in main, 2026-09-25

2351 cases, against 5.0's 1842, because main's registry is wider: **47** registered LSIDs to
5.0's 39. Two properties added that 5.0 has no equivalent of: that the same TLV twice never
names a JSON member twice, and a sub-TLV length class.

**Correction to something I had backwards.** Commit `2114ec208` is a backport *from* main
*into* 5.0, not the other way round. main already had Protocol-ID gate removal,
`GenericNodeDescriptor`, and the arity plus ascending-order checks in `unpack_descriptors`,
and had them first. My earlier framing of that work as originating in 5.0 was wrong. What is
still true is that 5.0 leads on the ASPath data model and led on the fuzz corpus.

One divergence recorded rather than ported: 5.0 asserts TLVs 1099 and 1158 accept a 2 or 3
octet payload. main refuses both, and main is right — RFC 9085 §2.2.1 and §2.3.1 give them
flags(1) + weight(1) + reserved(2) before the SID. 5.0's assertion is a 5.0.12 upgrade
concession, not a requirement.

### Bug: a sub-TLV length that overruns its enclosing TLV was compared with nothing

RFC 9552 §8.2.2 requires a speaker to validate "the length of each TLV and, when the TLV is
recognized then, the length of its sub-TLVs". `Srv6EndX._unpack_data` and `Srv6._unpack_data`
walked sub-TLVs with `data[4 : length + 4]`. **Every read was a slice, and a slice cannot
raise**, so the declared length was never checked against what remained. There is no
traceback to show, and that is the defect: silent acceptance is exactly why the fill-pattern
and random-byte sweeps came back clean over it.

A sub-TLV declaring 1000 octets with none present rendered `"unknown-subtlv-9999": "0x"`.
A trailing stub too short for a header was dropped without a word. Fixed with
`unpack_subtlvs()`; since `LinkState.DISCARD` is True the `Notify` becomes the Attribute
Discard that same section asks for, not a session reset.

### Bug: `Srv6LanEndXOSPF` read the SID from the wrong offset — in BOTH trees

`start_offset = 12 if protocol_type == ISIS else 6`. RFC 9514 §4.2 gives OSPFv3 a **four**
octet Router-ID where IS-IS has a six octet System-ID, so the SID starts at 10. Offset 6 is
where the Router-ID begins.

Fixed in main by the agent; **5.0 was left unfixed and I fixed it here.** 5.0 had two faults,
not one:

```python
FIXED_SIZE_OSPF = 22                        # should be 26 = 6 + 4 + 16
start_offset = 12 if type == ISIS else 6    # should be 10
```

The wrong constant agreed with the wrong offset, so neither length check could catch either.
Reproduced: `sid` came back `c000:201:fc00::` instead of `fc00::3`, with a stray
`"0-undecoded"` member invented from the SID's tail. Worse, **HEAD accepted a truncated SID**:
a 25 octet body passed the length check and the SID was read past the end of the buffer, which
is the EXA_STYLE "check the length before reading wire data" rule rather than merely a wrong
offset. Red-then-green against HEAD loaded via `git show` with `@LinkState.register()`
stripped: 0 of 5 at HEAD, 7 of 7 with the fix.

The two main fixes had to land together: with the length check in and the offset still 6, a
valid OSPF LAN End.X packed by our own factory would have been refused.

### Left as a strict xfail: a repeated sub-TLV loses the first one

`json.loads('{' + ', '.join(subtlvs) + '}')` writes the same member twice and keeps the last.
Not fixed, and the reason is the JSON constraint: RFC 9552 §8.2.2 forbids calling the
attribute malformed over which sub-TLVs it carries, so `Notify` is wrong, and the right
answer is an array, which reshapes a published member. Recorded with the section reference.

### My coordination failure

I fixed 5.0's OSPF offset while the 114-file hunt agent was independently reaching the same
bug, so 5.0 briefly had two test files for one fix. Consolidation handed to that agent. The
lesson: before fixing anything myself, check what the running agents' briefs already cover.

---

## 9. The two open 5.0 defects, fixed 2026-09-25

Both were real and both recorded descriptions were accurate. Each carried a worse bug than
the one recorded.

### 2.2 The MP path answered our own encoding limit with a Cease

`Update._mp_messages` guards `msg_size <= 0`, and a comment claimed `packed_attributes`
"raises rather than yield nothing, so it is never called with a budget which cannot hold
anything". That claim was false: a budget which is **positive but narrower than one MP
attribute** sails past the guard, and both methods then did

```python
raise Notify(6, 0, 'attributes size is so large we can not even pack on MPRNLRI')
```

6/0 is Cease / Unspecific, and `reactor/peer.py:706` puts it on the wire. Three arguments
against it, in order of weight: the peer did nothing, and RFC 4486's Cease subcodes are all
administrative, which is why the code fell back to Unspecific; a Cease does not achieve the
withdrawal it stands in for, since the unpackable route is still in our RIB on
re-establishment, so it is a flap loop rather than a failure; and it was inconsistent, as
5.0's own native IPv4 pass already handled the identical condition with `log.critical` and
no exception. One UPDATE, two policies, chosen by address family.

Now it logs and leaves the route out, matching the native pass rather than being stricter.
`MPURNLRI` was fixed too: same defect, same two lines, same call site, and only the
MP_REACH half happened to be in the report.

**A second bug the rewrite closed.** Old and new run side by side over 15 NLRI sets × 400
budgets: 5575 byte-identical, 410 where the old code raised, and 15 genuine differences. In
all 15 the old loop restarted the payload with the NLRI that had just overflowed already
inside it, and only measured again on the *next* one, so it emitted attributes **wider than
the budget** — UPDATEs past the negotiated maximum message size, which RFC 4271 §4.1 makes
the peer answer with Bad Message Length.

### 2.4 `SRv6SID.pack()` raised TypeError

`unpack_nlri` never stored the wire bytes, so `_packed` stayed `b''` and `pack()` tried to
rebuild the NLRI from the parsed form, concatenating a list of `NodeDescriptor` onto bytes.
Reached in production by `show adj-rib … json` for any received SRv6 SID route, via
`BGPLS.as_dict()` → `_raw()` → `pack()`.

Two consequences worse than the TypeError:

- `NLRI.index()` reads `pack_nlri()`, which read the never-filled `_packed`, so **every**
  SRv6 SID NLRI indexed to the same four octets `00 06 00 00` and hashed identically. The
  RIB held one SRv6 SID route however many the peer advertised.
- the deleted `pack()` override left out the RFC 7752 §3 NLRI Type and Total Length header
  entirely, so even had it not raised it would have produced an NLRI no peer could parse.
- `__len__` counted descriptor *entries* as octets: 12 where the answer is 45.

The registry was checked on a full import, not a partial one, per the earlier lesson:
`registered_bgpls` holds 1, 2, 3, 4, 6 and `SRv6SID` is registered under 6.

### The two 5.0 fixes interlock with 2.3

The `Attributes.pack` precedence bug was **hiding** 2.2 from the existing tests. With
`with_default=False` encoding nothing, an MP_UNREACH-only UPDATE was never sized against
real attributes. Fix the brackets and it is suddenly sized against 4061 octets, and the old
`packed_attributes` answers that with a Cease. Neither fix was complete without the other.

### Disclosure, verified

While measuring a baseline, one agent ran `git diff -- src/ > patch` and `git apply -R`,
which silently caught another agent's uncommitted `attributes.py` alongside its own and
briefly reverted it. It noticed, restored with `--exclude`, and disclosed. I checked myself:
`alls = set(keys + (list(default) if with_default else []))` is at line 350 and the four
`TreatAsWithdraw()` calls are present. Intact.

5.0 suite after both fixes: **7924 passed, 11 skipped, 8 xfailed, 0 failed.**

---

## 10. The respawn limiter, confirmed 2026-09-25

Reproduced in both trees with a real traceback, not inferred.

`self.respawn_number = 5 if getenv().api.respawn else 0` makes one variable both the on/off
switch and the per-window limit, so switching respawning off sets the limit to zero. The
limit is tested on *every* `_start`, not only on a respawn, so the second start of a helper
in one window trips `2 > 0` with nothing having died. `ProcessError` is not in `_start`'s
`except (CalledProcessError, OSError, ValueError)`, so it reaches the reactor's
`except ProcessError` and the daemon exits 1.

**Correction to the earlier description:** the window is not "63 seconds". It is
`int(time.time()) & 0xFFFFC0` — 64 seconds aligned to the wall clock, not since the last
start. Two reloads one second apart can trip it; two a minute apart can miss it across a
boundary. That is why it presents as random.

| | what it takes |
|---|---|
| 5.0 | two full reloads in one window, configuration **unchanged**. `start(restart=True)` terminates and restarts every helper with no comparison. |
| main | the same, but main compares the stanzas first, so the helper's `run`, `encoder` or `respawn` must also have changed. |

Every diagnostic an operator gets is wrong: 5.0 prints `Too many death for helper (0)
terminating program` (nothing died, and the limit reads 0 because respawning is off), main
prints `process.respawn.exceeded process=helper limit=0`, and both then print
`Problem when sending message(s) to helper program, stopping` when nothing was being sent.

5.0 also raises *without* terminating the helper it just spawned, where main calls
`self._terminate(process)` first, so 5.0 orphans it as the daemon exits.

Uncaught because `tests/unit/test_reactor_api_processes.py`, the one file covering
reload-restart, replaces `_start` with a stub and so never reaches the counter.

### Fixed 2026-09-25, both trees

The count moved off `_start` and onto the respawn path. `_handle_problem` already tests
`if self.respawn_number and self._restart[process]` on its own, so the limit never needed to
carry the switch. A helper started because the configuration was read now records nothing at
all, and `_record_respawn` is the only thing which raises.

- main: `_handle_problem` calls `_record_respawn` then `_start`, both inside the existing
  `contextlib.suppress(ProcessError)`, so a helper past its budget is left stopped and the
  asyncio callback survives. The `self._terminate(process)` inside `_record_respawn` went
  away because the caller terminates first.
- 5.0: the counting block was inline in `_start`; it is now a `_record_respawn` method called
  from `_handle_problem`. 5.0 has no suppression there, so a helper which cannot stay alive
  still stops the daemon. That behaviour is preserved deliberately, and pinned.

Red-then-green, with HEAD loaded from `git show` as a separate module so neither tree was
disturbed: 0 of 3 reload assertions passed at HEAD in both trees, 5 of 5 pass with the fix
in both.

`tests/unit/test_api_process_start.py::TestStartRespawn` had to be rewritten. Five of its
tests described `_start` keeping the count, and one of them,
`test_with_respawn_disabled_a_second_start_in_the_window_is_refused`, pinned the defect as
behaviour with the docstring "Pins current behaviour, which looks wrong, and is reported
rather than changed". It is now
`test_with_respawn_disabled_a_second_start_in_the_window_is_allowed`. 27 pass.

New: `tests/unit/test_respawn_limit_counts_respawns_only.py` in both trees, 5 tests each,
with time frozen so the wall-clock bucket cannot make them flaky.

Side effect: 5.0's ratchet improved to `long_function: 30` (was 31) from extracting the
method, and `silent_except: 19` (was 22) from deleting the VyOS prototype. **The baseline
still needs lowering with `--update-baseline` once the agents in flight have reported.**

---

## 11. The sub-TLV length check, and the compatibility decision

`qa/bin/compat_gate` caught main's new RFC 9552 §8.2.2 check breaking nine real inputs:

```
lsid/1106/23/00   ACCEPT:328e4 -> REFUSED
lsid/1106/24/30   ACCEPT:9dd6f -> REFUSED
lsid/1106/25/ff   ACCEPT:1b86a -> REFUSED
```

TLV 1106's fixed part is 22 octets, so payload lengths 23, 24 and 25 carry a 1, 2 or 3 octet
trailing remnant, too short for a sub-TLV header. Those used to decode with the remnant
silently dropped; the new check discarded the whole BGP-LS attribute, so an SRv6 End.X SID
from a peer which pads its TLV went dark on upgrade.

**Thomas's decision: tolerate the remnant, keep the overrun check.** Two cases, answered
differently on purpose:

| input | answer | why |
|---|---|---|
| sub-TLV *claiming* more octets than remain | refused | a length the peer got wrong about data we would go on to read. This is the half worth having: at 5.0 HEAD a sub-TLV claiming **65535** octets was accepted and rendered `0xAABB`. |
| trailing remnant too short for a header | ignored | costs no route and tells an operator nothing they can act on. Refusing it cost a working deployment its route. |

main: `0 regressions, exit 0`, with no entry added to compat_gate's allowed list. The three
tests that asserted the refusal were rewritten, and a new one pins that forgiving the remnant
does not bring back a member invented from its octets.

5.0: ported, and **no compatibility break there at all.** Red-then-green against HEAD showed
the three remnant cases already passed, because 5.0 was already tolerant; only the four
overrun cases went red → green. So 5.0 gains the fix and loses nothing.

One deliberate divergence: main logs the ignored remnant, 5.0 does not. 5.0's `log.debug`
raises `AttributeError` when `option.logger` has not been set, and this branch is reached by
ordinary peer data rather than only by an error path, so on the production tree that line
would turn a decode which works into a crash. Recorded in the code rather than in a log line.

The two published member names were preserved and must stay different: `subtlv-not-implemented-N`
for End.X, `N-undecoded` for its LAN siblings. The shared helper takes a formatter for exactly
that reason, and both names are pinned by tests.

---

## 12. Sweep of main's 114 unit-only files against 5.0, 2026-09-25

Method: copy all 114 into a scratch directory, collect them against 5.0's source with
`env -u PYTHONPATH`, and read the 61 collection errors as a map of main-only constructs.
Then re-drive each prioritised file's *assertions* against 5.0's own API as a probe script,
and prove every claim by running it. A read-only control was built with
`git archive HEAD src | tar -x -C /tmp/.../head50` plus a conftest asserting
`exabgp.__file__` resolves inside it, so every new test was shown red at HEAD and green
with the fix.

### Fixed in 5.0, each with a test which fails at HEAD

| where | failure | test |
|---|---|---|
| `attributes.py` `parse` | an Attribute Length past the end of the section was silently truncated: a COMMUNITY declaring 12 bytes with 4 present arrived as the one community those 4 decoded to. Same slice reached `NextHop.unpack(b'')`, which answers `NoNextHop`, and `add()` read `.ID` off it: `AttributeError` from four peer-chosen octets | `test_attribute_length_overrun.py` |
| `attributes.py` `parse` | tail-called itself per attribute: 996 three-byte attributes in a 3015-byte UPDATE raised `RecursionError`, answered to the peer as `Notify(1,0)` "malformed header" and a reset. Now a loop with a no-progress guard | `test_attribute_parse_iterative.py` |
| `bgpls/tlvs/ipreach.py` | no bound on prefix length or octet count: an oversized IPv6 reachability TLV let `ValueError` escape to the reactor (reset with **no NOTIFICATION**) from a 36-byte NLRI; IPv4 published "1.1.1.1.1/32"; a /255 was reported verbatim | `test_bgpls_ipreach_bounds.py` |
| `nlri/flow.py` | `FlowIPProtocol`/`FlowNextHeader` decoded with `ord`, so a protocol match in 2, 4 or 8 octets (all legal, RFC 8955 4.2.1.1) raised `TypeError`, uncaught: reset with no NOTIFICATION, **and the peering never re-establishes** | `test_flow_operator_value_width.py` |
| `configuration/neighbor/__init__.py` | `OperationalFamily.family()` is a tuple; `.afi_safi()` was called on it, so **every** config with an `operational` block refused to load | `test_operational_configuration_section.py` |
| `configuration/static/mpls.py` `route_distinguisher` | `rd 12345` / `rd :100` → `UnboundLocalError`; `rd 1.2:100`, `1.2.3:100`, `1.2.3.4.5:100` accepted and packed 6, 7, 9 octets **onto the wire**; negative fields → `struct.error` | `test_route_distinguisher_configuration.py` |
| `configuration/static/parser.py` `prefix`, `mpls.py` `prefix_sid` | bare `OSError` from `inet_pton`, and `UnboundLocalError` for `bgp-prefix-sid 300` | `test_configuration_static_parser_errors.py` |
| `bgpls/link/srv6lanendx.py` | OSPFv3 SID read at offset 6 (the Router-ID), `FIXED_SIZE_OSPF` 22 agreed with it; published `c000:201:...` and invented a `0-undecoded` member. Fix landed concurrently; the two duplicate test files were merged | `test_bgpls_srv6_lan_endx_offset.py` |

Also added `test_attribute_error_handling.py`: a `registry_floor` sweep over every registered
attribute code asserting nothing escapes the parser as a raw exception. It is what found the
`NoNextHop` crash, and `check_sweep_floors` accepts its floor.

### Confirmed by a real run, NOT yet fixed — highest value left on the board

1. **Attribute cache is process-wide and keyed on the wire bytes only** (`attributes.py:148-151`,
   `393-411`). AIGP decodes to nothing on a session which did not negotiate it and AS_PATH
   reads 2 vs 4 octets from `negotiated.asn4`, yet `negotiated` is not in the key. Measured:
   `asn4=True` primes the cache and a following `asn4=False` session is handed
   `as-path=( 65538 )` where it should treat-as-withdraw. RFC 7311 3.2, RFC 6793 4.2.2. Fix:
   move `cached`/`previous` onto `Negotiated` (one caller, `update/__init__.py`). Several 5.0
   tests already reset the two slots by hand to work around it.
2. **One peer's OPEN rewrites every other session's capability variant**
   (`capability/capability.py:199`, `kls.ID = what`). `RouteRefresh` and `MultiSession` are each
   registered under two codes and resolve to the same class object, and `__str__`/`json()` read
   `self.ID`. Measured: an established RFC peer's JSON flipped to `"variant": "Cisco"` when a
   second peer opened. Fix: set the code on the instance in `Capability.unpack`, as main does.
3. **A labelled NLRI whose single label has no S bit closes the session** (`nlri/inet.py:136-169`).
   RFC 8277 2.2 says that bit "MUST be ignored on reception", and 2.4 says the same of the
   MP_UNREACH Compatibility field. 5.0 answers `Notify(3,10)`. Fix at depth one only: end the
   stack on the NLRI Length; leave depth two and beyond refusing.
4. **BGP-LS NODE / PREFIXv4 / PREFIXv6 assign `self._pack`, base reads `self._packed`**
   (`bgpls/node.py:51`, `prefixv4.py:68`, `prefixv6.py:68`). `pack_nlri()` returns a 4-byte
   header with length zero, so **every** BGP-LS node route shares one RIB key and adj-rib-in
   collapses hundreds of routes to one. A BGP-LS VPN NLRI also loses its RD on re-encode
   (`bgpls/nlri.py:201-205`). Goes together with `node.py`'s `__eq__`/`__hash__` incoherence:
   `a == b` is True for two different routes while `hash(a) != hash(b)`.
5. **A BGP-LS prefix NLRI with no Local Node Descriptors TLV ends the session**
   (`prefixv4.py:101-107`, `prefixv6.py` same). RFC 9552 8.2.2 forbids calling an NLRI
   malformed over the exclusion of a TLV; `link.py` already accepts its absence. `local_node`
   is already `[]`, so only the IP Reachability half is load-bearing.
6. **Flow configuration silently drops an unparseable source/destination**
   (`configuration/flow/parser.py:82-115`): `flow { route x { source not-an-ip; then discard; } }`
   announces a zero-length FlowSpec NLRI, which RFC 8955 4.2 makes a **match-everything**
   rule, so a typo becomes discard-all. `/33` reaches the wire as `0x21`.
7. **MULTISESSION Session ID is never decoded** (`capability/ms.py:46-49`), so the RFC's
   Grouping Conflict refusal (2/8, already named in `notification.py`) is dead code. Only with
   `capability multi-session` configured. The fix has an exabgp↔exabgp interop wrinkle: 5.0
   packs the flags byte and each code as separate one-byte TLVs.

### Latent, or blocked, with the reason

- `Attributes.pack` raises `AttributeError` on a collection holding `Discard`/`TreatAsWithdraw`,
  because 65534/65535 are commented out of `INTERNAL`. **Do not fix by uncommenting them**:
  `NO_GENERATION = (NEXT_HOP,) + INTERNAL` feeds `_generate_json`, so that would REMOVE the
  published `"error"` key. Any fix must skip the two codes inside `pack()` only. No
  wire-reachable path found today.
- The fixed-size qualifier helpers (`ESI`, `EthernetTag`, `MAC`, `RouteDistinguisher`, `Labels`)
  truncate or raise `struct.error` on short input where main raises `Notify(3,10)`, but every
  caller in 5.0 validates the length first. Hardening gap, not live.
- `NLRI.__eq__` raises on a non-NLRI where `cidr.py` already returns `NotImplemented`. Not
  reachable from `src/`; inconsistent with the tree's own settled contract.
- A FlowSpec protocol value above 255 in a wide field decodes and then raises `ValueError` from
  `IOperationByte.encode` (`bytes([262])`) when rendered. **Present in both trees**: main uses
  the same `_number` decoder and the same `encode`.
- BGP-LS opaque TLVs (1025/1097/1157) publish arbitrary IGP bytes as lossy text; hex would
  retype a published key, and 5.0's `test_bgpls_json_escaping.py` asserts the text form.
  Reported, not touched.
- A repeated non-MERGE BGP-LS TLV still emits its key twice (33 of 39 TLVs). Left alone per
  §2.5 and 5.0's own `TestAKnownDisagreementLeftAlone`.
- `IPv4.create('2001:db8::1')` returns an `IPv6` (`IP.create` ignores `cls`). No caller in 5.0
  asks a concrete class for a family, so hardening only.
- 5.0 already satisfies, verified by running: the malformed-input Notify sweep over all 21 NLRI
  families, attribute codes 0-44 and message types 1-7/255 (0 escapes); the OPEN/UPDATE/
  KEEPALIVE minimum-length answers with the RFC 4271 6.1 Length in the Data field; unknown
  message type; flow_vpn short RD; AGGREGATOR discard; `Notification` truncated below 2 bytes;
  the API JSON member contract for all 8 families; family completeness; addpath wire encoding;
  NLRI deepcopy; CIDR ordering.

### Verification, 2026-09-25 (includes other agents' concurrent work in the same tree)

```
env -u PYTHONPATH exabgp_log_enable=false uv run pytest ./tests/ -q
7997 passed, 11 skipped, 8 xfailed, 1 warning in 100.36s
check_tiger_style: bare_except 0, input_assert 0, long_function 30 (down from 31), silent_except 19 (down from 22)
check_tests_run: ok, 136 files      check_sweep_floors: ok, 22 files checked
ruff format / ruff check: clean     functional encoding, decoding, parsing: all green
```

---

## 13. The luck audit, 2026-09-25

The probabilities were **measured**, not reasoned: each candidate draw run under 40
independent seeds × 200 examples with `derandomize=False`. The harness was validated against
the documented precedent first — the plan says a uniform byte draw is a non-finite float 0.39%
of the time, so 54% of runs find it; measured 0.56% of examples and 72.5% of rounds, higher
because Hypothesis biases bytes toward `0x00`/`0xFF`. The precedent reproduces.

The worst rows were not improbable but **impossible**:

| draw | gate | found in 200 |
|---|---|---|
| attribute decoders 14/15 with `Negotiated.UNSET` | `(afi,safi) in negotiated.families`, and UNSET has none | **0 of 40 rounds, 0 of 1000 examples** |
| `test_update_split` withdrawn length | `withdrawn_len == 10`, the only accepting value | 0.15% arithmetic, **0 of 40 measured** |
| `test_update_split` attribute length | `attr_len == 15` | 0.15%, **0 of 40** |

`Negotiated.UNSET` negotiated no families and RFC 4760 §7 refuses a non-negotiated family
before reading anything, so MP_REACH and MP_UNREACH — the two attributes carrying every family
but IPv4 unicast — were entered and rejected at byte three for every input that sweep can draw.

Fixed by construction, not by raising the example count: a new `framed()` strategy which draws
the payload first and then the length as `st.one_of(the truth, a value the payload can hold,
anything at all)`, so a third of examples agree by construction while the disagreeing draws
that the truncation checks exist for are kept. Plus `@example` pins for the single-value gates.
45 of 46 MP parametrisations now decode and render. Capability lift measured:
`software-version` 3.1% → 30.7%, `hostname` 0.1% → 4.4%.

**Proof the pins are load-bearing:** changing `assert len(withdrawn) == 10` to `== 11` fails
with the pin and *passes* without it. The three assertions behind that branch had never run.

Where construction found nothing, that is a coverage gain and not a defect list: FlowSpec by
construction went from 0/1000 accepted to 1016/2000 with zero escapes, and MP_REACH over all
23 families × every declared next-hop size also found zero.

---

## 14. Process rules learned the hard way

- **Never `git add -A`.** Commit `2114ec208` swept up an agent's unreviewed BGP-LS work and
  was pushed with a message that did not describe it. Corrected in `a8683597e` rather than
  by rewriting public history. Stage file by file, every time, including the last commit.
- **`env -u PYTHONPATH` in 5.0.** `PYTHONPATH` pointed at `main/src`, so every bare
  `uv run` in 5.0 imported main's source. It invalidated two suite results I had reported.
- **Re-record captures against a read-only HEAD control** via `git archive`, with an assert
  on the import path, and reproduce byte-for-byte *before* changing anything. 100 captures
  re-recorded in main, 1 in 5.0, on that discipline.
- **Verify a crash by running it.** A grep is not a reproduction; two of mine had the wrong
  import path. The AS4 crash was confirmed by 16 red against HEAD and 17 green with the fix.
- **Writes outside the primary directory need the sandbox disabled.** An edit to `../5.0`
  fails with `PermissionError: Operation not permitted` otherwise, which reads like a file
  permission problem and is not.
- **Six things were green while measuring nothing**, each found by something outside itself:
  `test_json` reading 325 of 395 lines; a decode failure counted as a pass; the re-recording
  survey's own blind regex; `check_reload_cleanup` skipping every run; `check_exa_style`
  printing `ok` four times and exiting 0 over an empty walk; and seven of twenty-three NLRI
  families swept 600 times each with inputs their decoder rejected at byte one. Assume a green
  gate is mismeasuring until something external says otherwise. Not one of these was caught by
  the thing itself.
