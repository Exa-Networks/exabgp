# Configuration grammar

**Read when:** adding or changing a configuration keyword, an API route command, or
anything printed back as configuration.

The configuration is declared once, in `src/exabgp/configuration/grammar/`. The parser,
the errors, the printer (`render`), the syntax help (`exabgp configuration syntax`), the
JSON schema and the CLI completion hints all come from that one declaration.

The legacy parser (`configuration/core`, `static/`, `flow/`, `neighbor/`, ...) still exists
beside it; `exabgp_debug_parser=legacy` selects it. The grammar is the default. See
`plan/wip-config-grammar.md` for the migration and the removal of the legacy parser.

---

## Layout

| File | Role |
|---|---|
| `lexer.py` | positioned tokens, the legacy quoting and continuation rules included |
| `words.py` | `Words`: the words of one statement, `peek`/`word`/`rest`, and the read `context` |
| `error.py` | `ConfigError(where, message, expected)`, `file:line:column: message` |
| `types/` | value types: `parse`, `render`, `hint`, `examples`, `choices`, `json_schema` |
| `nodes.py` | `Leaf` (keyword value;) and `Block` (keyword [name] { ... }) |
| `engine.py` | reads statements into a tree of values, calls each block's `build` |
| `render.py` | prints built values back as configuration (the inverse of `engine`) |
| `shape.py` | the data model: what a value is once read (a MED is a uint32), YANG-aligned |
| `json_schema.py`, `yang.py` | the JSON Schema and the YANG module, printed from the model |
| `describe.py` | syntax lines, keyword help, the model of the tree (`model()`) |
| `read.py` | `read_text`, `read_file`, `read_command` (API route commands) |
| `install.py` | makes the Neighbor objects from `NeighborSettings`, as the legacy post did |
| `tree/` | the declaration: `root`, `process`, `neighbor`, `family`, `session`, `static`, `announce`, `flow`, `l2vpn`, `select` (MUP, MVPN), `sr_policy`, `operational` |
| `tree/resolve.py` | template inheritance (`transfer`) and values → `NeighborSettings` |
| `tree/unresolve.py` | `NeighborSettings` → values, for printing |

## Names

One concept, one name, in every file of the package:

| Name | Is |
|---|---|
| `words` | the `Words` of a statement (a printed `list[str]` in the `*_words` printers) |
| `word` | one word, the argument of every converter |
| `where` | a position, from `words.where()` |
| `keyword` | the first word of a statement |
| `values` | the values of a block, by field (the neighbor ones too) |
| `context` | the dict shared by the whole read |
| `family` | an `(AFI, SAFI)` tuple, never anything else |
| `afi`, `safi` | an `AFI`, a `SAFI` |
| `afi_keyword`, `safi_keyword` | their configuration spelling, `ipv4`, `unicast` |
| `nexthop` | a next-hop (`Route.nexthop`), also in helper names: `_nexthop`, `FLOW_NEXTHOP` |
| `neighbor_capability` | a `NeighborCapability` |
| `route`, `routes`, `nlri`, `attributes`, `settings` | as in the rest of exabgp |

Helpers: a statement type is `<Thing>Line`; a printer is `<thing>_words(route)`; a block
builder is named after its keyword (`_flow`, `_vpls`); a `store` callback is
`_store_<what>` (`store_routes`, `_store_announced`, `_store_op`); a count bound is
`MAX_<THINGS>`, a value ceiling `<THING>_MAX`. Shared helpers: `Words.expect`,
`static.action`, `static.store_routes`, `static.MAX_ROUTE_VALUES`, `error.ROUTE_ERRORS`,
`render.INDENT`.

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
`store` callback alone does not make a value a list.


1. Find the `Block` it belongs to (`exabgp configuration syntax <section>` shows it).
2. Give it a type: reuse one of `types/` or write a `Type` with `parse` (raise
   `ConfigError` at `words.where()`), `render` (the words `parse` reads back), `hint`,
   and `examples` (every spelling, used by the forms tests).
3. Add the `Leaf(keyword, type, field=...)`; `collect` or `store` when it is not a plain
   set; `default`, `mandatory`, `doc`.
4. Make it reach the Settings: the block's `build`, or `tree/resolve.py` for a neighbor.
5. Make it print back: `tree/unresolve.py` for a neighbor value.
6. Add forms in `tests/unit/config_grammar/forms*.py`: one accepted and one refused per
   keyword are enforced by `test_forms.py`.

While the legacy parser exists every form is read by both parsers and must give the same
result (`configuration/compare.py`). A difference in behaviour, even an accidental one,
is reproduced and listed in the plan's accidents table.

## Tests

| Test | Proves |
|---|---|
| `test_forms.py` | every form and document reads the same with both parsers |
| `test_differential.py` | every `etc/exabgp/*.conf` and fixture reads the same |
| `test_commands.py` | every API route command of `qa/*/*.ci` reads the same |
| `test_roundtrip.py` | printed configuration reads back equal, with either parser |
| `test_frozen.py` | the grammar matches the frozen legacy results (`config_grammar/frozen.py`) |
| `test_imports.py` | the grammar imports nothing of the legacy parser |
| `test_describe.py` | the syntax help and schema cover every keyword |

Regenerate the frozen results, only while the legacy parser exists:

```bash
cd tests/unit && env exabgp_log_enable=false ../../.venv/bin/python -m config_grammar.frozen
```
