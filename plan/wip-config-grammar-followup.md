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
| 4 | `exabgp decode --command` builds API text by hand (`configuration/command.py`), not with `render()` | ✅ |
| 5 | ~~31 leaves are a plain `string`~~ the probe missed `anyOf` formats: addresses are typed; 15 free text strings left (description, passwords, names, run). Possible: `maxLength` on host-name, domain-name, md5-password, advisory | 🟢 optional |
| 6 | a configuration error is printed twice by `configuration validate` (log and `error:` line) | ✅ |
| 6b | an error names an internal code: `split` given twice says `attribute 0xfffd is given twice` | ✅ |
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

- 2026-10-08, item 6: `application/validate._fail` logs the error only where the log does not
  print to the terminal (stdout/stderr) the `error:` line already goes to; that line stays
  whatever the log (#1367). An error carrying `file:line:column` is no longer prefixed with the
  file a second time; file-not-found goes through `_fail` too.
  `tests/unit/test_validate_says_an_error_once.py` (4 red before).
- 2026-10-08, item 6b: `tree/static.INTERNAL_KEYWORDS` names `split` and `withdraw` in the
  given-twice message. `tests/unit/config_grammar/test_given_twice.py` reads every statement
  twice: a refusal names a statement of the block or of a route (8 red before).
  Left as is: `attribute [ 0x20 ... ]` twice in vpls is called `large-community`, the
  attribute's own keyword, which vpls does not have as a statement.

### Item 4: what the prototype found (2026-10-08)

Prototype (scratchpad, not in the tree): UPDATE -> `UpdateCollection.announces/withdraws` ->
`Route` -> the statement of the API section which reads it (`STATIC route|attributes`,
`IPV4/IPV6 <safi>`, `L2VPN vpls`, chosen as `unresolve.routes` chooses) -> its `printed(route)`.
Over the 414 `raw:` lines of `qa/*.ci`: 236 round-trip at first, 257 once the attributes the
wire adds by default (`AttributeCollection._default_attributes`: origin igp, the default
as-path, local-preference 100 inside the AS) are left out. The other 52:

- the round trip encodes with `qa/bin/test_api_encode`'s `encode_api_command`, ~800 lines
  which rebuild a configuration from the command words by hand: it drops what it does not
  know without a word. `announce ipv4 flow ... extended-community [ 0x8006000000000000 ]`,
  `... rate-limit 0`, `... community "[" 1:1 "]"` encode as if the value was not there,
  while the grammar (`read_command`) reads each correctly. Today's 411/411 compares one
  hand-written translator with another.
- 🐛 `SelectLine.printed` (mup, mcast-vpn) writes `origin`, `as-path`, `local-preference`,
  which its reader refuses (5.0 refuses them too): printed words which do not read back.
- the flow line prints `[` `]` as words, quoted `"["`: they read back, but look wrong.
- several routes in one UPDATE: `group announce A ; announce B` does not encode to one
  UPDATE with the qa encoder; the old decoder wrote `announce attributes ... nlri A B`.
- extended communities are printed as hex by `one_attribute_words` (on purpose, for the
  configuration printer); `decode --command` printed `[rate-limit:0]`, easier to read.

### Item 4: steps (approved by Thomas 2026-10-08)

1. `qa/bin/test_api_encode`: `encode_api_command` reads the command with the grammar
   (`read_command`, the reactor's sections) and packs the routes as one UPDATE, instead of
   rebuilding a configuration. Verify: `./qa/bin/test_api_encode` and `--self-check`, any
   change in pass/fail explained line by line.
2. Grammar printers: `SelectLine.printed` refuses (Unprintable) an attribute its reader
   refuses; the flow line writes its brackets as `Syntax`. Tests that print then read back.
3. `configuration/command.py` rewritten on the grammar printers (the prototype), default
   attributes left out, several routes of one UPDATE as one `attributes ... nlri ...` or
   `group`. Same signature. Verify: `--self-check`, the decode tests.
4. Remove what is left unused (the JSON formatters of command.py, the `format_*` copies in
   test_api_encode); update `tests/unit/test_decode_to_api_command_*.py`.
5. `./qa/bin/test_everything`.

- 2026-10-08, item 4 step 1: `test_api_encode.encode_api_command` reads a command with the
  reactor's parser (`group._parse_routes`) and sends the routes through the neighbor's
  outgoing RIB, as the reactor does; ~1200 lines of hand translation removed. 34 `cmd:` lines
  were commands the API refuses (`extended-community [rate-limit:0]`, `ipv4 flow ... rd`,
  `next-hop` on a flow withdrawal), written by the old decoder, read only by the old encoder:
  rewritten with the flow keywords (`rate-limit 0`, `redirect 65001:119`, `flow-vpn`).
  Verify mode 385/0/42 as before. The 30 frozen inputs they were all read `rejected`; their
  replacements are accepted (frozen results regenerated).
- 2026-10-08, item 4 step 2: `SelectLine.printed` refuses an attribute no statement of the
  line reads; flow communities print their brackets as syntax. `tests/unit/config_grammar/
  test_printed_reads_back.py` (2 red before, run against a copy of src without the fix).

- 2026-10-08, item 4 step 3: `configuration/command.py` rewritten (926 -> ~130 lines): the
  UPDATE's routes printed by the statement of the API section which reads each back
  (`_place`, as `unresolve.routes` chooses), the attributes sent anyway left out, routes
  differing by prefix only as `announce attributes ... nlri ...`, others as `group`, an
  End-of-RIB as `announce eor`, a flow with a next-hop as the `flow` route block on one line
  (`render.one_line`). The `generic` argument is gone (an unknown attribute prints as
  `attribute [ ... ]` whatever). Extended communities print as their text where it reads back
  to the same bytes (`static.community_word`), flow traffic actions as their statement
  (`flow.traffic_action`: `rate-limit 0`, `redirect 65000:1`, `mark 10`, `interface-set`
  in the `scope` block). Self-check 414/0/13 (was 411/0/16: the three `No cmd` vectors,
  all blamed on the old encoder, now round-trip); verify 388/0/39.
- 🐛 found by the new tests: `rtc_words` printed the next-hop twice and `route-target
  target:<rt>`; a withdrawn sr-policy printed `next-hop no-nexthop`, and its reader required a
  next-hop on a withdrawal. Fixed (3 red before, against a copy of src without the fix).
- Limit, documented in `decode_to_api_command`: the reactor packs several routes in one UPDATE
  only for ipv4 unicast and mcast-vpn announcements (`rib/outgoing._select_updates`), so a
  `group` of other routes is sent as several UPDATEs of the same routes.
- 2026-10-08, item 4 step 4: the formatters left in test_api_encode removed (~2300 -> ~900
  lines), `tests/unit/test_decode_to_api_command_paths.py` (stubs of the old internals)
  replaced by `tests/unit/test_decode_to_api_command.py`, the SR-Policy `--command` tests check
  the command reads back.

- 2026-10-08, after the push (f0b717c6b): a security review found that a `group` line was
  split on every `;` (reactor/api/command/group.group_inline): a quoted word holding one,
  such as an SR policy name a peer chose and `decode --command` printed, became a command of
  its own (`policy-name "x ; withdraw route 10.0.0.0/8 ; y"`), and a flow route block in a
  group was cut at its statements. `lexer.split_commands` ends a command where the lexer ends
  a statement (outside quotes and braces, escapes resolved); group_inline and test_api_encode
  use it. Tests: `tests/unit/test_group_split_commands.py`, two in
  `test_api_command_group.py` (red before), one end to end in `test_decode_to_api_command.py`.

## Failures

(none yet)

## Blockers

(none)

## Resume Point

Items 1, 2, 3 committed (f582eec21); 6, 6b and 4 done, not committed. Running
`test_everything`. Left: 5 (optional), 7 waits on Thomas.
