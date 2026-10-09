# Configuration quirks: the legacy accidents the grammar still reproduces

**Status:** 🚧 In progress
**Created:** 2026-10-09
**Last Updated:** 2026-10-09
**Follows:** `plan/wip-config-grammar-followup.md` item 7, and section 6 of
`plan/done-config-grammar.md`, which lists each accident

## Goal

The grammar reproduced what the legacy parser accepted or refused by accident, so that the
switch changed nothing. Thomas decided on 2026-10-09 what becomes of them:

- a template gives defaults which the neighbor changes: the neighbor's own value wins over the
  template's, without a warning, and the documentation, CHANGELOG and wiki say so
- an `inherit` of a template which does not exist is a warning
- an accident which loses or misreads what was written is refused
- the other accidents are fixed

Each change comes with the test which fails without it, its CHANGELOG entry, and the forms
and frozen results updated for that input only. The wiki (Breaking-Changes, From-5.x-to-6.x,
Templates-and-Inheritance) is updated at the end, from the CHANGELOG entries.

## Items

| # | Accident (done-config-grammar.md section 6) | Becomes | Status |
|---|---|---|---|
| 1 | a template's number, address or string replaces the neighbor's own (`resolve.transfer`) | the neighbor's value wins | ✅ |
| 2 | `inherit` of a template which does not exist is ignored | a warning | ✅ |
| 3 | `inherit` of a template defined further down is ignored | the template is found wherever it is | ✅ |
| 4 | words before a `}` are ignored, an unknown keyword included; a line not ended by `;` is refused | a line end ends a statement as `;` does, and the words before a `}` are a statement: `;` is no longer needed (plan-optional-trailing-semicolon.md) | ✅ |
| 5 | a `}` with nothing open ends the configuration, the rest unread | refused | ✅ |
| 6 | sections still open at the end of the text are closed | refused | ✅ |
| 7 | a section name is any word (`process {` is named `{`), more words ignored | refused | ✅ |
| 8 | process names are not checked (`process p$`) | fixed: a name is letters, digits, `-`, `_`, `.` | ✅ |
| 9 | a boolean given no word takes the leaf default (`respawn;`, `adj-rib-in;` is false) | fixed: no word is true | ✅ |
| 10 | an opening quote does not end the word before it (`ab"cd"` is `abcd`) | refused | ✅ |
| 11 | inside quotes the other quote character switches which one closes (`"it's"`) | fixed: only the opening character closes | ✅ |
| 12 | `validate()` failures ignored: an api naming an undefined process is accepted | refused | ✅ |
| 13 | `family { ipv4 unicast; all; }` asks for every family; `add-path { all; }` for none | fixed: `all` with another is refused; `add-path { all; }` is every family | ✅ |
| 14 | a route line is VPN or labelled when `rd`/`label` appears anywhere, a value included (`name rd`) | fixed: the keywords only | ✅ |
| 15 | a prefix whose mask is no number is a host route (`10.0.0.0/x`) | refused | ✅ |
| 16 | `bgp-prefix-sid` skips the words it does not expect | refused | ✅ |
| 17 | announce families declare values they refuse whatever is given (`announce.Refused`) | already accepted (see below) | ✅ |
| 18 | a prefix of the other family in `announce ipv4\|ipv6` builds a route no one can show | refused | ✅ |
| 19 | a file ending on a continuation line repeats its last piece | fixed | ✅ |
| 20 | a `flow` section's routes are counted twice | already fixed (one route, measured) | ✅ |
| 21 | a trailing `&` in a flow match is refused inside brackets only | refused everywhere | ✅ |
| 22 | IPv6-only flow components accepted before the family is known | measured, then fixed | ✅ |
| 23 | a one-line flow `route-distinguisher` sets no field and is refused | fixed: read as `rd` | ✅ |
| 24 | an IPv6 `copy` next to another is dropped as a duplicate | measured, then fixed | ✅ |
| 25 | an attribute in `l2vpn` goes to the last route read, a static one included | refused | ✅ |
| 26 | the `l2vpn` section takes every route not yet taken, those before it included | fixed: its own routes | ✅ |
| 27 | an sr-policy route ignores what follows its sub-TLVs | refused | ✅ |
| 28 | an operational message reads two words per value: `router-id` is never accepted | fixed | ✅ |
| 29 | an operational sequence of 0 is no sequence | kept: 0 asks for the next sequence (a choice, documented) | ✅ |
| 30 | a second `operational` block replaces the first, unless empty | fixed: they add up | ✅ |
| 31 | with `local-address auto`, a `md5-ip` given is dropped (`resolve.session`) | fixed: kept | ✅ |
| 32 | `inherit` takes any word, and a list takes a comma as a name (`neighbor._inherit`) | fixed: template names only | ✅ |
| 33 | an sr-policy `sid` range is checked for the types c, d and e only | fixed: every type | ✅ |
| 34 | an operational value is checked against 64 bits, then refused past 32 when packed | fixed: 32 bits, said when read | ✅ |
| 35 | the routes read since the last neighbor or template closed are the next neighbor's | measured: not reachable | ✅ |
| 36 | a route given two next-hops: the first is the attribute, the last the route's | refused, as any attribute given twice | ✅ |
| 37 | the family of `attributes ... nlri` is the one of its last word | refused when the prefixes mix families | ✅ |
| 38 | the limits of the last `family` block giving any replace those before | fixed: they add up, two limits for one family refused | ✅ |
| 39 | the MUP `next-hop self` is of the family of the last prefix read, not the route's | fixed: the route's | ✅ |

Kept as they are, each a choice rather than an accident: the static `sr-policy` takes its
family from its endpoint; an IPv6 MUP route carries its next-hop in MP_REACH_NLRI only; an
advisory longer than 2048 octets is cut, ending in `...`; a section opened twice continues the
first (two `capability { }` blocks); `attribute` is read as `attributes`, the 3.4 spelling; a
`}` with nothing open ends an API command (read.left_open), where a section may span commands.

Item 17 needs no work: the values an announce family refused are accepted since
plan/done-old-commands.md, and `Refused` is left on RTC, where a membership is no route, and on
`labeled-unicast`, each with its reason.

Changed already, no work: api names (refused when reused), `labeled-unicast` in an announce
family (refused with its reason), `next-hop self` of the wrong family (refused), `name` and
`path-information` in an announce family (accepted), a negative operational sequence (refused).

## Decisions

- 2026-10-09 (Thomas): templates are defaults, the neighbor's value wins, no warning; a
  missing template is a warning; the accidents losing what was written are refused, the
  others fixed.
- 2026-10-09 (Thomas): `;` is no longer required. The end of a line ends a statement, and
  `<something> }` is `<something>` then `}`; a `;` is still accepted, and separates two
  statements on one line. This is plan-optional-trailing-semicolon.md, done as item 4.
- 2026-10-09 (Thomas): invalid syntax, a missing `}` for one, does not load, even when 5.x
  loaded it: a 5.x configuration with one fails when moved to 6. The 5.0 test conf-split,
  whose file ends with its neighbor section open, is a recorded difference in
  qa/bin/test_old_scripts (ALLOWED).
- 2026-10-09 (Thomas): booleans. The presence of a keyword is true: off by default it turns
  the option on, on by default it changes nothing, and it is not refused for that: "we do not
  want to break things", a configuration is refused only for what cannot be expressed. No
  `no-` forms; true/false and enable/disable stay accepted. Item 9 as done stands.

## Progress

- 2026-10-09, item 1: `resolve.transfer` keeps what the neighbor has; `_inherit` merges a
  template's own values before those of its parents, so what is set first wins: the neighbor,
  then the templates in their `inherit` order. Tests in
  `tests/unit/config_grammar/test_template_inherit.py` (5 red before). Two forms flipped to
  accepted (a template's `local-as auto` or confederation members next to the neighbor's own,
  which were refused); 27 frozen results changed, each a template and its neighbor setting the
  same value. The grammar's descriptions say a template gives defaults (man page and wiki
  Syntax-Reference regenerated); CHANGELOG entry.
- 2026-10-09, items 2, 3: `read.templates_first` puts the `template` sections first, each
  whole and in its order, for a file or a text (not an API command); `resolve._inherit` warns
  `inherit <name>: no template has this name, nothing is inherited`. Two tests in
  test_template_inherit.py (red before); 1 frozen result changed, the template written after
  its neighbor.
- 2026-10-09, item 4: `lexer._Splitter._close` ends the statement left at the end of a line,
  or before a comment, with a `;` token (STATEMENT_END); a quote left open is still refused.
  `Engine.read` reads the words before a `}` as a statement. Lexer table: `a b`, `a # b;`,
  `a b# c;` and two multi-line cases (red before); forms: `hold 1 }` now refused (unknown
  keyword), `run /bin/cat }` accepted, two documents without `;` added. Frozen: those 2
  changed, 2 new; every file of etc/ and qa/ reads as before.
- 2026-10-09, items 5, 6: `Engine(whole=True)` for a file or a text (read._engine) refuses a
  `}` closing nothing ("this '}' closes no section") and a section open at the end ("the
  <keyword> section is not closed, '}' is missing"); an API command keeps both (a section may
  span commands). Forms: four documents flipped to refused; frozen: those 4 changed.
- 2026-10-09, items 7, 8: `types/basic.SectionName(kind)` replaces LegacyName (process) and
  TemplateName: a name is required and checked (NAME_CHARACTERS moved to basic.py);
  `Engine._open` refuses a word after the name, or after a section taking none. Forms: four
  documents flipped to refused (`process {`, `process a b {`, `process p$ {`, `neighbor
  127.0.0.1 extra {`); frozen: those 4 changed.
- 2026-10-09, item 9: every `boolean`/`requirable` leaf is true when bare (8 were false or
  refused). `tests/unit/config_grammar/test_bare_boolean.py`; forms: `link-local-nexthop`
  alone accepted, tcp-ao `base64` alone refused with the wrapper's `secret` (as `base64 true`);
  frozen: 16 changed, each a bare form of those 8, in a neighbor or a template.
- 2026-10-09, items 10, 11: `lexer._Splitter._quote` refuses a quote opening inside a word,
  and keeps the other quote character inside quotes; `render.quote` writes a word in the
  quote character it does not hold (both: still unprintable). Lexer table (3 red before),
  test_roundtrip quote tests; no frozen input used either form.
- 2026-10-09, item 12: `configuration.api_error(neighbors, processes)` replaces
  Configuration.validate() (whose answer was ignored, and which ran after `_link` had added an
  empty entry for each process named) and runs before the reload replaces anything.
  `tests/unit/test_api_process_defined.py` (refusals, and a refused reload keeping what ran).
  Forms: the api forms are wrapped with processes `a` and `b` defined (forms.API_PROCESSES);
  the `undefined` document flipped to refused. Frozen: that 1 changed; 579 inputs renamed
  (the api forms and one template document with their processes added).
- 2026-10-09, item 13: `family.AllStore` refuses `all` with a family, in either order (and
  twice); `resolve.addpaths` takes `all` as every negotiated family, and turns the capability
  off when no family named is negotiated (the printer's `add-path { all; }` for none is gone).
  `tests/unit/config_grammar/test_add_path_all.py`; forms: two documents flipped to refused;
  frozen: 4 changed. Man page and wiki Syntax-Reference regenerated (the `all` description).
- 2026-10-09, checkpoint: test_everything for items 1-13, 28/28 (old-scripts once the 5.0
  conf-split difference was recorded, see Decisions).
- 2026-10-09, item 14: no visible effect, measured: `normalize` made every such route unicast
  again, on a route line, an `attributes ... nlri` line and a split. The NLRI class is now
  decided after the values, from the keywords given (`static._read_values`, `_nlri_class`);
  `tests/unit/config_grammar/test_route_kind_from_keywords.py` pins it (green before and
  after); frozen unchanged. No CHANGELOG entry: nothing a user sees changed.
- 2026-10-09, item 15: `bgp.Prefix` refuses a mask which is no number (a second slash was
  refused already, the whole word being taken as the address). Form flipped; frozen: 1 changed.
- 2026-10-09, item 16: `bgp.PrefixSidType` reads its format strictly (`_expect`); ranges are
  separated by a comma or not, as a qa cmd: line writes them. Forms: three refused, one
  without commas (6 red before, against src with the previous bgp.py); frozen: the qa command
  reads as before (same digest computed with the previous bgp.py); 44 new inputs (the four
  forms under each section a route value is read in).
- 2026-10-09, item 18: `announce.AnnounceLine.parse` refuses a prefix whose family is not the
  block's. Two forms flipped; frozen: 4 changed (those forms in a neighbor and a template).
- 2026-10-09, item 19: `lexer._file_lines` yields what a final continuation continued, once.
  test_lexer.py (red before); no frozen input ends on a continuation.
- 2026-10-09, item 20: already fixed, measured (a flow section's route counted once; FLOW
  keeps none of its routes, `tree/flow.py` says why).
- 2026-10-09, item 21: `types/flow._expression` refuses a word ending on `&` wherever it is.
  Form `port 80&` flipped; frozen: 4 changed (that condition in a block, a template, a flow
  line and an announce line).
- 2026-10-09, item 22: measured: a route of IPv6-only components was IPv6 already (Flow.add),
  but `types/flow._condition` checked each component's class against the context family, the
  last prefix read anywhere: an IPv6 flow-label after an IPv4 static route, or an IPv4 flow
  route after an IPv6 one, were refused, and `fragment`, valid in both families, would have
  been on an IPv6 announce line. The check is gone (Flow.add and rule_conflict judge each
  component by its families); each flow route starts with no family (FlowRouteSection.opened,
  FlowLine) or its block's (AnnounceFlowLine). `tests/unit/config_grammar/test_flow_family_own.py`
  (2 red before); one document flipped to accepted; frozen: 1 changed.
- 2026-10-09, item 23: LINE's own `route-distinguisher` (field `route-distinguisher`) is gone,
  ROUTE's (field `rd`) is used; ANNOUNCE_FLOW takes `route-distinguisher` too. Found on the
  way: `announce ipv4 flow ... rd 1:1` built a flow route (SAFI 133) carrying an rd, which did
  not print back: refused, `flow-vpn` named. Forms: the one-line form flipped to accepted, two
  new announce forms; frozen: the one-line document changed, 2 new; no qa command changed.
  The `if ip or line` of FlowRoute.apply (a line takes a redirect's next-hop even when there is
  none) has no visible effect, measured: the route has no next-hop either way.
- 2026-10-09, item 24: measured: a second IPv6 `copy` was dropped (`AttributeCollection.add`
  keeps the first), and `copy` with `redirect-to-nexthop-ietf` refused as `attribute 0x19 is
  given twice`. IPV6_EXTENDED_COMMUNITY is a list attribute (static.LIST_ATTRIBUTES), and the
  flow next-hop actions go through `add_attribute`. `tests/unit/config_grammar/
  test_flow_ipv6_actions.py` (2 red before); two forms; frozen: 2 new.
- 2026-10-09, items 25, 26: `l2vpn._InVpls` refuses a VPLS field or attribute at the l2vpn
  level (`<keyword> is given in a vpls route, not in the l2vpn section`; LastRouteStore and
  _NoSetter gone); L2VPNSection keeps only the VPLS routes it takes, the others stay for the
  neighbor (no visible effect: the neighbor had them either way, measured).
  `tests/unit/config_grammar/test_l2vpn_own_routes.py` (3 red before); the l2vpn-level forms
  all refused; frozen: 30 changed, 86 inputs gone (generated from those leaves' examples,
  which a refused leaf has none of). Found on the way: `describe.syntax` listed the refused
  keywords bare (`endpoint;`, `labeled-unicast;`, `otc;`), as statements to use; they are left
  out now, man page and wiki Syntax-Reference regenerated.
- 2026-10-09, item 27: `sr_policy.sr_policy_route` refuses a word after the sub-TLVs (`med 5`
  was dropped too). The two `garbage words` forms flipped; frozen: 8 changed, each of them.
- 2026-10-09, items 28, 29, 30, 34: `operational._values` reads every word as named values,
  each once, any order, `router-id` optional; an unknown word refused (after an advisory, the
  error says to quote it); `counter` bounded to U32; a block adds its messages; the printer
  writes a message's router-id. 29 kept: `OperationalSequenced` documents 0 as "not given",
  filled with the next sequence when sent; the shape says so. The API (`read.read_operational`)
  takes everything after `advisory` as its text, one pair of quotes removed (5.0 kept the
  quotes and the first word). test_api_operational_command.py updated (router-id read, the
  advisory text, trailing words refused); forms: four flipped; frozen: 9 changed.
- 2026-10-09, item 31: `resolve.session` keeps the md5-ip given whatever the local address,
  and the printer writes it whenever it is set. `tests/unit/config_grammar/test_md5_ip_kept.py`;
  frozen: 1 changed (the document giving an md5-ip and no local address). Noticed, not
  changed: a neighbor with `listen` and no local address has no md5_ip, and Reactor's listener
  set-up calls `md5_ip.top()` on it (reactor/loop.py:658); to measure separately.
- 2026-10-09, item 32: `neighbor.Inherit` checks each name with NAME_CHARACTERS and drops the
  commas of a list. Forms: `inherit t$` and `[ t u$ ]` refused; test_template_inherit.py: a
  comma is no template (it was warned about since item 2); frozen: 4 new, none changed (a
  comma inherited nothing, as now).
- 2026-10-09, item 33: `sr_policy._mpls_sid` checks the label for every type.
  `tests/unit/config_grammar/test_sr_policy_sid_range.py` (3 red before). Forms tried and
  removed: inside a neighbor without its sr-policy family they are refused for that, before
  and after, and tested nothing; frozen unchanged.
- 2026-10-09, item 35: measured, not reachable: the top level holds process, neighbor and
  template only (`static` there is an unknown section), and neither nests, so the routes a
  neighbor or template takes are those of its own block. Nothing to change.
- 2026-10-09, item 36: measured: the first next-hop was kept for both the attribute and the
  route (first_next_hop, since an earlier fix), the second dropped silently. `first_next_hop`
  now refuses it in a configuration and warns on the API (READING_COMMAND, as add_attribute).
  `tests/unit/config_grammar/test_next_hop_twice.py`. The forms gave every next-hop form a
  second one, the wrapper's own: the route line, the route block (forms._nested drops a need
  the form gives) and the announce generator now leave theirs out; frozen: 124 inputs renamed
  (119 new, some now the same text as another), none changed.
- 2026-10-09, item 37: measured worse than recorded: every prefix was built in the last
  one's family (`10.0.0.0/24` sent as a00::/24, `2001:db8::/32` as 32.1.13.184/32).
  AttributesLine refuses a prefix of another family. `tests/unit/config_grammar/
  test_nlri_one_family.py`; frozen unchanged (no input mixed them).
- 2026-10-09, item 38: `family.FamiliesSection.finish` adds a block's limits to those before,
  refusing two different limits for one family (one family in two blocks stays accepted,
  negotiated once). Found with it, item 1 not finished: `prefix-limit` and the add-path
  entries are lists of (family, limit) pairs which `transfer` extends, so a template's came
  after the neighbor's and won. codecs (prefix_limit) and resolve.addpaths keep the first
  for a family. `tests/unit/config_grammar/test_family_limits.py`; frozen: 1 changed.
- 2026-10-09, item 39: measured worse than recorded: a MUP prefix sets no context family, so
  an IPv6 route's `self` had the family `undefined`. MupNextHop takes `context.mup_afi`, the
  route's (SelectLine sets it). `tests/unit/config_grammar/test_mup_next_hop_self.py` (the
  IPv6 case red before); frozen unchanged.
- 2026-10-09, wiki (../wiki, not committed): Templates-and-Inheritance rewritten for the
  neighbor winning (5.x behaviour kept as the comparison), Rule 1 (a template found wherever
  it is), Rule 2 (first listed wins, a template may inherit), Rule 3, Troubleshooting;
  Breaking-Changes #29 (templates), #30 (mistakes refused), #31 (lines read differently) and the
  `;` feature; From-5.x-to-6.x: three summary rows, three sections with tables, the `;` feature.
  link-local-nexthop and link-local-prefer left out of the 5.x comparisons: new in 6.0.

## Failures

(none yet)

## Blockers

(none)

- 2026-10-09, the listener note of item 31, measured: not reachable. `Session.missing()`
  refuses `listen` with no local address or `auto` (tree/neighbor._check, "session local-address
  required when listen is set"), the API `neighbor` command takes no `listen` and requires a
  local address, and `infer()` makes the local address the md5-ip. `_listen_for_neighbors` now
  asserts md5_ip is set instead of calling `.top()` on what the type allows to be None.
  `tests/unit/test_listen_needs_an_address.py` pins the refusal (green before: no behaviour
  changed).

## Resume Point

Items 1-39 done, wiki written (neither committed). Next: the Syntax-Reference intro on `;` (qa/bin/update_wiki_syntax), full suite, commit when asked.
