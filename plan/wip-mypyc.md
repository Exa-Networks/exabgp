# Compile the hot path with mypyc

🔄 **Status:** Active
**Created:** 2026-09-28

---

## Goal

Make UPDATE parsing, NLRI and attribute handling and the RIB faster by compiling
them with mypyc, while ExaBGP stays installable and runnable as pure Python.

mypyc is chosen over Cython because the code already passes `mypy --strict` with no
`type: ignore`. mypyc turns those annotations into C, where Cython only gains much
once the hot code is rewritten with `cdef` types in a second dialect.

The compiled build is an optional extra. The pure-Python package stays the reference,
keeps zero runtime dependencies, and every test must pass on both.

---

## 1. Measured state, 2026-09-28

mypyc (latest release, Python 3.12) was run on a scratch copy of
`exabgp/bgp`, `exabgp/protocol` and `exabgp/util`. The compile took 10 seconds and
stopped with 184 errors before generating any C:

| Count | Error | Cause |
|---|---|---|
| 155 | `Non-extension classes may not inherit from extension classes` | A class with a class decorator (other than a dataclass) is compiled as an ordinary Python class, which cannot inherit from a compiled one. The source has 204 decorated classes, for example `@Message.register`. |
| 26 | `Inheriting from most builtin types is unimplemented` | Classes built on `int`, `list` or `str` |
| 3 | `Type of X is incompatible with definition in class Y` | A subclass redefines a `ClassVar` with another type, for example `bgp/message/scheduling.py:88` |

### Registry decorators

| Decorator | Classes |
|---|---|
| `@LinkState.register_lsid` | 45 |
| `@ExtendedCommunity.register_subtype` | 24 |
| `@NLRI.register` | 23 |
| `@Attribute.register` | 23 |
| `@ParseAnnounce.register_family` | 20 (configuration, not compiled at first) |
| `@Capability.register` | 17 |
| `@SubTLV.register` | 8 |
| `@Message.register` | 6 |
| others (EVPN, BGPLS, PrefixSid, MUP, MVPN, PMSI, ParseStatic) | 25 |

### Classes built on a builtin type

| Base | Classes |
|---|---|
| `int` | `AFI`, `SAFI` (`protocol/family.py`), `BaseValue` and every `Resource` below it, including `ASN` (`protocol/resource.py`), `Version`, `HoldTime`, `CapabilityCode`, `Parameter`, `Type` (operational), `Reserved` (refresh), `_MessageCode`, `_integer` (`util/enumeration.py`) |
| `list[ASN]` | `SET`, `SEQUENCE`, `CONFED_SEQUENCE`, `CONFED_SET` (`attribute/aspath.py`) |
| `str` | `Syntax` (configuration grammar), `_RawJSON` (API JSON response) |

### Other facts which shape the work

- 36 classes have more than one base. mypyc allows only one concrete base, the others
  must be marked `@trait`. Known cases: `MPRNLRI(Attribute, Family)`,
  `Notification(Message, Exception)`, the `RTRecord*` classes which also inherit from
  `rt.RouteTarget*`.
- 80 test files use `monkeypatch` or `mock.patch`. Compiled code calls functions and
  methods directly, so replacing a module attribute does not reach callers inside
  compiled code.
- 16 `isinstance(..., int)` checks and 86 `json.dumps` calls in `src/` may be relying
  on `AFI`, `ASN` and friends being real `int`.
- The build backend is setuptools, which mypyc supports through `mypycify()`.
- `tests/performance/` and `qa/bin/check_perf` already exist, with pytest-benchmark.

---

## 2. Design

### 2.1 What gets compiled

Compiled, in order of expected value: `protocol/`, `bgp/message/` (UPDATE, NLRI,
attributes, OPEN), `rib/`, then the parts of `reactor/` which touch every message
(framing, not the asyncio plumbing).

Left interpreted: `configuration/`, `cli/`, `application/`, `environment/`,
`logger/`, `debug/`, `vendoring/`. They run once or rarely, use `setattr`
driven by keyword names, and gain nothing worth the constraints.

Compiled classes cannot be subclassed from interpreted code unless marked
`@mypyc_attr(allow_interpreted_subclasses=True)`. Every base which the configuration
layer or the tests subclass needs that mark, found by grepping before phase 5.

### 2.2 Registry: explicit calls instead of decorators

```python
class KeepAlive(Message):
    ...


Message.register(KeepAlive)
```

The register functions already return the class and do nothing else, so the
behaviour is identical. Decorators which take arguments
(`@X.register(code)` shape, if any) become `X.register(code)(Klass)`.
The move is mechanical and done by a script, reviewed by diff.

### 2.3 Builtin subclasses: the value lives in `.value`

```python
class AFI:
    __slots__ = ('value',)

    def __init__(self, value: int) -> None:
        self.value: Final = value

    def __index__(self) -> int:
        return self.value

    def __int__(self) -> int:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AFI):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    def __format__(self, spec: str) -> str:
        return format(self.value, spec)
```

Rules:

- `__hash__` returns `hash(self.value)` and `__eq__` accepts a plain `int`, so a dict
  keyed by the number still finds the object and the other way round.
- `__index__` keeps `struct.pack`, `bytes()`, `hex()` and slicing working.
- Arithmetic and bit operations are not reimplemented. The call site uses `.value`.
  A dunder is only added when several call sites need it.
- Comparison dunders (`__lt__` and so on) only where something sorts these objects.
- JSON output uses `.value` explicitly. Nothing relies on `json.dumps` of a wrapper.
- Strict mypy reports every place where one of these objects is passed as `int`,
  which gives the list of sites to fix. The two things mypy cannot see are
  `isinstance(x, int)` and `json.dumps`, which are audited by hand.
- The `list[ASN]` segments hold their list in a field and implement `__iter__`,
  `__len__`, `__getitem__`, `__eq__`, `__hash__` if needed.
- The constant holders (`_MessageCode` and similar) lose their base if nothing uses
  them as a number.
- `Syntax(str)` and `_RawJSON(str)` stay as they are, their modules are not compiled.

In pure Python, `afi == 1` becomes a call to a Python-level `__eq__`, slower than
`int`'s. The benchmark after each class change measures it. Hot loops compare
`.value` directly where the cost shows.

### 2.4 mypyc markers without a runtime dependency

`trait` and `mypyc_attr` come from `mypy_extensions`. A small module,
`exabgp/util/mypyc.py`, imports them when available and otherwise defines
decorators which return the class unchanged. The pure-Python package keeps
`dependencies = []`.

### 2.5 Build

- `qa/bin/build_mypyc` compiles the chosen module list in place (or into a scratch
  directory) and reports mypyc errors. It is also the check that nobody reintroduces
  a pattern mypyc refuses.
- `setup.py` (or the setuptools hook) calls `mypycify()` only when
  `EXABGP_MYPYC=1`. Without it the wheel is pure Python, as today.
- Release: cibuildwheel produces compiled wheels for Linux x86_64 and aarch64 and
  macOS arm64, one per supported Python minor version, next to the pure wheel.

### 2.6 Tests against the compiled build

- The unit suite, the encoding and decoding functional tests and the RFC ledger run
  against both builds.
- A test which patches a module attribute to change what compiled code does fails
  under the compiled build. Each one is either rewritten to inject the dependency
  (argument, object attribute) or marked as pure-Python only, with the reason.
- mypyc checks attribute types at runtime. A wrong type assigned somewhere the
  checker could not see now raises `TypeError`. Each one found is a real bug and
  gets a test.
- Verify `copy.deepcopy` and pickling of compiled instances where the code uses them
  (`@mypyc_attr(serializable=True)` if needed).

---

## 3. Phases

Each phase leaves `./qa/bin/test_everything` green in pure Python and is committed
on its own.

### Phase 0: baseline

- Benchmark: decode a large corpus of UPDATEs (built from `qa/decoding/` and the
  encoding tests), encode the same, RIB insert and withdraw. Record numbers in this
  file.
- Profile the same runs (`py-spy` or `cProfile`) and list the top modules.
- Exit: numbers and a profile recorded, compile list confirmed or adjusted.

### Phase 1: scaffolding

- `exabgp/util/mypyc.py` shim.
- `qa/bin/build_mypyc` with the phase 5 module list.
- Exit: script runs and reports the 184 errors.

### Phase 2: registry decorators

- Script the move for all 204 decorated classes, including the configuration ones
  so that the pattern is uniform.
- Exit: `test_everything` green, mypyc down to 29 errors.

### Phase 3: builtin subclasses

One commit per class or small group, benchmark after each:

1. Constant holders: `_MessageCode`, `_integer` and similar.
2. Small value types: `Version`, `HoldTime`, `Reserved`, `Type`, `Parameter`,
   `CapabilityCode`.
3. `AFI`, `SAFI`.
4. `BaseValue`, `Resource` and everything below it, `ASN` included. Largest change.
5. AS_PATH segments.

- Audit the 16 `isinstance(..., int)` and the `json.dumps` calls as each class
  changes.
- Exit: `test_everything` green, pure-Python benchmark not worse than the baseline
  by more than 5%, mypyc down to 3 errors plus
  anything new.

### Phase 4: traits and `ClassVar` types

- Mark mixins `@trait`, resolve `Notification(Message, Exception)` and the
  `RTRecord*` diamond.
- Fix the 3 `ClassVar` mismatches.
- Exit: `build_mypyc` compiles `protocol/` and `bgp/message/` with no errors.

### Phase 5: first compiled slice and go/no-go

- Compile `protocol/` and `bgp/message/`, run the phase 0 benchmarks.
- Run the test suites against the compiled build, list the failures.
- **Gate:** if UPDATE decode is not at least 30% faster, stop here. Phases 2
  to 4 stay, they are harmless in pure Python, and this plan moves to `hold-`.

### Phase 6: tests pass compiled

- Fix or mark every test which fails only under the compiled build (2.6).
- Add a compiled run to `test_everything`: compile, then run the unit, encoding and
  decoding suites against the compiled modules.
- Exit: every suite green on both builds.

### Phase 7: widen

- Add `rib/`, then the message framing in `reactor/`, one at a time, benchmark each.
- Exit: compile list final, numbers recorded.

### Phase 8: packaging

- `mypycify()` behind `EXABGP_MYPYC=1`, cibuildwheel job, pure wheel kept.
- Document the compiled build and how to fall back to pure Python.
- Exit: compiled wheels install and pass the functional tests on each platform.

---

## 4. Decisions

Decided 2026-09-28:

- Phase 5 gate: UPDATE decode must be at least 30% faster compiled.
- Phase 3: pure Python may not get more than 5% slower than the baseline.
- The compiled run is part of `./qa/bin/test_everything`.

Decided 2026-09-30:

- Tests which pass None or a Mock where a Negotiated is declared are rewritten to use a
  real one (Negotiated.UNSET, or one built by negotiation).
- A copy of a compiled object may share immutable state: objects are to be used as if
  immutable. Each class is checked before its copy returns shared parts.

Still open:

- Whether compiled wheels become the default install or stay an explicit extra.

---

## Progress

- 2026-09-28: first compile attempt, errors counted and classified (section 1).
- 2026-09-29: ✅ phase 0. `qa/bin/benchmark_codec` replays the 144 UPDATEs of
  qa/encoding/*.ci (`--corpus ci`, 40 times per run) or 20 full-table shaped ipv4 unicast
  UPDATEs of 400 prefixes each (`--corpus bulk`), through four stages: decode, API JSON,
  encode, outgoing RIB. Best of 7 runs, pure Python, a00cac720, this machine:

  | stage | ci (5760 UPDATEs) | bulk (60 UPDATEs, 24000 prefixes) |
  |---|---|---|
  | decode | 209.07 ms | 134.94 ms |
  | json | 84.19 ms | 62.73 ms |
  | encode | 96.35 ms | 80.97 ms |
  | rib | 22.20 ms | 77.90 ms |

  Saved as build/benchmark/baseline-{ci,bulk}.json (not in git, per machine).
  Run to run noise is about 3%.

  Profile (`--profile <stage>`, own time per module): decode is spread over
  attribute/collection.py, update/collection.py, attribute.py, nlri/cidr.py and inet.py;
  JSON over reactor/api/response/json.py. `protocol/family.py` is 35 to 44% of encode and
  RIB time, all of it `Family.family()`, `Family.index()` and `Family.__init__` building a
  new Family object per NLRI per call. That is an algorithmic cost mypyc will not remove
  and is worth its own fix, outside this plan. The compile list stays as planned:
  protocol/ and bgp/message/, then rib/.
- 2026-09-29: ✅ phase 1. `exabgp/util/mypyc.py` (tested with and without
  mypy_extensions), `qa/bin/build_mypyc` (copies src/exabgp to build/mypyc and compiles
  there, groups the errors). setuptools added to the dev dependencies: mypyc needs it to
  build. On today's code: 183 errors (158 decorator, 25 builtin base).
- 2026-09-29: phase 2. 172 classes (205 decorator lines) moved from `@X.register...` to
  `X.register...(Klass)` after the class, by an AST script which keeps the order the
  decorators applied in (bottom first). mypyc down to 42: 30 builtin base, 12 `ClassVar`
  type (the capability `ID`). Unit tests pass (the sandbox makes socket tests fail, they
  pass outside it). benchmark_codec and build_mypyc listed as tools in test_everything.

- 2026-09-29: ✅ phase 2 verified: full `test_everything` green except the `-O` step,
  which failed on the new IntValue assertion test (fixed: skipped under -O, the check is
  an assert); the other 23 steps re-run green.
- 2026-09-30: phase 3 in progress. `exabgp/util/intvalue.py` (IntValue) is the base:
  value in `.value`, equal to and hashed like the int, `__index__`, ordered against
  IntValue, int and float, false at zero, formatted like an int subclass (f'{x}' is the
  name, f'{x:02x}' the number). tests/unit/test_util_intvalue.py holds it to the old int
  subclass on every one of those. Converted so far: MessageCode (was _MessageCode),
  Version, HoldTime, Reserved, operational Type, Parameter, CapabilityCode, AFI, SAFI.
  mypy found the typed call sites; these it could not, and were found by tests:
  - JSON `_string` printed an int subclass bare and anything else quoted: IntValue added
    (decoding test G, "version": "4").
  - template inheritance (`transfer`) accepted int and refused other types: IntValue added.
  - BGP-LS `jsonable`: IntValue kept a JSON number.
  - Capabilities keys: our OPEN keys by CapabilityCode (JSON shows the name), a received
    OPEN by the int the peer sent (JSON shows the number). Tests pin both, so the dict is
    `dict[CapabilityCode | int, Capability]` and the wire decode keeps the int key.
  Decisions: `AFI.value(name)`/`SAFI.value(name)` renamed `from_name()` (clash with
  `.value`); `CapabilityCode` and `Resource` lose their `__new__` cache (mypyc cannot
  compile `__new__` on these); `Family(afi, safi)` now takes AFI/SAFI and stores them
  without `from_int`; `make_route_refresh` takes `AFI | int`.
  Performance: AFI/SAFI first cost 13% on bulk encode (264000 `__eq__` calls from
  `safi in (...)`). Fixed with numeric frozensets in has_label/has_rd/has_path, `.value`
  in `Family.index`, and an identity shortcut in `__eq__`. After: ci 0.97x to 1.06x,
  bulk 1.02x to 1.21x of the baseline (higher is faster).

- 2026-09-30: phase 3 continued. Converted Resource/BaseValue and everything below it
  (ASN, Port, Protocol, ICMP, NetMask, TCPFlag, Fragment), the AS_PATH segments (Segment
  base holding `.asns`), and the four list capabilities (CapabilityList base holding
  `.items`). Resource lost its `__new__` cache. `json.dumps` got `default=json_number` at
  the 69 structured call sites in bgp/ and reactor/ (peer show failed with "Object of type
  ASN is not JSON serializable"). Test fixtures which wrapped a value in its own type
  (`ASN4(ASN(x))`, `ASN('65500')`) were changed to pass the int.
- 2026-09-30: phase 4. What mypyc refused next, and what was done:
  - classes nested in a class body (Message.CODE, Capability.CODE, Attribute.CODE and Flag,
    Operational.SUBTYPE, Encapsulation.Type, EOR.EOR_NLRI, the NS/Advisory/Query/Response
    namespaces of operational.py): moved to module level, the old name kept as a
    `ClassVar[type[...]]` alias. NS.Malformed is NSMalformed, Advisory.ADM AdvisoryADM, ...
  - 272 class constants declared `ClassVar` (mypyc reads `NAME = value` in a class body as
    an instance attribute default). Two could not be both: IP.afi (now `ADDRESS_FAMILY` for
    the registry, the instance keeps `afi`) and Capability.ID (now a ClassVar, the
    instance's own code is `code()` / `wire_code`, which is how RouteRefresh and
    MultiSession tell the RFC and the Cisco variants apart).
  - multiple inheritance: the FlowSpec mixins are `@trait`; RTRecord is a trait and each
    format names its subtype again (tests/unit/test_rt_record.py); ASN4 is a Capability
    holding an ASN in `.asn`, comparing and hashing as the number; MPRNLRI no longer
    inherits Family.
  - link state: aliases and unknown TLVs no longer clone classes with type(); an instance
    keeps the code it was decoded under (`BaseLS.tlv()`, `json_key()`).
  - mypyc crashed (AssertionError in create_ne_from_eq) on a class with `__eq__` and no
    `__ne__`: 30 classes got an explicit `__ne__`.
  - mypyc 1.20 does not compile `__index__`: removed from IntValue, so the pure build
    fails exactly where the compiled one would. mypy with a strict struct.pack stub
    (--custom-typeshed-dir, not committed) found the 19 pack sites; the tests found the
    rest. Tests which built wire bytes from codes wrap them in int().
  - With all that, mypyc compiles 209 modules (protocol/, bgp/message/, util/intvalue.py).
- 2026-09-30: pre-existing flakiness found and fixed: tests/unit/application/test_validate.py
  left logging on (process wide), and the UPDATE handler tests in the same xdist worker
  failed at random ("'dict' object has no attribute 'session'"). HEAD shows it too (0 to 2
  failures a run). tests/conftest.py restores the logging state after every test.
- Known issue kept as it was, to fix separately: TrafficRedirectASN4 prints
  `redirect:ASN4(4200000000):7`, which the configuration cannot read back.

- 2026-09-30: the compiled tree imports and runs. Beyond the list above it needed:
  - package `__init__.py` files stay interpreted (compiled, a package lost `__path__` while
    importing its submodules), so the seven which defined classes moved them out:
    protocol/ip/address.py, protocol/protocol.py, protocol/iso/iso.py,
    bgp/message/open/open.py, bgp/message/update/update.py, tunnel_encap/tunnel.py,
    tunnel_encap/sr_policy/tunnel.py. The `__init__` re-exports the same names.
  - the dict capabilities (AddPath, Graceful, PathsLimit, MultipleLabels) on a
    CapabilityDict base holding `.entries`.
  - no `super()` in a classmethod: mypyc passed `type` as cls (Port._value).
  - no `cls.__new__(cls)`, no `object.__new__(cls)`: IP, NextHop (copies return self, they
    are immutable), Watchdog, NLRI singletons, CIDR (`_with_fields`), Negotiated.UNSET
    (built through `__init__` with no neighbor).
  - the compiled build checks declared types at run time, and found what mypy could not:
    the configuration's internal pseudo-attributes (name, split, watchdog, withdraw) were
    `str`/`int` subclasses stored in a collection typed Attribute: they are now Attribute
    classes in attribute/internal.py, keeping their class names so test_frozen still
    proves the configuration reads as before. The SRv6 service decoders declared what the
    registry returned as the generic class.
  - update/nlri and update/eor.py are not compiled yet: 37 places there build instances
    without `__init__`. Family allows interpreted subclasses meanwhile.
- 2026-09-30: phase 5, first measurement, 142 modules compiled (update/nlri interpreted),
  per UPDATE against the phase 0 baseline (qa/bin/benchmark_codec, best of 7):

  | stage | ci compiled | bulk compiled | ci pure now | bulk pure now |
  |---|---|---|---|---|
  | decode | 1.40x | 1.20x | 1.00x | 1.01x |
  | json | 1.13x | 1.27x | 0.96x | 1.03x |
  | encode | 1.82x | 1.42x | 0.97x | 1.17x |
  | rib | 1.38x | 1.45x | 1.08x | 1.23x |

  Bulk decode, a full table, is mostly NLRI decoding, which is still interpreted: compiling
  update/nlri is what the gate now waits on.

- 2026-09-30: update/nlri, the unicast/labelled/VPN chain (nlri.py, cidr.py, inet.py,
  label.py, ipvpn.py, qualifier/) compiled: factories build through `__init__`, copies
  through `INETBase._blank()` (the deepcopy tests require a distinct object, so a copy
  cannot return self), Labels/RD/PathInfo copy through their constructor. NLRI allows
  interpreted subclasses, so the other families (EVPN, MVPN, MUP, BGP-LS, Flow, VPLS, RTC,
  SR policy) stay interpreted with their `__new__` copies. `__ne__` is `not self == other`:
  calling `self.__eq__` put NotImplemented in a compiled bool local.
- 2026-09-30: ✅ phase 5 gate passed. 154 modules compiled, per UPDATE against the phase 0
  baseline, best of 7, every capture decoded:

  | stage | ci compiled | bulk compiled |
  |---|---|---|
  | decode | 1.55x | 2.10x |
  | json | 1.26x | 2.10x |
  | encode | 1.85x | 1.65x |
  | rib | 1.57x | 1.58x |

- 2026-09-30: phase 6 started. The suite run against the compiled tree
  (`PYTHONPATH=build/mypyc pytest tests`): 4097 failed, 10600 passed. By cause:

  | count | cause | where the fix belongs |
  |---|---|---|
  | ~2850 | a test passes None or a Mock where `Negotiated` is declared (2313 from one fuzz helper in test_bgpls_tlv_properties) | the tests: Negotiated.UNSET or a real one |
  | ~890 | `bool expected; got None/Mock` | to investigate: tests or source |
  | ~100 | a test passes int where ASN/MessageCode/CapabilityCode is declared, or the reverse | the tests |
  | 43 | a test subclasses a compiled class (Named(IntValue), fake messages) | allow_interpreted_subclasses on the base, or the test |
  | ~60 | test_message_contract reads signatures and `__dict__`, which a compiled class shows differently | the test |
  | ~30 | copy/deepcopy of compiled classes without `__copy__`: Negotiated (configuration/check.py copies it), and whatever a neighbour deepcopy reaches (install.py session_of, check.py) | the source: `__copy__`/`__deepcopy__`, or mypyc serializable with state methods |
  | 18 | test_rib_watchdog builds its own internal attribute | the test |

## Failures

(none yet)

## Blockers

(none)

## Resume Point

~~Phase 0: build the benchmark corpus and record the pure-Python baseline.~~

Phase 4, last blocker before the phase 5 measurement: the compiled tree does not import.
A mypyc class cannot be built without running `__init__` (`cls.__new__(cls)` fails to
compile, `object.__new__(cls)` is refused at run time, and the generated `__new__` calls
`__init__`). 24 sites in 13 classes use that to skip `__init__`: IP (NoNextHop, copies),
Watchdog, NextHop attribute copies, CIDR factories, Flow/INET/IPVPN/RTC/VPLS/Empty/
SRPolicy copies and factories, NLRI singletons, PathInfo copies. Each needs an `__init__`
which can take the stored fields.


SUPERSEDED BY (2026-09-30): phases 0 to 5 are done and the gate passed. Resume at phase 6:
the compiled test run (table above). Decisions wanted from Thomas before the test side:
rewrite the Mock/None negotiated tests to real objects, or mark them pure-Python only;
and whether copies of compiled classes may share immutable state. Nothing is committed yet:
the plan asked for a commit per phase.

### 2026-09-30: message functions take a MessageCode only

- `MessageCodes.name`/`short`, `Message.length_valid`/`header_refuses`/`string`/`klass`/`unpack` take a `MessageCode`, not `int | MessageCode` (no `None` either, nothing passed it)
- the type octet becomes a `MessageCode` where it is read: `MessageCodes.of(octet)` returns the known codes without building them again
- `Connection.reader_async` returns a `MessageCode` (`UNREAD`, code 0, with a header error), carried through `Protocol` and `Processes.packets` (JSON and text print `category.value`)
- tests pass `Message.CODE.X` or `Message.CODE.of(n)`
- the same for capabilities: `Capability.unpack`, `Capabilities.announced`/`tlvs` and the `Capabilities` keys take a `CapabilityCode`; the OPEN decoder builds it from the octet once. `CapabilityCode.__init__` and `MessageCode.__init__` take an `int` only
- compiled run after both: 260 failed (was 286), no MessageCode or CapabilityCode type error left
