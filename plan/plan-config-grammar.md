# Configuration grammar: define every keyword once, derive everything else

**Status:** 📋 Planning
**Created:** 2026-09-27
**Last Updated:** 2026-09-27

## Goal

The configuration classes were meant to be meta-defined: the valid syntax stated once, as
data, with the parser, the error messages, the help text, completion and the documentation
all derived from it. What we have is a hand-written parser with a schema layer bolted beside
it, and the hand parser still decides what is accepted.

This plan replaces both with a new package, `exabgp.configuration.grammar`, in which:

- each value kind is a reusable type which parses, renders, describes and completes itself
- each keyword is declared once, with its type, default, documentation and the Settings
  field it fills
- one engine walks the declarations to read a configuration and build Settings objects
- the configuration printer, `exabgp configuration syntax`, CLI completion, the example
  configuration, the man page, the wiki reference and the JSON schema are generated from
  the same declarations

The grammar parser **replaces main's configuration parser**. The target is main's current
behaviour; reading 5.0 configurations follows from that, since main's parser reads them.

Decided with Thomas on 2026-09-27:

- a **new package**, not an extension of `schema.py` / `validator.py`
- blocks **bind to Settings** objects directly, no scope dict in between

Decided with Thomas on 2026-09-27, second round:

- **preserve behaviour**: the new parser accepts exactly what the old one accepts and
  builds the same result; accidents are listed in section 6, not fixed
- **every configuration must parse with both parsers**, old and new, to the same result
- **a test for every valid configuration form**: every keyword, every accepted spelling of
  its value
- **both parsers during development only**, so they can be compared: once the grammar
  parser is complete, the work is committed with both parsers present (a milestone to
  return to), then the legacy parser and the switch between them are removed
- **unless the API changed**: if the work changes what API programs see as a side effect,
  the user may be given the choice and the legacy parser kept. Decided at the end, from
  the list in section 7

---

## 1. Measured state, 2026-09-27

Measured by walking every `Section` subclass (script in the Resume Point section).

### The schema is documentation in 13 sections

A `known` entry wins over the schema leaf of the same name (`Section.parse`, priority 1),
so for these keywords the schema type is never used to read anything:

| Section | Keywords where the hand parser runs instead of the schema |
|---|---|
| `ParseStaticRoute` | all 25 (`next-hop`, `as-path`, `community`, `label`, `rd`, ...) |
| `ParseVPLS` | all 21 |
| `ParseFlowMatch` | all 19 |
| `ParseFlowThen` | 15 |
| `ParseNeighbor` / `ParseTemplateNeighbor` | `local-address`, `local-as`, `peer-as`, `router-id`, `hold-time`, `outgoing-ttl`, `incoming-ttl`, `md5-base64`, `inherit` |
| `ParseAPI` | all 6 |
| `ParseFlowRoute` | all 4 |
| `ParseRole` | all 3 |
| `ParseConfederation`, `ParseProcess`, `ParseFlowScope`, `ParseCapability` | `identifier`, `members`, `run`, `interface-set`, `add-path` |

### The rest mostly wraps hand parsers

Of about 450 schema leaves, 162 use `LegacyParserValidator`, a wrapper around a hand
parser: the engine knows nothing of their syntax. That covers all of flow announce, VPLS,
L2VPN, MUP and operational.

### 61 leaves claim to be `STRING` and are not

For example `confederation members` (a list of ASN), flow `protocol` / `tcp-flags` /
`fragment` (enumerations), `otc` (an ASN), `bgp-prefix-sid`. Completion and generated
documentation are wrong wherever the type is wrong.

### One option lives in many places

`hold-time` has eight definitions, and nothing makes them agree:

1. schema `Leaf` with `IntValidators.hold_time()` (`neighbor/__init__.py:127`)
2. `known['hold-time'] = hold_time` (`neighbor/__init__.py:303`), the one which runs
3. `assign['hold-time'] = 'hold_time'` (`neighbor/__init__.py:355`)
4. `NumericConstraint` in `constraints.py:216`
5. `MIN_NONZERO_HOLDTIME` in `neighbor/parser.py:29`
6. the range check in `NeighborSettings.validate` (`bgp/neighbor/settings.py:190`)
7. the default 180, in both `settings.py:154` and `neighbor.py:84`
8. the configuration printer, `neighbor.py:624`

The printer drifting from the parser is why `str(neighbor)` prints `rate-limit disable`,
which does not read back.

### The section tree is patched by hand

`configuration.py` carries `_SPECIAL_COMMANDS`, `_KEYWORD_TO_SECTION`, a `l2vpn/vpls`
override and an `attribute` → `attributes` rename inside `run()`. Every `Section` carries
four parallel class dicts: `known`, `action`, `assign`, `default`.

### Errors are uneven

| Input | Message today |
|---|---|
| `encoder jsn;` | `'jsn' is not a valid choice`, `Valid options: text, json` (good) |
| `hold-tim 30;` | `invalid keyword "hold-tim"`, no suggestion: `Configuration.run()` rejects the keyword before `Section.parse` reaches its Levenshtein suggestions |
| `protocol tcpp;` | `unknown protocol tcpp`, no list |
| any error | `line N` is the count of statements, not the file line: an error on line 7 printed `line 6`. No column, no file name |

`core/format.py:tokens()` already yields `(line, column, word)`; `Parser._tokenise`
throws the positions away.

---

## 2. Design

### 2.1 Package layout

```
src/exabgp/configuration/grammar/
    __init__.py
    tokens.py       # Token(word, file, line, column), Tokens stream with peek/expect
    error.py        # ConfigError(token, message, expected=[...], suggestions=[...])
    types/
        base.py     # the Type protocol
        basic.py    # Int, Bool, Flag, Enum, Str, Hex, OneOf, ListOf, Bracketed
        network.py  # IP, Prefix, IPRange, Port, ASN
        bgp.py      # Community, ExtCommunity, LargeCommunity, RD, RT, Label, NextHop,
                    #   ASPath, Origin, Aggregator, ...
        flow.py     # FlowProtocol, TCPFlags, Fragment, numeric operators
    nodes.py        # Leaf, Block, Line, Select, Rule
    engine.py       # reads Tokens against a node tree, builds Settings
    render.py       # Settings -> configuration text
    describe.py     # syntax, completion, JSON schema, example, man/wiki output
    tree/           # the declarations, one module per section
        process.py
        neighbor.py
        capability.py
        family.py
        api.py
        confederation.py
        static.py
        flow.py
        l2vpn.py
        ...
        root.py     # the top of the tree
```

### 2.2 Types

```python
class Type(Protocol[T]):
    def parse(self, tokens: Tokens) -> T        # raises ConfigError
    def render(self, value: T) -> list[str]     # parse(render(v)) == v
    def hint(self) -> str                       # '<asn>', 'igp|egp|incomplete'
    def choices(self, partial: str) -> list[str]
    def json_schema(self) -> dict[str, Any]
```

- A type consumes as many tokens as it needs, so `ASPath` owns its brackets and segment
  keywords and `ListOf` owns `[ ... ]`. Tokeniser loops such as `confederation.members()`
  and `static/parser.as_path()` are not used by the grammar (they stay in the legacy code).
- `Enum` takes a real Python `Enum`. The valid choices, the default and the spelling used
  when printing all come from that one class:

  ```python
  class OnExit(StrEnum):
      WITHDRAW = 'withdraw'
      KEEP = 'keep'
  ```

- Limits live in the type: `Int(0, 65535, unit='seconds', rule=zero_or_at_least(3))`.
  The grammar does not use `constraints.py`; the legacy parser keeps it. A unit test checks
  the limits in the two agree while both exist.
- `OneOf(Enum(Disable), Int(1, MAX))` covers values such as `rate-limit disable|<n>` and
  `local-as auto|<asn>`.
- Every loop in a type is bounded by a named constant (EXA_STYLE).

### 2.3 Nodes

```python
PROCESS = Block(
    'process', named=Name(), into=ProcessSettings,
    doc='external program talking to exabgp over the API',
    children=[
        Leaf('run', Command(), field='run', mandatory=True),
        Leaf('encoder', Enum(Encoder), field='encoder', default=Encoder.TEXT),
        Leaf('on-exit', Enum(OnExit), field='on_exit', default=OnExit.WITHDRAW,
             doc='what happens to the routes this program announced when it exits'),
    ],
)

CONFEDERATION = Block(
    'confederation', into=ConfederationSettings,
    doc='RFC 5065 BGP confederation',
    children=[
        Leaf('identifier', ASN(zero=False), field='identifier', mandatory=True),
        Leaf('members', ListOf(ASN(), max=MAX_MEMBERS), field='members', default=()),
    ],
)

NEIGHBOR = Block(
    'neighbor', named=IPRange(), into=NeighborSettings, repeat=True,
    children=[
        Leaf('hold-time', Int(0, 65535, unit='seconds', rule=zero_or_at_least(3)),
             field='session.hold_time', default=180),
        Leaf('local-as', OneOf(Keyword('auto'), ASN()), field='session.local_as', mandatory=True),
        Leaf('as-set', Enum(ASSet), field='as_set', default=ASSet.WITHDRAW),
        CONFEDERATION, FAMILY, CAPABILITY, API, STATIC, FLOW, L2VPN,
    ],
    rules=[
        Requires('confederation', explicit=['local-as', 'peer-as']),
        Check(confederation_is_consistent),
    ],
)
```

| Node | Replaces | Meaning |
|---|---|---|
| `Leaf(keyword, type, field=, default=, mandatory=, repeat=, doc=, since=, deprecated=)` | schema `Leaf`/`LeafList`, `known`, `action`, `assign`, `default` | `keyword value ;` |
| `Block(keyword, named=, into=, children=, rules=, repeat=)` | `Section` subclasses, `_KEYWORD_TO_SECTION` | `keyword [name] { ... }` |
| `Line(keyword, head=, children=, into=)` | `RouteBuilder`, the static/flow one-liners | `route <prefix> k v k v ... ;` with the children in any order |
| `Select(keyword, variants={word: node})` | `TypeSelectorBuilder`, `TupleLeaf`, `_SPECIAL_COMMANDS` | the first word picks the variant (`family ipv4 unicast`, `mup-isd ...`) |
| `Rule` (`Requires`, `Conflicts`, `Check(fn)`) | `ParseConfederation.apply`, the `post()` checks, the cross-field half of `*Settings.validate` | a rule over a finished block, reported at the block's position |

- `field=` names a Settings attribute, dotted for nested ones (`session.hold_time`).
- `repeat=True` on a leaf collects a list, on a block a dict keyed by name.
- `since=` / `deprecated=` carry the version history and drive a warning, replacing ad hoc
  renames such as `attribute` → `attributes`.
- The same `Block` object is used for `template neighbor` and `neighbor`, so the two can no
  longer drift (today `ParseTemplateNeighbor` duplicates the neighbor schema).

### 2.4 Binding to Settings

- `into=` names a Settings dataclass. The engine builds an instance, assigns each leaf to
  its `field`, applies defaults from the declaration, runs the rules, and hands the finished
  object to the parent block.
- Settings objects which do not exist yet are created in their phase: `ProcessSettings`,
  `CapabilitySettings`, `APISettings`, `FamilySettings`, `ConfederationSettings`,
  `RoleSettings`, `TCPAOSettings`, `OperationalSettings`, and the route line settings that
  `INETSettings` / `FlowSettings` / `VPLSSettings` / `RTCSettings` do not already cover.
- For the grammar parser, defaults come from the declaration. Settings dataclass defaults
  which duplicate them stay while the legacy parser relies on them, and a unit test checks
  the two are equal.
- `Neighbor.from_settings()` and `Configuration.from_settings()` stay the only way from
  Settings to runtime objects, so the programmatic API (`done-from-settings-conversion.md`)
  and the file parser meet at the same place.
- Inheritance (`inherit` / templates) becomes a merge of two Settings objects field by
  field, driven by the declaration, instead of copying scope dicts.

### 2.5 Engine

- `Tokens` keeps the file, line and column of every token (from `format.tokens()`).
- The engine reads a statement, looks up the keyword among the children of the current
  node, and asks the child to consume the rest. There is no separate command list and no
  second lookup table, so an unknown keyword and a misspelt one are found in one place.
- Errors all have one shape:

  ```
  etc/x.conf:7:3: unknown keyword 'hold-tim' in neighbor 127.0.0.1
    did you mean: hold-time
  etc/x.conf:9:12: 'tcpp' is not a valid flow protocol
    expected: tcp, udp, icmp, gre, ... or a number 0-255
  etc/x.conf:4:1: neighbor 127.0.0.1 is missing peer-as
  ```

  The `expected:` list comes from `Type.choices('')` / `Type.hint()`, the suggestion from
  Levenshtein over the same choices.
- API text commands (`announce route ...`, `Configuration.partial()`) go through the same
  `Line` declarations, so the API and the file accept one language.
- Reload keeps its transaction behaviour: parse to Settings first, swap only on success.

### 2.6 What is generated

| Output | Today | After |
|---|---|---|
| configuration printer (`str(neighbor)`, `configuration.to_dict`) | hand written in `neighbor.py`, drifts | `render.py` walks the tree over Settings |
| `exabgp configuration syntax [path]` | partial `syntax` strings | `describe.py`, per section or whole tree |
| CLI / editor completion | `cli/schema_bridge.py` via schema types which may be wrong | `Type.choices()` |
| `configuration/example.py` | walks the schema | walks the tree |
| `doc/man/exabgp.conf.5`, wiki Directives-Reference / Attribute-Reference | written by hand | generated, then reviewed |
| JSON schema | `schema_to_json_schema` | `Type.json_schema()` |
| `exabgp decode --command` (`configuration/command.py`) | builds API text by hand | uses `render()` for the route line |

### 2.7 Selecting the parser (development only)

While the work is in progress both parsers live side by side, behind one switch:

```
exabgp_configuration_parser = grammar | legacy
```

- the default stays `legacy` until the grammar parser is complete (end of phase 4)
- `exabgp configuration validate --parser grammar|legacy|both`; `both` runs the two and
  reports any difference
- the switch and `--parser` are development tools: they are not documented for users, and
  they are removed with the legacy parser in phase 6
- the grammar package never imports from the legacy modules (`core/section.py`,
  `*/parser.py`, `schema.py`, `validator.py`, ...), so removing them does not touch it. It
  may import the BGP objects both build (`ASN`, `Community`, `INET`, ...)

### 2.8 Differential test: old and new agree

A configuration is **equal** under the two parsers when all of these match:

- `Configuration.to_dict()` (the JSON export)
- per neighbor, `Neighbor.__eq__` (checked to cover every field first, extended if not)
- per neighbor, the UPDATE messages its routes encode to (the `check_generation` path),
  byte for byte
- the processes and their settings

A configuration is **rejected alike** when both parsers refuse it. The messages may differ
(the new ones are meant to be better), the verdict may not.

Inputs, all run through both parsers:

1. every `etc/exabgp/*.conf`
2. every configuration used by `qa/encoding`, `qa/api`, `qa/decoding` and the unit fixtures
3. the forms corpus (2.9)
4. every API route command in `qa/api/*.ci` and `qa/encoding/*.ci` (`cmd:` lines), through
   `Configuration.partial()` on both sides

A difference fails the test. Where the difference is an accident of the old parser, it is
recorded in section 6 and the new parser reproduces it, per the preserve decision.

### 2.9 The forms corpus: every valid configuration form

`tests/unit/configuration/forms/` holds one case per keyword per accepted form:

```python
FORMS = [
    Form('neighbor', 'local-as 65000;'),
    Form('neighbor', 'local-as auto;'),
    Form('neighbor', 'local-as 1.10;'),               # asdot, if the old parser takes it
    Form('neighbor', 'hold-time 0;'),
    Form('neighbor', 'hold-time 3;'),
    Form('neighbor', 'hold-time 65535;'),
    Form('route',    'as-path [ 1 2 ] ( 3 4 ) confed-sequence [ 5 ] confed-set [ 6 7 ]'),
    Form('route',    'as-path 65001'),
    Form('route',    'as-path [ ]'),
    Form('route',    'community [ 1:1 no-export ]'),
    Form('route',    'community 1:1'),
    ...
]
```

- each form is wrapped in the smallest configuration that makes it legal (a neighbor with
  its mandatory leaves, a route with a next-hop) and run through both parsers, 2.8 rules
- each type declares `examples()`, every spelling it accepts, and each leaf lists the
  boundary values of its range; a **coverage test** fails when a declared keyword, a type
  example or a `Select` variant has no form in the corpus, so a new keyword cannot land
  without its forms
- forms found only by reading the legacy parser (aliases, case folding, optional commas,
  `attribute` for `attributes`) are added by hand and tagged `legacy_alias=True`
- the same corpus carries **invalid forms** (out of range, wrong bracket, unknown choice),
  which both parsers must reject
- the corpus is built before the declaration it covers: the forms are written against the
  legacy parser first, so they record what is accepted today, then the declaration is
  written until the new parser agrees

### 2.10 The round-trip test

For every input of 2.8 which parses:

```
settings1 = read(file)
text      = render(settings1)
settings2 = read(text)
assert settings1 == settings2
assert render(settings2) == text
```

and `render()` output must also be accepted by the legacy parser, with an equal result, so a
configuration printed by the new code still loads on a deployment which selected `legacy`.

Per type, a property test: `parse(render(v)) == v` over generated values.

---

## 3. Phases

Each phase ends with `./qa/bin/test_everything` passing, and with the differential,
forms-coverage and round-trip tests green for every section migrated so far. The
configuration language does not change. The legacy code is not modified except to fix
the line number (phase 0), until phase 6 removes it.

There is no per-section bridge between the two parsers: the grammar parser reads a whole
configuration or refuses it. Until phase 4 is done the differential test runs on the
configurations whose sections are all migrated, plus the forms corpus of the migrated
sections, and reports the rest as skipped with the missing section named.

### Phase 0: groundwork

- [ ] `grammar/tokens.py`: positioned tokens from `format.tokens()`, errors carry
      `file:line:column`
- [ ] `grammar/error.py`
- [ ] `grammar/types/base.py`, `basic.py`, `network.py`, each type with `examples()`, unit
      and property tests
- [ ] `grammar/nodes.py`, `engine.py`, `render.py`
- [ ] `exabgp_configuration_parser` switch, default `legacy`
- [ ] `configuration validate --parser grammar|legacy|both`
- [ ] differential test harness (2.8), with the equality check; verify `Neighbor.__eq__`
      covers every field and extend it where it does not
- [ ] forms corpus skeleton and coverage test (2.9)
- [ ] round-trip harness (2.10)
- [ ] fix the reported line number in the legacy parser (wrong today regardless of this plan)

### Phase 1: the small blocks

For each block: write its forms against the legacy parser first, then the declaration and
its Settings class, until both parsers agree on every form.

- [ ] `process` (`ProcessSettings`)
- [ ] `api`, `api/send`, `api/receive`
- [ ] `capability`, `role`, `tcp-ao`
- [ ] `confederation`
- [ ] `family`, `add-path`, `nexthop`

### Phase 2: neighbor and template

- [ ] forms for every neighbor leaf and for `inherit` / `template` combinations
- [ ] `neighbor` and `template neighbor` from one `Block`
- [ ] `inherit` as a Settings merge, compared to the legacy result on every template form
- [ ] `str(neighbor)` and `to_dict` from `render()`, output accepted by both parsers; the
      `rate-limit disable` printing bug closes here (printing, not parsing, so the preserve
      decision is not touched)

### Phase 3: unicast route lines

- [ ] forms for every attribute and every route keyword
- [ ] `grammar/types/bgp.py`: every attribute type (`Origin`, `ASPath`, `Community`, ...)
- [ ] `static` / `route` as a `Line`; API `announce` commands through it when `grammar` is
      selected, and the `cmd:` lines of `qa/*.ci` in the differential test
- [ ] `label`, `vpn`, `path`, `rtc`
- [ ] `exabgp decode --command` uses `render()`

### Phase 4: the rest of the families

- [ ] flow (`match`, `then`, `scope`, the one-liner)
- [ ] l2vpn / vpls
- [ ] mup, mvpn (`Select`)
- [ ] sr-policy
- [ ] operational

Exit: every configuration and every API command in the repository parses under both
parsers to the same result, and the coverage test reports no keyword without forms.

### Phase 5: complete, with both parsers (milestone commit)

- [ ] default `exabgp_configuration_parser` to `grammar`
- [ ] `test_everything` passes with `grammar` as the default, and the differential suite
      passes with both
- [ ] `cli/schema_bridge.py` switched to `describe.py`
- [ ] a unit test over the import graph: the grammar package imports nothing from the
      legacy modules
- [ ] **freeze the legacy results**: for every input of 2.8 and every form of 2.9, store
      what the legacy parser produced (`to_dict()` JSON and the encoded UPDATE bytes, or
      "rejected") as golden fixtures under `tests/unit/configuration/forms/expected/`.
      Once the legacy parser is gone the forms and differential tests compare against
      these files, so they keep proving the behaviour was preserved
- [ ] commit, when Thomas asks: this commit holds both parsers and is the point to come
      back to if the removal shows a problem

### Phase 6: remove the legacy parser and the switch

Gate: review section 7 (API side effects) with Thomas first. If it is not empty he may
decide to keep the legacy parser and the switch as a user choice for the API; this phase
is then replaced by documenting the switch and keeping both parsers tested.

- [ ] delete `core/section.py`, `core/action.py`, the `Parse*` / `Announce*` sections, the
      `*/parser.py` hand parsers, `schema.py`, `validator.py`, `validators.py`,
      `constraints.py`, `_build_structure`, `_SPECIAL_COMMANDS`, `_KEYWORD_TO_SECTION`,
      `dispatch`, `_enter`, `run`
- [ ] delete `exabgp_configuration_parser` and `configuration validate --parser`
- [ ] the differential tests switch to the frozen fixtures; nothing else in `tests/` may
      import a deleted module (tests which only tested legacy internals go with it)
- [ ] `test_everything` passes
- [ ] commit, when Thomas asks

### Phase 7: generated documentation

- [ ] `exabgp configuration syntax [section]`
- [ ] man page and wiki reference pages generated, reviewed by hand before publishing
- [ ] `.claude/exabgp/` codebase docs updated for the new package

---

## 4. Open decisions

1. **Command name** for the generated syntax: `exabgp configuration syntax` or a
   `--help` on `configuration validate`?
2. **Documentation source of truth.** Generated man page replaces the hand-written one, or
   the generated reference is included in it with the prose kept by hand?
3. **Switch name.** `exabgp_configuration_parser = grammar|legacy` is proposed; it only
   lives during development, so any name that fits the environment section naming will do.

Settled: strictness (preserve). 5.0 compatibility is not a separate goal: the grammar
parser replaces main's parser and must match it, and main's parser already reads 5.0
configurations, so 5.0 compatibility comes with doing main correctly. No 5.0 configuration
corpus, no 5.0 branch work.

---

## 5. Risks

- **Inheritance and templates** are the least regular part of the current parser; phase 2
  may find behaviour no test covers. Mitigation: forms for every template combination the
  legacy parser takes, written before the declaration.
- **Route lines** accept keywords in any order and some attributes more than once
  (`community` appends). The `Line` node must model repetition explicitly.
- **Reproducing accidents** can push odd special cases into clean declarations. Each one is
  isolated (a `legacy_alias` on the leaf or a named quirk type), listed in section 6, so it
  can be dropped in one place when the legacy parser goes.
- **Equality blind spots**: if `Neighbor.__eq__` or `to_dict()` miss a field, the
  differential test passes on a real difference. Mitigation: phase 0 audits the comparison
  against every Settings field, and the wire bytes are compared as well.
- **Performance**: large static route tables are read at start and on reload. Measure
  reading `qa/` bulk configurations with both parsers in phase 3.
- **Two parsers during development**: a keyword added to main while this work runs has to
  go into both. The forms coverage test makes forgetting either one fail.
- **Losing the comparison when the legacy parser goes**: covered by the frozen fixtures of
  phase 5, taken from the legacy parser before it is deleted.

---

## 6. Accidents found during migration

(to fill: things the legacy parser accepts or rejects by accident, one line each. The
grammar parser reproduces each one; whether to drop any of them is a separate decision
after phase 6, each with its own CHANGELOG entry.)

---

## 7. API side effects

Anything an API program would see differently under the grammar parser, one line each,
with the command, the old behaviour, the new behaviour and why the new one cannot match.
Covers the text commands going through `Configuration.partial()` (`announce`,
`withdraw`, `group`, ...), the replies and error messages returned to the program, and
anything printed from `render()` that the API emits (`show neighbor configuration`, ...).

Preserving behaviour means this list should stay empty; an entry is a failure to preserve
that could not be avoided. It decides the phase 6 gate.

(none yet)

---

## Progress

- 2026-09-27: survey done, design agreed (new package, bind to Settings), plan written
- 2026-09-27: preserve behaviour, both parsers must agree, forms corpus for every valid
  form
- 2026-09-27: both parsers only during development; commit complete work with both, then
  remove the legacy parser and the switch
- 2026-09-27: if the API changed as a side effect, keeping the legacy parser as a user
  choice is decided at the end (section 7, phase 6 gate)

## Failures

(none yet)

## Blockers

(none)

## Resume Point

Start phase 0. The survey script used for section 1:

```python
import importlib, pkgutil
import exabgp.configuration as C
from exabgp.configuration.core import Section
from exabgp.configuration.schema import Leaf, LeafList
for m in pkgutil.walk_packages(C.__path__, 'exabgp.configuration.'):
    importlib.import_module(m.name)
def subs(c):
    for s in c.__subclasses__():
        yield s
        yield from subs(s)
for cls in sorted(set(subs(Section)), key=lambda c: c.__module__):
    children = cls.schema.children if cls.schema else {}
    known = cls.__dict__.get('known', {})
    leaves = [k for k, v in children.items() if isinstance(v, (Leaf, LeafList))]
    print(cls.__name__, 'leaves', len(leaves), 'hand', [k for k in leaves if k in known],
          {k: type(children[k].get_validator()).__name__ for k in leaves})
```

Run with `env exabgp_log_enable=false PYTHONPATH=src .venv/bin/python survey.py`.
