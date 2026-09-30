# Compile the hot path with mypyc

📋 **Status:** Planning
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

Still open:

- Whether compiled wheels become the default install or stay an explicit extra.

---

## Progress

- 2026-09-28: first compile attempt, errors counted and classified (section 1).

## Failures

(none yet)

## Blockers

(none)

## Resume Point

Phase 0: build the benchmark corpus and record the pure-Python baseline.
