# Review Findings F5–F20 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify and, where confirmed, fix the 16 remaining findings (F5–F14 important, F15–F20 minor/latent) from the 2026-08-22 full-codebase review, the same way the four critical findings were fixed: probe first, test first, neuter-check after.

**Architecture:** Each task is one finding (or one batch of same-shape findings). Each begins with a reproduction probe because the findings come from review subagents whose claims were wrong in 3 of the 4 cases already fixed. A refuted probe closes the task without a code change — that is a success, not a failure. Task 1 fixes the test runner's pipe handling first because it unblocks the encoding suite as a gate for every later task on this machine.

**Tech Stack:** Python 3.12, pytest, ruff, mypy --strict, the repo's qa/ harness.

**Spec:** The review artifact (claude.ai/code/artifact/10118c92-381e-4a72-bd9b-001caf9b9119) and the finding descriptions reproduced verbatim inside each task below — each task is self-contained; no task requires reading the artifact.

## Global Constraints

- **Probe before fixing.** Step 1 of every task reproduces the finding. If the probe refutes it, STOP: write the probe command, its output, and why it refutes the finding into your report; do not change code. Closing a finding as invalid is a valid, complete outcome.
- **TDD.** The test is written and observed to FAIL before the fix. After the fix passes, neuter the fix (invert/disable the specific check) and confirm the test goes red again, then restore. State all three observations in the report.
- **Tiger Style** (`.claude/TIGER_STYLE.md` is binding): malformed peer bytes raise `Notify` (from `exabgp.bgp.message.notification`), never IndexError/ValueError/struct.error escaping a decoder. Malformed operator config raises `ValueError` with the offending token in the message. Never `assert` on data from outside the process. Every loop bounded. Functions you write or modify stay under 70 lines. No bare `except:`; a new `except X: pass` needs a comment.
- **No `# type: ignore` in any form** — fix type errors at the source. `mypy --strict` on `src/exabgp/` must stay at 0 errors.
- Wire-data parameters are typed `Buffer` (`from exabgp.util.types import Buffer`), never changed to `bytes`.
- **Per-task gate**, run before commit, in order: `uv run ruff format src tests && uv run ruff check src tests` (clean), targeted pytest for your tests, `env exabgp_log_enable=false uv run pytest tests/unit/ tests/fuzz/ -q` (no failures), `uv run mypy src/exabgp/` (0 errors), `./qa/bin/check_tiger_style` (all `ok`, `long_function` count must not rise above 91).
- Tasks marked **[WIRE]** additionally run `./qa/bin/compat_gate` (expect `0 regressions`) and `./qa/bin/functional decoding -q` (expect 22/22). Note: the compat corpus has no BGP-LS inputs — a green compat_gate is not evidence for BGP-LS code.
- After Task 1 lands, `./qa/bin/functional encoding -q` is expected to report 40/40 on this machine, and every subsequent task keeps it there. Before Task 1, encoding reports 31/40 with [6 7 8 M U V X a b] failing for environmental reasons (8 KB pipe capacity — see `.claude/memory/functional-tests-8kb-pipe-limit.md`); that baseline is a pass.
- One commit per finding: the fix and its tests together, subject imperative (`fix: …`), body says what was wrong, what it caused, why this is the right fix. End the body with `Co-Authored-By: Claude <noreply@anthropic.com>`.
- The baseline branch already carries the four critical fixes (F1–F4) as its first commits. `AttributeCollection.parse` already contains the F2 overrun check near its top (`if length > len(data): self.add(TreatAsWithdraw()); return self`), and `unpack` caches on `negotiated.attribute_cache`. Do not undo either.
- An implementer that discovers a file materially different from what a task describes reports NEEDS_CONTEXT with what it actually found — the finding descriptions are second-hand and line numbers may drift.

---

### Task 1: F14 — the test runner never drains its subprocess pipes

**Files:**
- Modify: `qa/bin/functional` (class `Exec`, ~lines 526–600: `run()`, `collect()`)
- Test: the suite itself is the test (see steps); plus any runner self-checks found via `grep -rn 'functional' qa/bin/check_tests_run qa/bin/test_everything`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: a working local encoding gate (40/40) that every later task's Global-Constraints gate relies on.

**Finding (verbatim from review, verified this session):** `Exec.run()` spawns each test server/client with `subprocess.Popen(..., stdout=subprocess.PIPE, stderr=subprocess.PIPE)` and nothing reads those pipes until `collect()` calls `communicate()` after exit. A pipe is a fixed-size kernel buffer; on this machine new pipes are capped at 8192 bytes (user FIFO pressure past `fs.pipe-user-pages-soft`), so any test daemon logging more than that blocks in `write()`, freezing its event loop mid-session. Verified directly: `/proc/PID/wchan` = `anon_pipe_write` during a hang, socket in CLOSE-WAIT with unread keepalives. Latent even at the normal 64 KB: a chattier future test deadlocks CI the same way.

- [ ] **Step 1: Reproduce.** Run `python3 -c "import os,fcntl; r,w=os.pipe(); print(fcntl.fcntl(r,1032))"` — expect `8192` on this machine. Run `./qa/bin/functional encoding 6 -q` — expect TIMEOUT. If the pipe prints 65536 or test 6 passes, the environment changed; report NEEDS_CONTEXT rather than fixing blind.
- [ ] **Step 2: Fix — back the pipes with files.** In `Exec.run()`, replace the two `subprocess.PIPE` arguments with two unbuffered temp files (`tempfile.TemporaryFile()`), stored on the instance. In `collect()`, replace `communicate()` with: wait for the process (same 15 s alarm guard), then seek both files to 0 and read them into `self.stdout` / `self.stderr` (bytes, as before), then close the files. Keep the existing attribute names and types — downstream reporting code reads `self.stdout`/`self.stderr` as bytes. Keep `ready()` untouched. Nothing else in the file changes.
- [ ] **Step 3: Verify the fix on the failing set.** `./qa/bin/functional encoding 6 -q` → pass. Then the full suite: `./qa/bin/functional encoding -q` → `passed 40/40 (100.0%)`. If any of the nine former failures still fails, the diagnosis was incomplete: report DONE_WITH_CONCERNS with the failing IDs and their `-v` tails; do not paper over it.
- [ ] **Step 4: Verify nothing else regressed.** `./qa/bin/functional decoding -q` → 22/22. Run the Global-Constraints gate.
- [ ] **Step 5: Commit** `fix: read test daemon output through files, not undrained pipes`.

---

### Task 2: F13 + F15 + F16 — config and environment errors escape as raw tracebacks

Three same-shape defects, one batch: operator input reaching the operator as a raw Python exception instead of the intended `ValueError` with context.

**Files:**
- Modify: `src/exabgp/configuration/static/parser.py` (function `prefix()`, ~line 84)
- Modify: `src/exabgp/configuration/static/mpls.py` (functions `route_distinguisher()` ~60–82, `prefix_sid()` ~86–138)
- Modify: `src/exabgp/environment/config.py` (~lines 416–420, the `except TypeError` in `Environment.setup()`)
- Modify: `src/exabgp/configuration/process/parser.py` (function `run()`, ~line 63)
- Test: `tests/unit/test_configuration_parser_exceptions.py` (exists — add cases in its style)

**Interfaces:** none consumed, none produced.

**Findings (verbatim):** (a) `prefix()` calls `IP.pton(ip)` → `socket.inet_pton`, which raises `OSError` on `999.999.999.999`; nothing catches it, and the API/`encode` path has no catch-all. (b) `route_distinguisher()` only assigns `prefix`/`suffix` when the token contains `:`, so `rd 12345` hits `UnboundLocalError`; `prefix_sid()` only assigns `label_sid` when the first token is `[`, so `bgp-prefix-sid 300` hits `UnboundLocalError` at `int(label_sid)` outside the try. (c) The `except TypeError` in `Environment.setup()` is dead for the integer/real/umask readers, which raise `ValueError` — `exabgp_tcp_attempts=abc` produces a raw contextless traceback. (d) `run()` does `prg = tokeniser()` then `prg[0]` with no emptiness check — bare `run;` raises IndexError.

- [ ] **Step 1: Probe all four.** `./sbin/exabgp encode "route 999.999.999.999/24 next-hop 1.2.3.4"` → expect raw OSError traceback. A scratch conf with `rd 12345;` inside a static route and one with `bgp-prefix-sid 300` through `./sbin/exabgp configuration validate -nrv <file>` → expect UnboundLocalError-derived failures, not clean parse errors. `env exabgp_tcp_attempts=abc ./sbin/exabgp version` → expect raw ValueError traceback. A conf whose process section contains bare `run;` through validate → expect "string index out of range". Any probe that instead produces a clean, contextful error message closes that sub-finding — record it and skip its fix.
- [ ] **Step 2: Write the failing tests** in `test_configuration_parser_exceptions.py`, one per confirmed sub-finding, following that file's existing pattern. Each asserts `ValueError` (with the offending token in the message) and asserts the specific wrong exception does NOT escape, e.g.:

```python
def test_an_unparseable_prefix_address_is_a_configuration_error() -> None:
    with pytest.raises(ValueError, match='999.999.999.999'):
        prefix(tokeniser_returning('999.999.999.999/24'))
```

(Build `tokeniser_returning` the way the file already fakes tokenisers; read it first.) For (c), call `Environment.setup()`/the parse path directly with a bad value and expect the formatted `ValueError` naming `tcp.attempts`.
- [ ] **Step 3: Run them, confirm each fails** with the raw exception from Step 1.
- [ ] **Step 4: Fix.** (a) wrap the address construction in `except (OSError, ValueError):` → `raise ValueError(f'invalid prefix "{token}"...')` — `IPPrefixValidator._parse()` in `configuration/validator.py` already does this correctly; match it. (b) validate `separator > 0` / first-token-`[` up front and raise `ValueError` naming the token — `RouteDistinguisherValidator._parse()` (validator.py ~line 622) is the model. Check the other unguarded callers the finding names (`mvpn_sharedjoin`, `mvpn_sourcejoin`, `mvpn_sourcead`, `srv6_mup_isd`, `srv6_mup_dsd`, `srv6_mup_t1st`) — they share `route_distinguisher()`, so fixing it fixes them; confirm by probe, don't assume. (c) `except TypeError` → `except (TypeError, ValueError)`. (d) `if not prg or prg[0] != '/':` → the existing `ValueError` path.
- [ ] **Step 5: Green, neuter-check each fix, restore.** Run the gate.
- [ ] **Step 6: Commit** `fix: keep malformed configuration errors as ValueError with context`.

---

### Task 3: F5 — an unparseable flow source/destination silently widens the filter **[WIRE-adjacent: config side]**

**Files:**
- Modify: `src/exabgp/configuration/flow/parser.py` (functions `source()` ~127–146, `destination()` ~148–166)
- Test: Create `tests/unit/test_flow_match_rejects_garbage.py`

**Interfaces:** none.

**Finding (verbatim, confirmed by direct read this session):** `source()`/`destination()` are generators with three `if/elif` branches for IPv4, IPv6, IPv6-with-offset. A value matching none of them yields nothing and raises nothing, so `flow { route x { source not-an-ip; then discard; } }` parses successfully with the source match dropped — the rule matches ALL sources. A mitigation rule silently becomes a much broader one.

- [ ] **Step 1: Probe.** Craft `/tmp/flow-bad-source.conf` with a flow route whose `source` is `not-an-ip`, run `./sbin/exabgp configuration validate -nrv /tmp/flow-bad-source.conf`. Expect: validates successfully (exit 0) — that is the bug. Also probe `source 10.0.0/24;` (three dots' worth missing) and confirm which branch, if any, catches it.
- [ ] **Step 2: Failing tests.** Call `source()` / `destination()` directly with a fake tokeniser returning the garbage token; assert `ValueError` is raised (`pytest.raises(ValueError, match='not-an-ip')`). Negative space in the same file: `10.0.0.0/24`, `2001:db8::/32`, and `2001:db8::/32/64` still yield exactly one component of the right class, and a malformed-but-branch-matching value (`10.0.0.256/24`) raises rather than building a bogus component.
- [ ] **Step 3: Red.**
- [ ] **Step 4: Fix.** Add a trailing `else:`-equivalent: after the three branches, `raise ValueError(f'unrecognised flow source "{data}"' )` (and destination). Inside the branches, wrap the `int()`/`IP.pton` conversions so `10.0.0.256` and friends also become `ValueError` with the token, not OSError. Keep both functions generators (the caller iterates).
- [ ] **Step 5: Green, neuter-check, gate. Also re-run Step 1's validate — must now fail with the token named.**
- [ ] **Step 6: Commit** `fix: reject a flow source or destination the parser cannot read`.

---

### Task 4: F11 — a flow_vpn NLRI shorter than its mandatory RD parses as filter rules **[WIRE]**

**Files:**
- Modify: `src/exabgp/bgp/message/update/nlri/flow.py` (`unpack_nlri` / `_parse_rules` ~908–945, `rd` property ~887–896)
- Test: Create `tests/unit/test_flow_vpn_short_rd.py`

**Interfaces:** none.

**Finding (verbatim):** For `SAFI.flow_vpn` an 8-byte Route Distinguisher is mandatory, but the stripping code is `if self.safi in (SAFI.flow_vpn,) and len(bgp) >= 8: bgp = bgp[8:]` — a payload shorter than 8 bytes skips the strip and feeds what should have been RD bytes into the rule parser. A 3-byte payload `[0x03, 0x81, 0x06]` decodes as a valid-looking "protocol == TCP" rule with `rd = NORD`.

- [ ] **Step 1: Probe.** Drive `Flow.unpack_nlri` (or the registered NLRI entry point for flow_vpn — read `flow.py` to find the real one) with a flow_vpn NLRI whose payload is `[0x03, 0x81, 0x06]`. Expect: an accepted NLRI, no Notify. If it already raises Notify, the finding is stale — close it with the output.
- [ ] **Step 2: Failing tests.** flow_vpn payloads of length 0–7 → `pytest.raises(Notify)`. Negative space: a valid flow_vpn NLRI (8-byte RD + one component) still decodes and reports its RD; a plain `SAFI.flow` NLRI of 3 bytes is unaffected by the new check.
- [ ] **Step 3: Red.**
- [ ] **Step 4: Fix.** At the flow_vpn entry, before any rule parsing: `if len(...) < 8: raise Notify(3, 10, 'flow-vpn NLRI too short for its route distinguisher')`. Use the length the parser actually has at that point (read the code — the finding's variable names may not match).
- [ ] **Step 5: Green, neuter-check, gate + [WIRE] checks.**
- [ ] **Step 6: Commit** `fix: a flow-vpn NLRI must be long enough to carry its route distinguisher`.

---

### Task 5: F6 — Capability.klass() mutates shared class state across sessions

**Files:**
- Modify: `src/exabgp/bgp/message/open/capability/capability.py` (`klass()` ~215–223, `unpack()` ~226–228)
- Possibly modify: `src/exabgp/bgp/message/open/capability/refresh.py`, `ms.py` (readers of `self.ID`)
- Test: Create `tests/unit/test_capability_variant_isolation.py`

**Interfaces:** none.

**Finding (verbatim, confirmed by direct read this session):** `klass()` does `kls.ID = what` — a write to the class object. `RouteRefresh` is registered under both 0x02 (RFC) and 0x80 (Cisco); `MultiSession` under 0x44 and 0x83. Both read `self.ID` in `__str__`/`json()` to report the variant. One peer's OPEN carrying the Cisco code rewrites the reported variant of every established peer's capability object, process-wide. Wire encoding is unaffected (packing keys off the registry dict key).

- [ ] **Step 1: Probe.** Unpack a RouteRefresh capability as code 0x02 into instance A; then call `Capability.klass(0x80)`; assert whether `str(A)`/`A.json()` now reports Cisco. Expect: it does.
- [ ] **Step 2: Failing tests.** Instance A unpacked under 0x02 keeps reporting RFC after an unpack under 0x80 creates instance B, and B reports Cisco; same pair for MultiSession 0x44/0x83; and `Capability.klass(x)` twice in a row returns the same class object without observable state change (compare `__dict__` before/after or assert `ID` restored to its class-definition value).
- [ ] **Step 3: Red.**
- [ ] **Step 4: Fix.** Remove the `kls.ID = what` mutation from `klass()`. In `Capability.unpack()` (which knows `capability`, the code actually received), set the variant on the **instance**: `instance.ID = capability` before returning it — an instance attribute shadows the ClassVar for `self.ID` reads. Check every reader of `.ID` on capability classes (`grep -n '\.ID' src/exabgp/bgp/message/open/capability/*.py`) to confirm none relies on the class-level mutation; if one does, that call site gets the instance value instead.
- [ ] **Step 5: Green, neuter-check, gate.**
- [ ] **Step 6: Commit** `fix: record a capability's wire variant on the instance, not the shared class`.

---

### Task 6: F7 — MultiSession.unpack_capability ignores its payload, so the negotiation check cannot fire

**Files:**
- Modify: `src/exabgp/bgp/message/open/capability/ms.py` (`unpack_capability` ~51–57)
- Test: Create `tests/unit/test_multisession_negotiation.py`

**Interfaces:**
- Consumes: Task 5's instance-level `ID` convention if both touch `ms.py` — Task 5 lands first; read `ms.py` as it then stands.

**Finding (verbatim):** `unpack_capability` ignores `data` entirely, so `recv_capa[MULTISESSION]` is always an empty list; in `negotiated.py:198–206` the empty set is replaced by the hardcoded default, which always equals the sent set, so the mismatch branch (`self.multisession = (2, 8, ...)`) is structurally dead. The session proceeds as if the check passed without comparing real peer data.

**This task carries a behavioral decision.** Making the check live means a peer advertising multisession with a different session-id set will now be refused (Notify 2,8) where before it was silently accepted. That is what the dead code plainly intended, and ExaBGP does not otherwise support multisession — but it is a behavior change for any peer currently sending mismatched multisession capabilities. The fix is correct; the report must FLAG the behavior change prominently so the controller can ledger it.

- [ ] **Step 1: Probe.** Read `ms.py` and `negotiated.py:190–210` as they stand. Feed `MultiSession.unpack_capability` a payload of one capability code byte and confirm the instance's list stays empty. Trace `negotiated.multisession` for a mismatched payload — confirm it stays `False`.
- [ ] **Step 2: Failing tests.** (a) unpacking a payload of capability codes populates the instance list; (b) `Negotiated.multisession` becomes the `(2, 8, …)` refusal tuple when the peer's session-id set differs from ours; (c) negative space: no multisession capability at all → `multisession` stays `False` and nothing new fires; a peer echoing exactly our set → accepted.
- [ ] **Step 3: Red.**
- [ ] **Step 4: Fix.** Make `unpack_capability` consume `data`: each byte is a capability code; length-check before each read (peer bytes → malformed payload raises `Notify(2, 0, ...)` or is handled per the file's existing style for capability payloads — match `graceful.py`/`addpath.py`'s pattern of bounded strict consumption). Append codes to the instance list.
- [ ] **Step 5: Green, neuter-check, gate.**
- [ ] **Step 6: Commit** `fix: read the multisession capability payload so the session-id check can compare it`.

---

### Task 7: F8 — AttributeCollection.parse recurses once per attribute on peer data **[WIRE]**

**Files:**
- Modify: `src/exabgp/bgp/message/update/attribute/collection.py` (`parse()` ~404–560)
- Test: Create `tests/unit/test_attribute_parse_iterative.py`

**Interfaces:**
- Consumes: the F2 overrun check and F3 per-session cache already in this function/file — preserve both; the overrun check sits at the top of `parse()`.

**Finding (verbatim, structure confirmed by direct read this session):** every branch of `parse()` ends `return self.parse(left, negotiated)` — one recursion level per attribute, minimum 3 bytes each, so a single 4096-byte UPDATE can exceed Python's 1000-frame default. Today a broad `except Exception` in `reactor/protocol.py` converts the `RecursionError` to a generic Notify, so the cost is a wrong-cause session reset rather than a crash — and the tree's own rule is "no recursion on peer data". All the recursive calls are tail calls.

- [ ] **Step 1: Probe.** Build an attribute section of ~1200 unknown non-transitive attributes (3 bytes each: flag 0x80, aid 0xEF, len 0) — ~3600 bytes, inside the 4096 message bound — and feed it to `AttributeCollection().parse(section, negotiated_mock)`. Expect `RecursionError`. If Python's limit has been raised somewhere or the structure changed, report what you find.
- [ ] **Step 2: Failing test.** The Step-1 payload parses without exception and returns a collection (the unknown non-transitive attributes are skipped, so it should be empty of them). A second case mixing ~1100 unknowns with one real ORIGIN asserts ORIGIN survives.
- [ ] **Step 3: Red** (fails with RecursionError).
- [ ] **Step 4: Fix.** Convert to iteration: wrap the body in `while True:`, replace every `return self.parse(left, negotiated)` with `data = left` + `continue`, keep every other `return`/`raise` exactly as is. The F2 overrun check runs each iteration (it already sits after the per-attribute header reads — keep it there). Function stays under 70 lines *modified-function rule applies to what you touch*: `parse()` is grandfathered long; do not grow it — the mechanical rewrite should not add lines beyond the loop frame. Preserve comment text.
- [ ] **Step 5: Green. Neuter-check is the probe: re-introduce one recursive return, confirm the new test goes red, restore.** Full gate + [WIRE] checks. The existing 5174-test suite and `tests/fuzz/` are the regression net for the rewrite — all must stay green.
- [ ] **Step 6: Commit** `fix: parse path attributes iteratively rather than one stack frame per attribute`.

---

### Task 8: F18 + F20 — pack-guard mismatch, and the missing-mandatory-attribute question **[WIRE]**

**Files:**
- Modify: `src/exabgp/bgp/message/update/attribute/collection.py` (`INTERNAL` tuple ~78–83, `pack_attribute` ~314)
- Possibly modify: `src/exabgp/bgp/message/update/collection.py` (post-parse validation) — only if F20's probe confirms
- Test: Create `tests/unit/test_internal_attribute_packing.py`; extend it for F20 if confirmed

**Interfaces:** consumes Task 7's iterative `parse()` (land after it).

**F18 (verbatim):** `pack_attribute` skips codes in the `INTERNAL` tuple, but `Discard` (0xFFFE) and `TreatAsWithdraw` (0xFFFF) are not in it; both set `NO_GENERATION`, which is the guard text/JSON generation uses. A collection containing a `Discard` that reaches `pack_attribute` raises `NotImplementedError`. Two guards that should agree, don't. No live path re-packs a received collection today — latent.

**F20 (from this session's F2 work, probe-gated):** an UPDATE whose attribute section is self-consistent but omits well-known mandatory attributes was accepted. CAUTION, this was observed **without NLRI in the message**: RFC 4271 §6.3 makes ORIGIN/AS_PATH/NEXT_HOP mandatory only when the UPDATE carries NLRI, and RFC 7606 §3 prescribes treat-as-withdraw for a missing mandatory attribute in that case. The finding is only real if an UPDATE **with NLRI** and no ORIGIN is accepted as an announce.

- [ ] **Step 1: Probe F18.** Build a collection: `c = AttributeCollection(); c.add(Discard())`, call `c.pack_attribute(negotiated_mock)`. Expect `NotImplementedError`. Probe F20: build a full UPDATE message (wire bytes) carrying one IPv4 NLRI (e.g. `20 0A 00 00 01` appended after the attribute section) whose attributes are only LOCAL_PREF — no ORIGIN, no AS_PATH, no NEXT_HOP — and run it through `Update.unpack_message(...).parse(negotiated)`. Record precisely what comes back: announced routes? treat-as-withdraw? Notify? **If it already treat-as-withdraws or refuses, F20 is closed** — write the evidence.
- [ ] **Step 2: Failing tests.** F18: packing a collection containing `Discard()` / `TreatAsWithdraw()` silently skips them — output equals packing the same collection without them; every member of the current `INTERNAL` tuple sets `NO_GENERATION` (assert it, so the two guards provably coincide before you merge them). F20 (only if confirmed): an UPDATE with NLRI and no ORIGIN yields treat-as-withdraw, not an announce; negative space: the same UPDATE with ORIGIN/AS_PATH/NEXT_HOP present announces; an attributes-free UPDATE with no NLRI still parses (EOR handling unaffected).
- [ ] **Step 3: Red.**
- [ ] **Step 4: Fix.** F18: change `pack_attribute`'s skip condition from `aid in AttributeCollection.INTERNAL` to the class's `NO_GENERATION` flag (look the class up via `Attribute.klass_by_id(aid)` the way `parse()` does, or check the instance), so one flag governs both packing and generation. Verify no INTERNAL member relies on being packed. F20 (if confirmed): after attribute parsing, where the update knows it carries v4 NLRI announcements (read `update/collection.py`'s parse flow to find the seam — likely where announces are assembled), missing any of ORIGIN/AS_PATH/NEXT_HOP adds `TreatAsWithdraw()` per RFC 7606 §3. Keep the check off the EOR and withdraw-only paths.
- [ ] **Step 5: Green, neuter-check each, full gate + [WIRE] checks.**
- [ ] **Step 6: Commit** — one commit per confirmed finding (`fix: skip internal pseudo-attributes by their own flag when packing`; `fix: treat an announce missing a mandatory attribute as withdraw` if F20 confirmed).

---

### Task 9: F12 — connection_attempts counts forever, so tcp.attempts eventually strands a healthy peer

**Files:**
- Modify: `src/exabgp/reactor/peer/peer.py` (`connection_attempts` init ~166, increment ~446, `can_reconnect` ~289–293, and the establishment transition)
- Modify: `.claude/exabgp/ENVIRONMENT_VARIABLES.md` (the `tcp.attempts` entry — align the text with the fixed semantics)
- Test: Create `tests/unit/reactor/peer/test_connection_attempts.py`

**Interfaces:** none.

**Finding (verbatim):** `connection_attempts` increments on every attempt and is never reset; `can_reconnect()` compares the lifetime total against `tcp.attempts`. With a nonzero setting, a healthy peer that reconnects occasionally over months accumulates to the ceiling and `stop()` permanently disables it (`_restart = False`). The docs describe a consecutive-failure counter. Default 0 (unlimited) is unaffected.

- [ ] **Step 1: Probe.** `grep -n 'connection_attempts' src/exabgp/reactor/peer/peer.py` — confirm: initialized once, incremented in `_connect()`, never assigned 0 elsewhere. Find the point where the session reaches ESTABLISHED (the FSM change or the point after OPEN/KEEPALIVE exchange in `_run`/`_establish` — read the file; do not trust these names).
- [ ] **Step 2: Failing test.** Unit-level on `Peer` is heavy; test the semantics instead: construct the smallest `Peer` the existing `tests/unit/reactor/peer/` fixtures allow (read that directory first — reuse its fakes), set `max_connection_attempts = 3`, set `connection_attempts = 3`, assert `can_reconnect()` is False; then invoke the establishment-reset seam you found in Step 1 (directly if it is a method, else extract one — smallest coherent change) and assert `can_reconnect()` is True again. If no usable fixture exists, a focused test that calls the new reset method and `can_reconnect()` on a minimally-stubbed Peer is acceptable; say so in the report.
- [ ] **Step 3: Red** (no reset exists, so the second assertion fails).
- [ ] **Step 4: Fix.** Reset `self.connection_attempts = 0` at the point the session is confirmed ESTABLISHED (not merely connected — a connect that dies during OPEN should still count). One line plus, if needed, one small method. Update `ENVIRONMENT_VARIABLES.md`'s `tcp.attempts` text to say "consecutive failed attempts; resets when a session establishes".
- [ ] **Step 5: Green, neuter-check, gate.**
- [ ] **Step 6: Commit** `fix: reset the connection attempt counter when a session establishes`.

---

### Task 10: F9 — exabgp run exits 0 on daemon-side errors

**Files:**
- Modify: `src/exabgp/application/run.py` (`send_command_socket` ~160–200, `cmdline_socket` ~410–420, `cmdline_pipe` ~555–590, `cmdline_batch`)
- Test: Create `tests/unit/application/test_run_exit_codes.py` (check `tests/unit/application/` for existing fakes first)

**Interfaces:** none.

**Finding (verbatim):** with `return_output=False`, all three failure shapes — daemon replies `error`, daemon replies shutdown, daemon closes mid-response — print to stderr and fall through to unconditional `sys.exit(0)`. `cmdline_batch` counts 0 errors when every command was rejected. The `sock.timeout` path is intentionally silent when `exabgp.api.ack` is false — leave it be.

- [ ] **Step 1: Probe.** Read `run.py`'s actual structure (the line numbers above are the reviewer's). Confirm: `send_command_socket(..., return_output=False)`'s error/shutdown/early-close paths do not raise and the callers exit 0 unconditionally. If the code distinguishes them already, close the finding with evidence.
- [ ] **Step 2: Failing tests.** Drive `send_command_socket` against a fake socket (an in-process `socketpair` or a stub object with `recv` scripted — match whatever `tests/unit/application/` already does) for four scripted conversations: clean `done`, `error` reply, `shutdown` reply, connection closed early. Assert the function's return value (or raised exception — pick ONE contract and state it) distinguishes success from all three failures. Then assert `cmdline_socket` maps failure to `SystemExit(1)` and success to `SystemExit(0)` (use `pytest.raises(SystemExit)` and check `.value.code`). The timeout-with-ack-disabled path stays success — test it so the fix doesn't break it.
- [ ] **Step 3: Red.**
- [ ] **Step 4: Fix.** Give `send_command_socket` (and the pipe equivalent) a boolean return that is False on error/shutdown/early-close even when `return_output=False`; callers `sys.exit(0 if ok else 1)`; `cmdline_batch` counts `not ok` as errors. Do not change the printed output.
- [ ] **Step 5: Green, neuter-check, gate.**
- [ ] **Step 6: Commit** `fix: exabgp run exits non-zero when the daemon rejects the command`.

---

### Task 11: F17 — decode_to_api_command hides its own failures

**Files:**
- Modify: `src/exabgp/configuration/command.py` (~line 838, `except Exception: return []` in `decode_to_api_command()`)
- Test: Create `tests/unit/test_decode_to_api_command_errors.py`

**Interfaces:** none.

**Finding (verbatim):** the blanket `except Exception: return []` makes a formatting crash indistinguishable from "no commands", defeating the round-trip testing the function exists for.

- [ ] **Step 1: Probe.** Read the function and its callers (`grep -rn 'decode_to_api_command' src/ qa/`). Confirm the empty-list ambiguity and identify what callers do with `[]`.
- [ ] **Step 2: Failing test.** Monkeypatch one of the formatters it calls to raise `RuntimeError('boom')`; assert the exception propagates (or, if a caller genuinely needs the no-throw contract — say which, from Step 1 — assert a logged error plus a sentinel distinct from `[]`). Negative space: a valid input still returns its commands.
- [ ] **Step 3: Red.**
- [ ] **Step 4: Fix** per the Step-2 contract: prefer removing the blanket except so failures surface in the round-trip tooling; narrow to specific expected exceptions only if Step 1 showed a caller that must not throw, with a comment saying why.
- [ ] **Step 5: Green, neuter-check, gate.**
- [ ] **Step 6: Commit** `fix: let decode_to_api_command failures surface instead of returning an empty list`.

---

### Task 12: F19 — qualifier unpack helpers slice without length checks **[WIRE]**

**Files:**
- Modify: `src/exabgp/bgp/message/update/nlri/qualifier/` (`esi.py`, `etag.py`, `labels.py`, `mac.py`, `path.py`, `rd.py` — whichever `unpack_*` classmethods slice unchecked)
- Test: Create `tests/unit/test_qualifier_unpack_bounds.py`

**Interfaces:** none.

**Finding (verbatim):** the `unpack_*` classmethods slice without length checks, relying on `__init__` raising `ValueError` on a wrong-size buffer. Every current caller validates length first, so it is not reachable with attacker bytes today — a landmine for the next caller, not a live defect.

- [ ] **Step 1: Probe.** For each file, call its `unpack_*` with an empty and a one-byte buffer. Record what escapes (ValueError? silent short object?). Also re-verify the "all callers check first" claim: `grep -rn 'unpack_esi\|unpack_etag\|unpack_label\|unpack_mac\|unpack_path\|unpack_rd' src/` and confirm each call site's guard — if any caller does NOT guard, say so in the report; that caller is a live [WIRE] bug and its fix joins this task.
- [ ] **Step 2: Failing tests.** Each helper, short buffer → `pytest.raises(Notify)`. Negative space: exact-size buffers still construct objects equal to the ones the existing tests build.
- [ ] **Step 3: Red.**
- [ ] **Step 4: Fix.** In each `unpack_*`: length check first, `raise Notify(3, 10, '<qualifier> requires N bytes, got M')`, then slice. Do not touch `__init__` — configuration-side construction keeps its `ValueError` contract.
- [ ] **Step 5: Green, neuter-check per helper, full gate + [WIRE] checks + `tests/fuzz/` green.**
- [ ] **Step 6: Commit** `fix: bound every qualifier unpack before it slices`.

---

### Task 13: F10 — the CLI's retry-on-reconnect deadlocks on its own reader thread

**Files:**
- Modify: `src/exabgp/cli/persistent_connection.py` (`_reconnect` ~347–360, `send_command` ~603–649, `_read_loop` routing ~400, ~465, `_send_ping` guard ~505)
- Test: Create `tests/unit/cli/test_reconnect_retry.py` (check `tests/unit/cli/` and `tests/unit/test_cli_transport.py` for existing fakes)

**Interfaces:** none. Last task: highest-judgment change, isolated from the rest.

**Finding (verbatim):** `_read_loop` (reader thread) detects a closed socket and calls `_reconnect()`, which — if a command was in flight — synchronously calls `send_command(last_cmd, is_retry=True)` **on the reader thread**. `send_command` blocks on `pending_responses.get(timeout=5)`, but the only thread that fills that queue is the reader thread itself, several frames up. The nested call therefore always times out, delivers `'Error: Timeout waiting for response'` to the original caller even when the daemon answered, and its `finally` clobbers `command_in_progress`/`pending_user_command` for the still-waiting outer call; its queue-flush can also discard a response that arrived just before the disconnect.

- [ ] **Step 1: Probe.** Read the file end to end first — threading claims are the least trustworthy kind of second-hand finding. Confirm: which thread runs `_reconnect`, what `send_command` blocks on, who fills `pending_responses`. Write the confirmed call-chain into the report before touching anything. If the structure differs materially, NEEDS_CONTEXT.
- [ ] **Step 2: Failing test.** With a scripted fake socket pair: start a command from the main thread, close the daemon side mid-flight, script the reconnect to succeed and the daemon to answer the resent command promptly. Assert the caller receives the real response, not a timeout string, within a bound (< the 5 s nested timeout — a passing pre-fix run would take 5+ s, so bound the assert at ~3 s). Second test: after the recovery, `command_in_progress`/`pending_user_command` are both False and a subsequent command works.
- [ ] **Step 3: Red** (times out / wrong response today).
- [ ] **Step 4: Fix.** The reader thread must never wait on itself: in `_reconnect`, replace the nested `send_command(...)` with a bytes-level resend (write the command to the new socket, restore the in-flight bookkeeping) and return, letting the normal `_read_loop` iteration route the response to the original waiter. Remove the nested call's state-clobber and queue-flush from this path. Keep the no-command-in-flight reconnect behavior unchanged.
- [ ] **Step 5: Green, neuter-check, gate. Run the new tests 20× (`pytest ... --count` is unavailable; loop in shell) to shake out timing flake — threading tests that pass once are not evidence.**
- [ ] **Step 6: Commit** `fix: resend a mid-flight command after reconnect without waiting on the reader thread`.

---

## Verification (whole plan)

After the final task: `./qa/bin/test_everything` end to end — with Task 1 landed it should pass all steps on this machine for the first time. Then `./qa/bin/functional encoding --stress 10` on tests 6 and a (formerly pipe-blocked, exercising F1's read path under repetition) — the stress verification still owed from the F1 fix.

## Progress

Tracked in the SDD ledger (`.superpowers/sdd/<plan-basename>/progress.md`), not here.

## Failures

Append here only what outlives the SDD workspace: findings closed as invalid (with probe evidence), behavior changes ledgered (Task 6), contracts changed (Task 10's return convention).

## Blockers

None known at write time.

## Resume Point

If resuming without the SDD ledger: `git log --oneline` on the feature branch; one commit per finding in task order.
