# TIGER STYLE (Python, ExaBGP)

**Status:** MANDATORY. Applies to every line you write or touch in this repository.
**When to read:** Before writing code. Again before opening a commit.
**Enforced by:** `./qa/bin/check_tiger_style`, run as the `tiger-style` step of `./qa/bin/test_everything`.

Adapted from [TigerBeetle's TIGER_STYLE](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/TIGER_STYLE.md),
which in turn adapts NASA's *Power of Ten: Rules for Developing Safety Critical Code*. The rules below
are the Python and ExaBGP translation, not a copy: Python has no compiler to lean on, no static
allocation, and `assert` disappears under `-O`, so several rules land differently.

---

## Why

ExaBGP parses bytes sent by peers on the public internet and runs unattended for months at a time.
Two failure modes matter more than anything else:

1. **A crash is an outage.** A traceback out of a decoder takes the session, and often the process,
   with it. Every peer on the box pays for one malformed byte.
2. **A wrong route is worse than no route.** Silently accepting a malformed NLRI, or re-encoding it
   into something the peer never sent, puts wrong state into someone's network.

So the order is: **safety, then performance, then developer experience.** Never trade the first for
the second. The third is what makes the first two survive contact with next year.

> "Simplicity is prerequisite for reliability." - Dijkstra

---

## 1. Safety

### 1.1 Never trust the wire

Peer supplied bytes are hostile until proven otherwise.

- **Check the length before every read.** Indexing, slicing into a struct, `unpack`, all of it.
  A decoder that reaches past its payload is a bug even if Python happens to raise.
- **Malformed input raises `Notify`, never a Python exception.** `IndexError`, `struct.error`,
  `ValueError`, `UnicodeDecodeError` and `AssertionError` escaping a decoder are all the same bug:
  the session should have been closed with a NOTIFICATION and the peer told why.
- **Validate once, at the boundary.** After the decoder returns, the object is trusted by the RIB,
  by the API, by everything downstream. That is only true if the decoder checked everything.
- **What a decoder accepts, it must be able to re-encode.** If `pack(unpack(x))` cannot be decoded
  again, or decodes to something else, the NLRI stored on one side of the process disagrees with the
  wire on the other. That mismatch surfaces later, in JSON output, where nobody can trace it back to
  the peer who caused it.
- **A decoded object must survive `json()`, `str()`, `index()` and `hash()`.** Lazy accessors that
  re-derive structure from the packed bytes must use what the decoder recorded, not re-guess it.

```python
# WRONG: reads before checking, and lets the wire pick the exception
mask = data[0]
rd = RouteDistinguisher(bytes(data[:8]))

# RIGHT: check, then read, and say what was wrong
if not data:
    raise Notify(3, 10, 'not enough data to extract the mask of the NLRI')
mask = data[0]
if len(data) < rd_size:
    raise Notify(3, 10, 'not enough data to extract the route distinguisher of the NLRI')
```

The property tests in `tests/fuzz/test_nlri_decoder_properties.py` hold every registered decoder to
this rule. New decoders are covered the day they are registered. Falsifying examples become plain
regression tests in `tests/unit/test_nlri_wire_bounds.py`.

They run derandomized as part of `test_everything`, so the gate fails on what the code does rather
than on which examples Hypothesis drew. Hunting for new ones is a separate, deeper run:
`./qa/bin/fuzz_hunt`. Run it after touching a decoder.

### 1.2 Assert your invariants, never your input

Python strips `assert` under `-O`. An assertion is therefore a statement about *our* code, checked
during development and during every test run, and never a validation of anything that arrives from
outside the process.

| Source of the problem | What to raise |
|---|---|
| Peer supplied bytes | `Notify` |
| Operator configuration | `ValueError` with the parser context |
| API or CLI client input | An error response, never an exception through the reactor |
| Our own invariant broken | `assert`, or an explicit `raise RuntimeError` on a path that must hold under `-O` |

**Assert liberally.** An invariant which is only in your head is one refactor away from being false.
Write it down where the code can check it:

- **Preconditions.** What the function needs from its caller. `assert self._label_size % 3 == 0`.
- **Postconditions.** What the function promises. `assert len(packed) == self.LENGTH`.
- **The negative space.** Not only that a value is what you expect, but that it is not what it must
  never be. An offset which must stay inside the buffer, a counter which must never go negative, a
  cache which must never hold a mutable NLRI.
- **Structural agreement.** When two representations of the same thing exist, assert they agree. The
  label stack bug lived exactly there: the decoder and the accessors disagreed, and nothing said so.

Two assertions in a non-trivial function is a reasonable habit, not a quota. An assertion which
cannot fail is noise, and an assertion which restates the line above it is worse.

```python
# WRONG: the peer decides whether this holds, and -O deletes the check
assert len(data) >= 8

# RIGHT: the peer decides, so the peer gets told
if len(data) < 8:
    raise Notify(3, 10, 'not enough data to extract the route distinguisher of the NLRI')

# RIGHT: we decide this, and it must hold for the slice below to mean anything
assert self._label_size % 3 == 0, 'a label stack is made of three byte labels'
```

ExaBGP is not run with `-O`, and must not be: the assertions are part of how the daemon fails
loudly in testing rather than quietly in production. Nothing may *depend* on them running.

### 1.3 Bound everything

Anything a peer, an API client or a configuration file can grow, has a limit, a name, and a defined
behaviour when it is reached.

- **Every loop has a bound.** A parsing loop must strictly consume input each iteration. A `while`
  that depends on remote data needs a counter, a size cap or a deadline.
- **Every buffer has a maximum, as a named constant.** `MAX_COMMAND_SIZE`, `MAX_GROUP_COMMANDS`,
  `MAX_GROUP_BYTES` are the pattern. Count **bytes**, not entries, when bytes are what grows.
- **Say what happens on excess.** Drop the input, close the connection, kill the helper. Never let
  the buffer keep growing while a check that never fires watches the wrong number.
- **State is cleared on disconnect.** Per client state that outlives its client is a leak with a
  slow fuse.
- **No recursion on peer data.** Recursion elsewhere needs a depth that is provably bounded.

### 1.4 Handle every error explicitly

- No bare `except:`. Ever. The checker fails the build on the first one.
- `except SomeError: pass` needs a comment saying why the error is expected and why swallowing it is
  safe. The ones already in the tree are debt: do not add to them.
- Convert at the boundary each error belongs to. A `ValueError` from `ipaddress` inside a decoder
  becomes a `Notify`. A `ValueError` inside the configuration parser gains the line and the token.
- Never report success you have not verified. A function that returns `True` on a path it did not
  execute is lying to its caller.

### 1.5 Keep functions short

**70 lines is the limit for any function you write or modify. 40 is the target.** A function longer
than that is doing more than one thing and hides the seam where the bug lives. Split at the seam,
not at an arbitrary line count.

The existing long functions are grandfathered by the ratchet in the checker. Touching one is the
moment to shorten it, not the moment to add to it.

### 1.6 Smallest possible scope

- Declare a variable where it is used, not at the top of the function.
- Module level mutable state that remote input can grow is the shape of every resource exhaustion
  bug we have had. If it must exist, it is capped and cleared (see `reactor/api/command/group.py`).
- Prefer immutable objects. NLRI and attributes are immutable by design: see
  `.claude/exabgp/WIRE_SEMANTIC_SEPARATION.md`.

### 1.7 Zero warnings

`ruff format`, `ruff check` and `mypy --strict` clean, every commit, no exceptions. `# type: ignore`
is prohibited without explicit approval (`qa/bin/check_type_ignores` enforces it). A warning you have
decided to live with is a warning everybody else learns to skip past.

---

## 2. Performance

Design for the bottleneck before writing the code, not after profiling reveals you built the wrong
thing. Napkin math first: the costs, worst to best, are **network, then disk, then memory, then CPU**.

- **Batch.** One syscall for many messages beats many syscalls. One UPDATE carrying many NLRI beats
  many UPDATEs.
- **Do not copy the wire.** Decoders take `Buffer` (PEP 688) and slice `memoryview`, they do not
  build `bytes` per field. See `.claude/exabgp/PEP688_BUFFER_PROTOCOL.md`. Never change a
  `data: Buffer` parameter back to `data: bytes`.
- **Pack once.** Wire bytes are stored, not rebuilt on every access. See
  `.claude/exabgp/PACKED_BYTES_FIRST_PATTERN.md`.
- **Do not allocate inside a decode loop** when a slice will do.
- **Measure.** `pytest-benchmark` for micro work, `./qa/bin/functional encoding --stress N` for the
  whole path. A performance claim without a number is an opinion.

---

## 3. Developer experience

### Naming

- **Units belong in the name.** `size_bytes`, `timeout_ms`, `interval_seconds`. A bare `size` invites
  the caller to guess.
- **`_at` for an absolute time, `_ms`/`_seconds` for a duration, `count` for a count, `index` for a
  position.**
- **No abbreviations**, except the BGP vocabulary this codebase speaks: `nlri`, `afi`, `safi`, `rd`,
  `rt`, `esi`, `asn`. If a newcomer to the file cannot expand it, write it out.
- **Booleans are positive.** `has_labels`, not `no_labels`. `enabled`, not `disabled`.
- **Say what it is, not what it does to you.** `_label_size` beats `_label_helper`.

### Comments

Comments are sentences, with a capital and a full stop, and they explain **why**. The code already
says what. A comment that repeats the line below it is noise that will go stale and mislead.

Write down the reasoning that is not visible: the RFC that mandates the check, the peer behaviour
that forced the workaround, the reason the obvious approach does not work.

### Commits

- **One change per commit.** A fix, its test, and nothing else.
- **The subject is imperative and specific**: `fix: bound the mask and the payload of a unicast NLRI`.
- **The body says what was wrong, what it caused, and why this is the right fix.** Future you is
  reading it during an incident.
- **A bug fix arrives with the test that fails without it.** Write the test first, watch it fail,
  then fix. A fix without that evidence is a guess.
- **Never commit or push without being asked.** See `.claude/GIT_VERIFICATION_PROTOCOL.md`.

### Zero technical debt

Do it properly the first time. The cost of a shortcut is paid by whoever debugs it at 3am with a
network down. If something must be deferred, it is written down in `plan/`, with what is missing and
why, not left as a silent gap.

---

## 4. Where the codebase already shows this

| Rule | Look at |
|---|---|
| Check before you read | `bgp/message/update/nlri/inet.py`, `ipvpn.py`, `cidr.py` |
| Notify, not Python exceptions | `bgp/message/update/nlri/rtc.py`, `vpls.py`, `bgpls/nlri.py` |
| Record structure, do not re-guess it | `_label_size` in `bgp/message/update/nlri/label.py` |
| Named caps on remote input | `MAX_COMMAND_SIZE` in `reactor/api/processes.py`, `MAX_GROUP_BYTES` in `reactor/api/command/group.py` |
| Strict validation of operator secrets | `util/psk.py` |
| Invariants written down where the code checks them | `_label_end_offset` in `bgp/message/update/nlri/label.py` |
| Property tests over a whole registry | `tests/fuzz/test_nlri_decoder_properties.py` |

---

## 5. Enforcement

Mechanical, in `./qa/bin/check_tiger_style` (part of `./qa/bin/test_everything`):

| Check | Rule | How it fails |
|---|---|---|
| `bare_except` | 1.4 | Any occurrence fails |
| `input_assert` | 1.2 | Any occurrence fails: an `assert` which tests a wire data parameter (`data`, `bgp`, `payload`, `raw`, `packed`, `buffer`) |
| `long_function` | 1.5 | Fails if the count rises above the baseline |
| `silent_except` | 1.4 | Fails if the count rises above the baseline |

Assertions about our own state are not counted: they are the point of rule 1.2, not a violation of
it. Only the ones which validate the bytes a function was handed are.

The baseline lives in `qa/tiger_style.json` and only ever goes **down**. Lower it with
`./qa/bin/check_tiger_style --update-baseline` after removing violations, and say so in the commit.

Everything else is a review responsibility.

### A sweep is evidence only once it has gone red

A test suite, a fuzz run or a corpus which reports no problem has said one of two things,
and they look identical: *the code is correct*, or *the code never ran*. Four times in one
piece of work the second was true and was read as the first:

| what was measured | why it was empty |
|---|---|
| every registered attribute decoder | the registries fill by import side effect, and the module imported only what it named |
| every BGP-LS TLV, no backstop needed | a catch-all converted every escape, so a TLV with no length checks looked like one with them |
| tunnel encapsulation, no problem found | RFC 9012 gives a sub-TLV type of 128 or more a two byte length; the probe wrote one, so nothing above 127 was framed |
| every NLRI family, no regression | VPLS carries a two byte length prefix and the corpus emitted one byte, so that family was never decoded |

Each of those numbers was reported, believed, and repeated to somebody else before the hole
was found. None of them was found by reading the code.

**So: before a green sweep is evidence of anything, break the thing it is watching and
require it to fail.** Revert the fix, neuter the comparison, delete the check, and re-run.
If it stays green, it is measuring nothing and the number is worse than useless, because it
reads as coverage.

This applies to a test as much as to a sweep. `./qa/bin/check_tiger_style` cannot tell you
whether a test asserts anything: three tests guarding the API command size cap read the
source file as *text* and asserted the constant's name appeared in it, and disabling all
three comparisons left the whole suite green.

The mechanical parts of this are `tests/fuzz/test_decoder_coverage.py`, which fails when a
registered decoder is never entered, and `qa/bin/compat_gate`, which fails when this tree
refuses something the last release accepts. Neither replaces the rule.

### Mutation testing

`./qa/bin/mutmut_run` changes the meaning of the validation code, one edit at a time, and reports
the edits the test suite did not notice. Coverage says a line ran; mutation testing says a line is
defended. It is not part of `test_everything` (it takes a long time), it is what you run after
writing the tests for a fix, on the module you touched:

```bash
./qa/bin/mutmut_run exabgp.bgp.message.update.nlri.inet   # one module
./qa/bin/mutmut_run --results                             # what survived
./qa/bin/mutmut_run --show <mutant>                       # the diff of one survivor
```

A survivor is a question. Either a test is missing, or the edit changed something nobody depends
on, an error message or a log line, which is a fine reason to leave it alone. The modules under
test are listed in `[tool.mutmut]` in `pyproject.toml`: add the module you are hardening.

## 6. Review checklist

- [ ] Every read from wire data is preceded by a length check
- [ ] Malformed peer input raises `Notify`, malformed configuration raises `ValueError` with context
- [ ] No `assert` on anything that came from outside the process
- [ ] Every new loop is bounded, every new buffer is capped by a named constant and cleared on disconnect
- [ ] No new `except X: pass` without a comment justifying it
- [ ] New and modified functions are under 70 lines
- [ ] Names carry their units, booleans are positive, no new abbreviations
- [ ] Comments explain why, not what
- [ ] The fix has a test that fails without it
- [ ] `./qa/bin/test_everything` passes, including `tiger-style`

---

**See also:** `.claude/CODING_STANDARDS.md` (Python and API rules), `.claude/ESSENTIAL_PROTOCOLS.md`
(session rules), `doc/RFC_WIRE_FORMAT_REFERENCE.md` (what the wire actually says).
