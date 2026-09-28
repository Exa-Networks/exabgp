# Configuration grammar

**Read when:** adding or changing a configuration keyword, an API route command, or
anything printed back as configuration.

The configuration is declared once, in `src/exabgp/configuration/grammar/`. The parser,
the errors, the printer (`render`), the syntax help (`exabgp configuration syntax`), the
JSON schema and the CLI completion hints all come from that one declaration.

It replaced the legacy parser (`configuration/core`, `static/`, `flow/`, `neighbor/`, ...),
removed once every configuration and API command read the same with both; see
`plan/wip-config-grammar.md`. The API command tokeniser is `reactor/api/tokeniser.py`.

---

## Layout

| File | Role |
|---|---|
| `lexer.py` | positioned tokens, the legacy quoting and continuation rules included |
| `words.py` | `Words`: the words of one statement, `peek`/`word`/`rest`, and the read `context` |
| `context.py` | `ReadContext`, `PrintContext`: what one read, or one print, keeps across its statements |
| `section.py` | the base classes of the code a tree runs: `Section` (a block) and `Store` (a statement) |
| `error.py` | `ConfigError(where, message, expected)`, `file:line:column: message` |
| `types/` | value types: `parse`, `render`, `hint`, `examples`, `choices`, `json_schema` |
| `nodes.py` | `Leaf` (keyword value;) and `Block` (keyword [name] { ... }) |
| `engine.py` | reads statements into a tree of values, calls each block's `section` |
| `render.py` | prints built values back as configuration (the inverse of `engine`) |
| `shape.py` | the data model: what a value is once read (a MED is a uint32), YANG-aligned |
| `json_schema.py`, `yang.py` | the JSON Schema and the YANG module, printed from the model |
| `describe.py` | syntax lines, keyword help, the model of the tree (`model()`) |
| `read.py` | `read_text`, `read_file`, `read_command` (API route commands) |
| `install.py` | makes the Neighbor objects from `NeighborSettings`, as the legacy post did |
| `tree/` | the declaration: `root`, `process`, `neighbor`, `family`, `session`, `static`, `announce`, `flow`, `l2vpn`, `select` (MUP, MVPN), `sr_policy`, `operational` |
| `tree/codecs.py` | the parts of a neighbor, a `Codec` each: `neighbor_settings` and `neighbor_values` |
| `tree/resolve.py` | template inheritance (`transfer`) and the rules values → `NeighborSettings` |
| `tree/unresolve.py` | the rules `NeighborSettings` → values, for printing |

## Names

One concept, one name, in every file of the package:

| Name | Is |
|---|---|
| `words` | the `Words` of a statement (a printed `list[str]` in the `*_words` printers) |
| `word` | one word, the argument of every converter |
| `where` | a position, from `words.where()` |
| `keyword` | the first word of a statement |
| `values` | the values of a block, by field (the neighbor ones too) |
| `context` | the `ReadContext` shared by the whole read, or the `PrintContext` of a print |
| `family` | an `(AFI, SAFI)` tuple, never anything else |
| `afi`, `safi` | an `AFI`, a `SAFI` |
| `afi_keyword`, `safi_keyword` | their configuration spelling, `ipv4`, `unicast` |
| `nexthop` | a next-hop (`Route.nexthop`), also in helper names: `_nexthop`, `FLOW_NEXTHOP` |
| `neighbor_capability` | a `NeighborCapability` |
| `route`, `routes`, `nlri`, `attributes`, `settings` | as in the rest of exabgp |

Helpers: a statement type is `<Thing>Line`; a printer is `<thing>_words(route)`; the
section of a block is `<Keyword>Section` (`FlowSection`, `VPLSSection`); a store is
`<What>Store` (`RoutesStore`, `AnnouncedStore`, `LastRouteStore`); a count bound is
`MAX_<THINGS>`, a value ceiling `<THING>_MAX`. Shared helpers: `Words.expect`,
`static.action`, `static.ROUTES`, `types.route.MAX_ROUTE_VALUES`, `error.ROUTE_ERRORS`,
`render.INDENT`.

## The code a tree runs

A tree is declared, the little code it runs has a base class each (`section.py`), so every
implementation is a subclass an editor or `__subclasses__()` finds:

| Base | Runs | Default |
|---|---|---|
| `Type[T]` (`types/base.py`) | reads and prints the value of a statement | none, abstract |
| `RouteStatement` (`types/route.py`) | a `Type` reading routes: `keywords` walks its `<keyword> <value>` pairs, `printed` writes one route | none, abstract |
| `Section[T]` | `opened`, `finish`, `build` a block into a `T`, `unbuild` it to print | `KEPT`: the values as they are |
| `Store` | `keep`s the value of a statement, when it is not simply set or added to a list | `Leaf.collect` |
| `Collector[T]` | a `Section` using its statements together, in order, when it closes: `collected` | its leaves use `Pending` |
| `Codec` | one part of a neighbor: `resolve` its fields into `NeighborSettings`, `unresolve` them back | none, abstract |

Sections and stores keep no state: what a statement tells another block goes through the
`ReadContext`. `test_sections.py` holds the tree to it: every block runs a `Section`, every
section and store is used, and a block building a Settings dataclass has a field for each leaf.
`test_codecs.py` holds the neighbor to its codecs: each field has one owner, which prints only it.

`Configuration.serialise()` prints what a configuration was made from, routes aside, with the
same printer: it reads back equal (`test_serialise.py`, every configuration of the repository).
`str(neighbor)` is a display, it does not read back.

## The data model

Every type says what its value is with `shape()`: the value exabgp keeps and prints, not the
spellings it accepts (`1.1` is the AS number 65537, `enable` is `true`). The model follows
YANG, so both `exabgp configuration syntax --json` and `--yang` are printed from it.

A number is a `Number` (`types/word.py`) declaring its ranges once; the check, the hint, the
examples and the model come from them. Where the range belongs to the wire format it is taken
from the class which packs it: `MED.MAX` and `LocalPreference.MAX` come from `WIDTH = 4` of
`UnsignedAttribute`, `PathInfo.MAX` from its four octets. `test_model.py` checks every
`Number` reads its bounds and refuses what is past them.

A statement given several times (a route, a family) says so with `Leaf(multiple=True)`; a
`Store` alone does not make a value a list.

## Adding a keyword

1. Find the `Block` it belongs to (`exabgp configuration syntax <section>` shows it).
2. Give it a type: reuse one of `types/` or write a `Type` with `parse` (raise
   `ConfigError` at `words.where()`), `render` (the words `parse` reads back), `hint`,
   and `examples` (every spelling, used by the forms tests).
3. Add the `Leaf(keyword, type, field=...)`; `collect`, or a `Store` subclass, when it is
   not a plain set; `default`, `mandatory`, `doc`.
4. Make it reach the Settings: the `build` of the block's `Section`, or `tree/resolve.py`
   for a neighbor.
5. Make it print back: `tree/unresolve.py` for a neighbor value, through the codec owning it.
6. Add forms in `tests/unit/config_grammar/forms*.py`: one accepted and one refused per
   keyword are enforced by `test_forms.py`.

Whether each form is accepted was recorded against the legacy parser, and what every input
made is frozen (`tests/unit/configuration/forms/expected/legacy.json`, `test_frozen.py`). A
change of behaviour, even of an accidental one, is a decision: it changes the frozen results,
and the commit says so. The accidents the grammar reproduces are listed in the plan.

## Tests

| Test | Proves |
|---|---|
| `test_forms.py` | every form and document is accepted or refused as the legacy parser did |
| `test_frozen.py` | every form, document, `etc/exabgp/*.conf`, fixture and API command of `qa/*/*.ci` makes what the legacy parser made (`config_grammar/frozen.py`) |
| `test_roundtrip.py` | printed configuration reads back equal |
| `test_model.py` | the data model: every Number reads its bounds, no number is a string, JSON Schema and YANG well formed |
| `test_imports.py` | the grammar imports no configuration module but its own and settings |
| `test_describe.py` | the syntax help and schema cover every keyword |

Regenerate the frozen results only for a change of behaviour made on purpose:

```bash
cd tests/unit && env exabgp_log_enable=false ../../.venv/bin/python -m config_grammar.frozen
```
