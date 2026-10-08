# Configuration grammar: what was left after the plan was closed

**Status:** 🚧 In progress
**Created:** 2026-10-08
**Last Updated:** 2026-10-08
**Follows:** `plan/done-config-grammar.md` (closed 2026-09-29 with these items still open)

## Goal

The grammar exists so the configuration documents itself and the user gets good help. These
are the items the first plan left open, re-checked against the code on 2026-10-08.

## Measured state, 2026-10-08

Done and verified: legacy parser gone; `exabgp configuration syntax [section] [--json|--yang]`;
`schema export` prints the grammar's JSON Schema (header, `required`, `additionalProperties`,
defaults; 424 leaves typed with range, enum or pattern); errors carry `file:line:column`,
`did you mean`, `expected`; man page and wiki syntax pass `--check`, the wiki commit is pushed.

## Items

| # | Item | Status |
|---|---|---|
| 1 | `configuration syntax <section> <keyword>` gives the help of one keyword (syntax, doc, default, examples) | ✅ |
| 1b | "may be repeated" was said of ~100 statements a second one replaces or which are refused twice | ✅ |
| 1c | `manual()` left a too-wide statement unwrapped when it had no note | ✅ |
| 2 | ~~`role` and `tcp-ao` sections have no description in the model~~ not an issue: the description is in `$defs/neighbor`, the probe read the neighbor's `required` overlay | ✅ |
| 3 | `rate-limit disable` refused, which 5.0 read and `str(neighbor)` prints | ✅ |
| 4 | `exabgp decode --command` builds API text by hand (`configuration/command.py`), not with `render()` | ⏳ |
| 5 | ~~31 leaves are a plain `string`~~ the probe missed `anyOf` formats: addresses are typed; 15 free text strings left (description, passwords, names, run). Possible: `maxLength` on host-name, domain-name, md5-password, advisory | 🟢 optional |
| 6 | a configuration error is printed twice by `configuration validate` (log and `error:` line) | ⏳ |
| 6b | an error names an internal code: `split` given twice says `attribute 0xfffd is given twice` | ⏳ |
| 7 | decisions: the accidents of `done-config-grammar.md` section 6, `tree/resolve.py` legacy inheritance, JSON output of configuration errors | ⏸️ Thomas |

## Decisions

- 2026-10-08: order agreed with Thomas: 1, 2, then 3; the plan file first.
- 2026-10-08: "may be repeated" means each statement adds to the value (a list in the model,
  `Leaf.many`, or `Leaf.adds` for a statement whose value is a list made longer: communities,
  flow rules, flow actions carried as extended communities). A statement whose second value
  replaces the first says nothing. Before, it was `Leaf.repeated`, a printer property.
- 2026-10-08: `rate-limit disable|disabled` (any case) reads as 0, as in 5.0. 5.0 refused 0
  itself; main keeps accepting it. The accident "rate-limit takes any integer, a negative one
  included" of done-config-grammar.md section 6 was already gone: a negative is refused.

## Progress

- 2026-10-08, item 1: `describe.locate`, `statement_help`, `statement_schema`; `application/syntax.py`
  prints the help of a statement, `--json` its schema, `--yang` refused for a statement.
  Tests in `tests/unit/config_grammar/test_describe.py`: every declared statement has a help;
  `test_may_be_repeated_is_said_of_a_statement_which_adds` reads every statement twice and
  checks the note against what happened (42 red before the fix; 116 skipped, they have fewer
  than two spellings reading to different values, so adding can not be told from replacing).
- 2026-10-08, item 3: `types/network.RATE_LIMIT`; `tests/unit/test_rate_limit_disable.py`
  (4 red before); forms flipped, frozen results regenerated (2 changed, 6 new, only rate-limit);
  man page and wiki Syntax-Reference regenerated (the wiki not committed, Thomas publishes).

## Failures

(none yet)

## Blockers

(none)

## Resume Point

Items 1, 2, 3 done; `test_everything` passed (28/28, 2026-10-08). Next: 4 (`decode --command` from `render()`),
6, 6b; 7 waits on Thomas.
