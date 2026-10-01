# Configuration grammar: define every keyword once, derive everything else

**Status:** ✅ Completed
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

- [x] `grammar/tokens.py`: positioned tokens from `format.tokens()`, errors carry
      `file:line:column`
- [x] `grammar/error.py`
- [x] `grammar/types/base.py`, `basic.py`, `network.py`, each type with `examples()`, unit
      and property tests
- [x] `grammar/nodes.py`, `engine.py`, `render.py`
- [x] `exabgp_debug_parser` switch, default `legacy` (`Configuration.reload(parser)`)
- [x] `configuration validate --parser grammar|legacy|both`
- [x] differential test harness (2.8), with the equality check; verify `Neighbor.__eq__`
      covers every field and extend it where it does not
- [x] forms corpus skeleton and coverage test (2.9)
- [x] round-trip harness (2.10)
- [x] fix the reported line number in the legacy parser (commit 2978fbb38)

### Phase 1: neighbor, template and the blocks inside them

Merged with the old phase 2 on 2026-09-27: the small blocks (api, capability, role,
tcp-ao, confederation, family, add-path, nexthop) all sit inside `neighbor`, and can only
be compared through the `Neighbor` the section builds. The legacy parser builds that
`Neighbor` directly (`ParseNeighbor.post`, ~400 lines), not through `NeighborSettings`.

- [x] compare neighbors: `Neighbor.__eq__` only covers what forces a reset on reload, so
      `compare.neighbor_state` snapshots every field (session and capability dataclasses,
      families, api, routes as text, RIB name)
- [x] `SessionSettings` gains md5-ip, local-link-local, confederation; `NeighborSettings`
      gains prefix-limit; `Neighbor.from_settings(rib=False)` lets the configuration make
      the RIB after the multi-session split (`grammar/install.py`)
- [x] forms for every neighbor leaf and section leaf (`tests/unit/config_grammar/forms_neighbor.py`),
      each run in a neighbor and in a template it inherits, plus whole documents
- [x] `neighbor` and `template neighbor` from one set of children, with `api`, `capability`,
      `role`, `tcp-ao`, `confederation`, `family`, `add-path`, `nexthop`
      (`static`, `flow`, `l2vpn`, `operational`, `announce` stay pending for phases 3 and 4)
- [x] `inherit` merges the values by keyword before they become Settings, with the legacy
      `transfer` rules (`grammar/tree/resolve.py`): the rules operate on the raw values, a
      Settings merge could not reproduce them. To revisit once the legacy parser is gone.
- [x] a neighbor prints back from its NeighborSettings (`grammar/tree/unresolve.py`), and the
      print reads back equal with both parsers
- [ ] `str(neighbor)` and `to_dict` from `render()`: deferred to the milestone review, it
      changes what `show neighbor configuration` prints to API programs (section 7)

### Phase 2: merged into phase 1

The numbers of the later phases are kept, other sections refer to them.

### Phase 3: unicast route lines

Decided 2026-09-28: every route value (next-hop, as-path, communities, labels, RD, flow
match and then, MUP, VPLS, ...) is rewritten as a grammar Type with parse, render, hint and
examples; the ~130 legacy value functions are not moved or wrapped. Each type is checked
against the legacy function by the forms and differential tests, and phase 6 deletes the
legacy functions.

- [x] forms for every attribute and every route keyword (`tests/unit/config_grammar/forms_route.py`),
      each in a one-line route, a route block, and a template
- [x] `grammar/types/bgp.py`: every static route value (prefix, next-hop, origin, med,
      local-preference, as-path, communities, large and extended communities, aggregator,
      originator-id, cluster-list, otc, aigp, attribute, label, rd, path-information,
      bgp-prefix-sid, bgp-prefix-sid-srv6, name, split, watchdog, withdraw);
      `grammar/types/lists.py`: `OneOrList` for `value | [ value ... ]`
- [x] `static`: `route` one-liner, `route <prefix> { }` block, `attributes`/`attribute`
      (`grammar/tree/static.py`); routes printed back as route lines. `sr-policy` and `rtc`
      statements pending.
- [x] API `announce|withdraw route|attributes` read by the grammar when selected
      (`Configuration._partial_grammar`); the `cmd:` lines of `qa/*.ci` in
      `tests/unit/config_grammar/test_commands.py`
- [x] `announce { ipv4|ipv6 { unicast|multicast|nlri-mpls|mpls-vpn|rtc ...; } }` and
      `static { rtc ...; }` (`grammar/tree/announce.py`), with the announce value rules;
      API `announce|withdraw ipv4|ipv6 ...`; routes no static line writes are printed in
      announce blocks. `mcast-vpn`, `flow`, `flow-vpn`, `mup`, `sr-policy`, `vpls` pending.
- [ ] `exabgp decode --command` uses `render()`

### Phase 4: the rest of the families

- [x] flow (`match`, `then`, `scope`, the one-liner, `announce ipv4|ipv6 flow|flow-vpn`)
      (`grammar/types/flow.py`, `grammar/tree/flow.py`)
- [x] l2vpn / vpls, and `announce { l2vpn { vpls ...; } }` (`grammar/tree/l2vpn.py`)
- [x] mup, mvpn (`grammar/tree/select.py`)
- [x] sr-policy, static and announce (`grammar/tree/sr_policy.py`); printed from the sub-TLV
      objects, the TunnelEncap text is not configuration syntax
- [x] operational (`grammar/tree/operational.py`); `NeighborSettings.operational` carries the
      messages to `grammar/install.py`, which files them as `_init_neighbor` did
- [x] round trip over every `etc/exabgp/*.conf` and fixture (`test_roundtrip.py`), 112 files,
      none skipped

Exit: every configuration and every API command in the repository parses under both
parsers to the same result, and the coverage test reports no keyword without forms.

### Phase 5: complete, with both parsers (milestone commit)

- [x] default `exabgp_debug_parser` to `grammar` (`environment/config.py`); `Configuration.partial()`
      takes an explicit `parser` like `reload()`
- [x] `test_everything` passes with `grammar` as the default, and the differential suite
      passes with both
- [x] the CLI completer takes its hints and examples from `grammar/describe.py` (`route_help`);
      `cli/schema_bridge.py` is no longer used by the CLI and goes with the legacy parser
- [x] a unit test over the import graph: the grammar package imports nothing from the
      legacy modules (`test_imports.py`, direct imports: every exabgp module reaches
      `Configuration` through the reactor until phase 6 rewires it)
- [x] **freeze the legacy results**: for every input of 2.8 and every form of 2.9, store
      what the legacy parser produced (`to_dict()` JSON and the encoded UPDATE bytes, or
      "rejected") as golden fixtures under `tests/unit/configuration/forms/expected/`.
      Done as digests: `tests/unit/configuration/forms/expected/legacy.json` maps each of the
      5817 inputs (forms, documents, files, API commands) to a digest of its outcome
      (`config_grammar/frozen.py`, checked by `test_frozen.py`). A digest rather than
      `to_dict()` and UPDATE bytes: the outcome compared is the one of `compare.py`, and the
      whole file stays at 228 KB
      Once the legacy parser is gone the forms and differential tests compare against
      these files, so they keep proving the behaviour was preserved
- [x] commit, when Thomas asks: this commit holds both parsers and is the point to come
      back to if the removal shows a problem (95f03e1e3)

### Phase 6: remove the legacy parser and the switch

Gate: review section 7 (API side effects) with Thomas first. If it is not empty he may
decide to keep the legacy parser and the switch as a user choice for the API; this phase
is then replaced by documenting the switch and keeping both parsers tested.

Gate passed 2026-09-28: Thomas reviewed section 7 (errors are not an API; `schema export`
moves to the grammar's model; man pages at the end).

What outside the parser uses it (source scan, 15,490 lines to remove, 35 test files):

| user | uses | step |
|---|---|---|
| API dispatch (`reactor/api/dispatch/*`, `reactor/api`) | `core.parser.Tokeniser`, `core.format` | 6.1 move out of configuration/ |
| API `operational` command | `operational.parser` | 6.2 the grammar's OperationalLine |
| reactor loop, processes | `process.API_PREFIX` | 6.3 move the constant |
| `api.command.peer` | `neighbor.api` | 6.3 |
| `Configuration` | every section, the route scope | 6.4 grammar only |
| `schema export`, `configuration example` | `schema.py` | 6.5 from the model |
| `cli/command_schema.py`, `cli/schema_bridge.py` | `ValueType`, validators | 6.5 |
| tests | legacy internals | 6.6 port what proves behaviour (RFC markers), drop the rest |

- [x] 6.1 the API tokeniser and `formated` moved to `reactor/api/tokeniser.py`
- [x] 6.2 the API `operational` command reads through the grammar (`read.read_operational`),
      its expectations taken from the legacy parser (`tests/unit/test_api_operational_command.py`)
- [x] 6.3 `API_PREFIX` and the CLI processes in `configuration/cli_process.py`; the `peer`
      command flattens its api with `grammar.tree.resolve.api`
- [x] 6.4 `Configuration` reads with the grammar only (475 lines, was 922): `partial()` then
      `pop_routes()`, `open_sections` for a command leaving a section open (the API drops its
      routes, as before), `ConfigurationError` in place of the legacy `Error`
- [x] 6.5 `schema export` prints the grammar's JSON Schema; `configuration example` is
      generated from the grammar (`grammar/example.py`, a configuration which validates);
      `cli/command_schema.py` without `ValueType`; `cli/schema_bridge.py` deleted
- [x] delete `core/`, the `Parse*` / `Announce*` sections, the `*/parser.py` hand parsers,
      `schema.py`, `validator.py`, `validators.py`, `constraints.py`, `example.py`,
      `compare.py` (moved to the tests as `config_grammar/outcome.py`): 57 files
- [x] delete `exabgp_debug_parser` and `configuration validate --parser`
- [x] the grammar tests hold to the frozen results; `test_differential.py` goes (the frozen
      results cover every file), the lexer's legacy parity frozen as literal expectations
- [x] the other tests importing deleted modules: 23 ported where they prove behaviour (every
      RFC marker kept), 9 deleted which only tested legacy internals (schema, validators,
      constraints, action enums, the error collector, the old example generator, schema_bridge)
- [x] `needed` leaves (local-as, peer-as, role local, tcp-ao keyid/algorithm/password): the
      neighbor requires them in the model (JSON `required`, YANG `refine ... mandatory`), a
      template does not; `role` and `tcp-ao` are YANG presence containers
- [x] an error of a value inside a route is positioned once (it was `line 1:11: line 1:51:`)
- [x] `test_everything` passes (25/25)
- bug found and fixed: the Prefix-SID package (attribute/sr) did not register the SRv6 service
  TLVs, the legacy parser importing them did; a received SRv6 L3 service was shown as not
  implemented (qa decoding test M). `tests/unit/test_prefix_sid_srv6_registered.py`; every
  one of the 130 registering modules is now loaded by the daemon's entry points
- bug found and fixed: a failed reload left `Configuration.processes` with the processes read
  before the error (legacy) or none (grammar); the reactor then stopped every API program not
  in it. The configuration is now left as it was (`tests/unit/test_reload_keeps_processes.py`,
  which fails on 40c34c239)
- [x] `test_everything` passes
- [x] commit, when Thomas asks (b30698a1d)

### Phase 7: generated documentation

- [x] `exabgp configuration syntax [section ...] [--json]` (`application/syntax.py`)
- [x] man page and wiki reference pages generated: the syntax block of `exabgp.conf.5`
      between two markers (`qa/bin/update_man_syntax`, held by
      `tests/unit/test_man_configuration_syntax.py`), the prose kept by hand; the wiki page
      `Configuration/Syntax-Reference.md` generated whole (`qa/bin/update_wiki_syntax`),
      linked from the hand-written pages, committed in the wiki (50cf9c3), not pushed:
      Thomas publishes it
- [x] `.claude/exabgp/` codebase docs updated for the new package (`CONFIGURATION_GRAMMAR.md`)

---

## 4. Open decisions

1. ~~**Command name** for the generated syntax~~ Settled: `exabgp configuration syntax`
   (with `--json` and `--yang`).
2. ~~**Documentation source of truth.**~~ Settled 2026-09-29 by Thomas: the syntax block of
   `exabgp.conf.5` is generated, the prose sections stay written by hand; the wiki reference
   is generated too, and committed to the wiki repository for him to publish.
3. ~~**Switch name.**~~ Moot: the switch went with the legacy parser (b30698a1d).

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

Things the legacy parser accepts or rejects by accident, one line each. The grammar
reproduces each one (marked `legacy:` in `grammar/engine.py` and the types); whether to
drop any of them is a separate decision after phase 6, each with its own CHANGELOG entry.
Each is pinned by a form or document in `tests/unit/config_grammar/forms.py`.

| Accident | Example | Where reproduced |
|---|---|---|
| ~~words a value does not use are ignored~~ refused since 2026-10-01 (`plan/done-agent-reported-bugs.md` item 2) | `respawn false extra;` is `respawn false;` | engine `_leaf` |
| words before a `}` are ignored, even an unknown keyword | `process p { run /bin/cat; hold 1 }` | engine `read` |
| a `}` with nothing open ends the configuration, the rest is never read | `process p { ... } } anything {` | engine `read` |
| sections still open at the end of the text are closed | `process p { run /bin/cat;` | engine `read` |
| a section name is the word after the keyword, whatever it is, and more words are ignored | `process { ... }` is named `{`, `process a b {` is `a` | engine `_open` |
| process names are not checked | `process p$ { ... }` | engine `_open` |
| a boolean given no word takes the leaf default rather than true | `respawn;` | `Bool(bare=...)` |
| an opening quote does not end the word before it | `ab"cd"` is `abcd` | lexer `_quote` |
| inside quotes the other quote character switches which one closes, so a word can not hold a quote | `"it's"` never closes | lexer `_quote`, render `quote` |
| `validate()` failures are ignored: its result is only returned when true | `api { processes [ undefined ]; }` is accepted | `Configuration._reload_grammar` |
| templates override the neighbor: a number, address or string of the template replaces the neighbor's own | `inherit t; hold-time 30;` with `hold-time 60` in `t` is 60 | `resolve.transfer` |
| an `inherit` of a template which does not exist, or is defined further down, is ignored | `inherit nothing;` | `resolve.inherit` |
| `family { ipv4 unicast; all; }` is accepted and asks for every family; `add-path { all; }` asks for none | | `family._store_all` |
| a boolean given no word takes the leaf default, which is not the neighbor default | `adj-rib-in;` is false, no statement is true | `boolean(bare)` |
| `rate-limit` takes any integer, a negative one or 0 included, and not `disable` (which the printer writes) | `rate-limit -5;` | `integer('rate-limit')` |
| api names are unique across the whole configuration, not per neighbor | two neighbors with `api a { }` | `session._api` |
| a route line picks VPN or labelled from the word `rd`, `route-distinguisher` or `label` anywhere in the statement, a value included | `route ... name rd;` is built as a VPN route, then made unicast again | `static._mentions`, `static.normalize` |
| a prefix whose mask is no number is a host route | `route 10.0.0.0/x` is `10.0.0.0/32` | `bgp.Prefix` |
| `bgp-prefix-sid` skips the words it does not expect, and looped forever on a list never closed (the grammar refuses it) | `bgp-prefix-sid [ 300` hung the legacy parser | `bgp.PrefixSidType` |
| the announce families declare `atomic-aggregate`, `originator-id`, `cluster-list`, `aigp`, `attribute`, `name`, `split`, `watchdog`, `withdraw` and refuse every value of them (the validators return a bool, address, number or string where an attribute is needed; for an API command the exception leaves `partial()`) | `announce { ipv4 { unicast ... name x; } }` | `announce.Refused` |
| `path-information` is refused in an announce family: a number is no address, an address no path id | `unicast ... path-information 1` | `announce.Refused` |
| `labeled-unicast` is listed for `announce ipv4`/`ipv6` and refused as an unknown command | | `announce._refused_family` |
| `next-hop self` in an announce family is IPv4 whatever the family | `announce { ipv6 { unicast ... next-hop self; } }` | `announce.AnnounceNextHop` |
| a prefix of the other address family is taken, and builds a route no one can show | `announce { ipv4 { unicast 2001:db8::/48 ... } }` | `announce.AnnounceLine` |
| a file ending on a continuation line repeats its last piece | `run /bin/cat \` at EOF | lexer `_file_lines` |
| a `flow` section keeps the neighbor's list of routes, which the neighbor adds again: every route counts twice | `flow { route r { ... } }` | `flow._flow`, unresolve `_routes` |
| a trailing `&` in a flow match is refused inside brackets only | | `types/flow._expression` |
| IPv6-only flow components are accepted while the family is not set yet | | `types/flow` |
| a one-line flow `route-distinguisher` sets a field which does not exist and is refused | | `tree/flow.LINE` |
| an IPv6 `copy` next to another is dropped as a duplicate attribute | | `tree/flow.FlowRoute` |
| an attribute given in the `l2vpn` section goes to the last route read, a static one included, and fails when there is none | `l2vpn { vpls ...; origin igp; }` | `l2vpn._last_route` |
| the `l2vpn` section takes every route not yet taken, those read before it included | | `l2vpn._l2vpn` |
| a VPLS value given at the `l2vpn` level is refused | `l2vpn { endpoint 5; }` | `l2vpn._NoSetter` |
| the MUP `next-hop self` takes the family of the context; an IPv4 next-hop is mapped into IPv6 for an IPv6 route, which carries no next-hop attribute | | `select.MupNextHop` |
| an sr-policy route ignores what follows its sub-TLVs | `sr-policy ... preference 1 garbage words;` | `sr_policy.sr_policy_route` |
| the static `sr-policy` takes its family from the endpoint, IPv4 when it has none | | `sr_policy._endpoint_afi` |
| an operational message reads exactly two words per value and ignores the rest; `router-id` takes the place of a value, so it is never accepted | `rpcq afi ipv4 safi unicast router-id 1.2.3.4 sequence 5;` is refused | `operational._values` |
| the advisory of an operational message is not checked against its maximum length | | `operational.CONVERT` |
| a sequence may be negative, and 0 is no sequence | `sequence -1;` | `operational.CONVERT` |
| a second `operational` block replaces the messages of the first, unless it is empty | | `operational._operational` |
| a template's operational messages are added after the neighbor's own | | `resolve.transfer` |

---

## 7. API side effects

Anything an API program would see differently under the grammar parser, one line each,
with the command, the old behaviour, the new behaviour and why the new one cannot match.
Covers the text commands going through `Configuration.partial()` (`announce`,
`withdraw`, `group`, ...), the replies and error messages returned to the program, and
anything printed from `render()` that the API emits (`show neighbor configuration`, ...).

Preserving behaviour means this list should stay empty; an entry is a failure to preserve
that could not be avoided. It decides the phase 6 gate.

- bug found, not a parser one: `Resource.__new__` caches instances by value, so every
  `NetMask` of one length is one object, and `make_netmask` sets `maximum` on it. An IPv6
  `/32` prefix makes the IPv4 peer's `/32` count 2**96 addresses: an IPv4 neighbor with an
  IPv6 `/32` route is refused "can only use ip ranges for the peer address with passive
  neighbors". The host-bit check of prefixes can be wrong the same way. Both parsers go
  through it; pinned as NETMASK_DOCUMENT_BODY in the forms. Fixed in 01e92cdf9, with
  `tests/unit/test_netmask_family.py`.
- configuration errors: the grammar positions an error as `<file>:<line>:<column>: <message>`
  (`line <line>:<column>:` for text), where the legacy parser wrote `line <line>: <the
  statement>` and named the section (`neighbor/flow/route`). Some messages are worded
  differently too (`'jsn' is not a valid encoder`). Tests which checked the legacy form now
  accept either (`test_configuration_error_line.py` checks each parser's own).
  Thomas: the error text is not an API we provide, the change stands. Idea for later: a
  JSON output for configuration errors (position, message, expected words), which
  `ConfigError` already holds
- `exabgp schema export` still prints the legacy schema; `exabgp configuration syntax --json`
  prints the grammar's. Switching `schema export` changes its output. The differences:
  - layout: the legacy schema lists every section at the top (`capability`, `family`,
    `static`, `flow`, ... beside `neighbor`), flattens a flow route (`match`/`then` values
    straight under `route`) and puts route values straight under `static`; the grammar
    nests each section where it is written, `neighbor` a list, `process` by name
  - coverage: the grammar has 155 paths the legacy schema lacks (the `announce` families,
    `api` send/receive, `add-path`, `tcp-ao`, `nexthop`, `l2vpn` values, `match`/`then`/
    `scope`, sr-policy, mup, mcast-vpn); nothing of the legacy one is missing
  - leaf types: the legacy schema is richer. It gives integers with ranges (`hold-time`
    0-65535, `med`), formats (`ip-address`), enums, booleans, defaults, `required` and
    `additionalProperties: false`. The grammar types mostly fall back to `{"type": "string"}`
    (only `Choice` and a few override `json_schema()`), give no default or `required`, and
    a route value written through a `store` callback shows as an array
  - header: no `$schema`, `$id` or `title` in the grammar's
  Before `schema export` switches: `json_schema()` on every type (ranges, enums, formats),
  defaults and mandatory leaves from the Leaf, `additionalProperties: false`, the header,
  and a repeated-or-not flag that is not inferred from `store`
- candidate, not done: `str(neighbor)` from `render()` would change the text of
  `show neighbor configuration`. Today's printer writes `rate-limit disable`, which neither
  parser reads back.
- man pages: updated from `exabgp configuration syntax` once the work is done (Thomas)

---

## Progress

- 2026-09-27: phase 0 started
  - `grammar/`: lexer (legacy words, physical positions), error, words, types (base,
    `Bool`, `Choice`, `Program`), nodes (`Leaf`, `Block`), engine, render, read
  - `process` declared (`tree/process.py`), `ProcessSettings`, `Encoder`, `OnExit` in
    `configuration/settings.py`; `Configuration.from_settings` takes `ProcessSettings`
  - program lookup and checks moved to `util/program.py`, used by both parsers
  - `configuration/compare.py` and `configuration validate --parser legacy|grammar|both`
  - tests in `tests/unit/config_grammar/`: lexer parity with the legacy tokeniser over
    every example configuration, forms (generated and hand written), documents,
    differential over every `etc/exabgp/*.conf` and fixture, round trip through both
    parsers; mutating the grammar (dropping a boolean spelling, a default, an accident)
    turns them red
  - legacy error line fixed: it named the statement count (`tests/unit/test_configuration_error_line.py`)
- 2026-09-28: phase 3 announce sections (ipv4/ipv6 unicast, multicast, nlri-mpls, mpls-vpn,
  rtc; static rtc; API ipv4/ipv6 commands); 5957 grammar tests
- 2026-09-28: phase 3 static routes: every static route value as a type, `static` section,
  API route commands; all `etc/exabgp/*.conf` without flow/l2vpn/announce/sr-policy
  compared (22 skipped), 4400+ grammar tests
- 2026-09-28: switch `exabgp_debug_parser=grammar` (`Configuration.reload(parser)`,
  `_reload_grammar` commits the same way as the legacy reload); phase 1 (neighbor, template
  and their sections) done but for the printer switch; 3309 grammar tests, every
  `etc/exabgp/*.conf` without routes compared (66 skipped for static/flow/l2vpn/operational)

- 2026-09-27: survey done, design agreed (new package, bind to Settings), plan written
- 2026-09-27: preserve behaviour, both parsers must agree, forms corpus for every valid
  form
- 2026-09-27: both parsers only during development; commit complete work with both, then
  remove the legacy parser and the switch
- 2026-09-27: if the API changed as a side effect, keeping the legacy parser as a user
  choice is decided at the end (section 7, phase 6 gate)

- 2026-09-28: phase 4 complete: flow, l2vpn, mup, mvpn, sr-policy, operational; no keyword is
  pending, `NotMigrated` is never raised by the tree any more. 8500+ grammar tests; every
  `etc/exabgp/*.conf` and fixture reads the same with both parsers and prints back to a
  configuration both parsers read the same. `compare` now also compares the sequence and
  router-id of operational messages, which their text leaves out

- 2026-09-28: phase 5 and 7 work: grammar is the default parser; frozen legacy results;
  import test; `describe.py` (syntax, keyword help, JSON schema) behind the CLI completer
  and `exabgp configuration syntax`; `CONFIGURATION_GRAMMAR.md`. Under the grammar default,
  14 unit tests failed on error wording and position format: wording aligned with the
  legacy messages (prefix-limit, source-interface), position tests made parser-aware
- phase 7 left: the man page syntax block and the wiki pages are to be generated from
  `exabgp configuration syntax` and reviewed by Thomas (the hand written block has errors,
  `rate-limit <enable | disable>` where a number is read)

- 2026-09-28: naming pass over the grammar package (asked by Thomas): one name per concept
  (`family` is only a FamilyTuple, `afi_keyword`/`safi_keyword` for spellings, `values`
  for the neighbor values rather than the legacy `local`, `nexthop`, `word` for converter
  arguments, `_store_<what>` callbacks), duplicated helpers shared (`Words.expect`,
  `static.action`, `static.store_routes`, `MAX_ROUTE_VALUES`, `error.ROUTE_ERRORS`,
  `INDENT`). Conventions written in `.claude/exabgp/CONFIGURATION_GRAMMAR.md`. Left as
  they are: `Statement.words` (tokens, not words), the `...Type` suffix of some value
  types in `types/bgp.py`, the context key constants (no common scheme yet)

- 2026-09-28: data model (asked by Thomas: typed JSON Schema, a base class carrying the
  constraint, exposable as YANG). `grammar/shape.py` is a YANG-aligned model every type
  returns from `shape()`; `json_schema.py` and `yang.py` print it; `describe.model()` builds
  it from the tree (a statement and a section of one keyword are one list node; the section
  shared by neighbor and template neighbor is one grouping / `$defs` entry). `Number`
  declares a range once. `UnsignedAttribute` (MED, LOCAL_PREF) derives its range from its
  width. `exabgp configuration syntax --yang`. Bug found and fixed: `PathInfo.make_from_integer`
  kept the low 32 bits, `path-information 4294967296` was path 0 (both parsers);
  `tests/unit/test_path_info_range.py`. Open: the JSON Schema is 395 KB, the route values are
  repeated for each announce family; identical containers could share one `$defs` entry

- 2026-09-28, committed after the plan was last written: phase 5 (95f03e1e3), the data model
  (40c34c239), phase 6 (b30698a1d, 57 files, the switch and `configuration validate --parser`
  removed). Then, outside the phases: route refresh and enhanced route refresh configured
  apart (edfcc782b), typed contexts shared by reading and printing (5c699fc6e), `Section` and
  `Store` (c6741b655), `Collector` (ecbaaff25), `Configuration.serialise()` (b531b4f5c),
  `RouteStatement` (580a5c372), `Target` (ddc65f51b), the 256 route values bound (bfe9efc80).
- 2026-09-29: Thomas asked to complete the plan: the JSON Schema shares identical containers
  (it was 509 KB), the man page syntax block and the wiki reference generated.
  - JSON Schema: `json_schema.share` moves every container of 256 octets or more which comes
    out the same in several places to `$defs`, the largest first: 509 KB -> 174 KB. The
    document is built once per section (`describe._json_document`, cached): sharing costs
    0.13 s, and the tests build it hundreds of times.
  - YANG: `yang.share` makes a grouping of a repeated container body, and of a repeated list
    member whole; a list key stays in the list: 261 KB -> 97 KB.
  - Both tests went red with sharing disabled. The first version of the YANG test read the
    module's own threshold, so raising it switched both off and the test stayed green: each
    test now has its own number.
  - Man page: the block printed from the grammar, a note too wide put above its statement,
    a statement too wide carried on indented lines (at a space, or after a `|`). The old
    block had `rate-limit <enable | disable>` and `encoding`; `mandoc -T lint` reports
    nothing new. The grammar's `a ipv4 family` became `an ipv4 family`.

## Failures

(none yet)

## Blockers

(none)

## Resume Point

Complete. Phases 0 to 7 done; the wiki commit (50cf9c3 in the wiki repository) waits for
Thomas to push it. The naming items left as they were (`Statement.words`, the `...Type`
suffix, the context key constants) stay a deliberate choice, not work owed.

The survey script used for section 1:

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
