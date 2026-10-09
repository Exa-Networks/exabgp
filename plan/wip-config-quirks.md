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
| 1 | a template's number, address or string replaces the neighbor's own (`resolve.transfer`) | the neighbor's value wins | ⏳ |
| 2 | `inherit` of a template which does not exist is ignored | a warning | ⏳ |
| 3 | `inherit` of a template defined further down is ignored | the template is found wherever it is | ⏳ |
| 4 | words before a `}` are ignored, an unknown keyword included; a line not ended by `;` is refused | a line end ends a statement as `;` does, and the words before a `}` are a statement: `;` is no longer needed (plan-optional-trailing-semicolon.md) | ⏳ |
| 5 | a `}` with nothing open ends the configuration, the rest unread | refused | ⏳ |
| 6 | sections still open at the end of the text are closed | refused | ⏳ |
| 7 | a section name is any word (`process {` is named `{`), more words ignored | refused | ⏳ |
| 8 | process names are not checked (`process p$`) | fixed: a name is letters, digits, `-`, `_`, `.` | ⏳ |
| 9 | a boolean given no word takes the leaf default (`respawn;`, `adj-rib-in;` is false) | fixed: no word is true | ⏳ |
| 10 | an opening quote does not end the word before it (`ab"cd"` is `abcd`) | refused | ⏳ |
| 11 | inside quotes the other quote character switches which one closes (`"it's"`) | fixed: only the opening character closes | ⏳ |
| 12 | `validate()` failures ignored: an api naming an undefined process is accepted | refused | ⏳ |
| 13 | `family { ipv4 unicast; all; }` asks for every family; `add-path { all; }` for none | fixed: `all` with another is refused; `add-path { all; }` is every family | ⏳ |
| 14 | a route line is VPN or labelled when `rd`/`label` appears anywhere, a value included (`name rd`) | fixed: the keywords only | ⏳ |
| 15 | a prefix whose mask is no number is a host route (`10.0.0.0/x`) | refused | ⏳ |
| 16 | `bgp-prefix-sid` skips the words it does not expect | refused | ⏳ |
| 17 | announce families declare values they refuse whatever is given (`announce.Refused`) | already accepted (see below) | ✅ |
| 18 | a prefix of the other family in `announce ipv4\|ipv6` builds a route no one can show | refused | ⏳ |
| 19 | a file ending on a continuation line repeats its last piece | fixed | ⏳ |
| 20 | a `flow` section's routes are counted twice | fixed | ⏳ |
| 21 | a trailing `&` in a flow match is refused inside brackets only | refused everywhere | ⏳ |
| 22 | IPv6-only flow components accepted before the family is known | measured, then fixed | ⏳ |
| 23 | a one-line flow `route-distinguisher` sets no field and is refused | fixed: read as `rd` | ⏳ |
| 24 | an IPv6 `copy` next to another is dropped as a duplicate | measured, then fixed | ⏳ |
| 25 | an attribute in `l2vpn` goes to the last route read, a static one included | refused | ⏳ |
| 26 | the `l2vpn` section takes every route not yet taken, those before it included | fixed: its own routes | ⏳ |
| 27 | an sr-policy route ignores what follows its sub-TLVs | refused | ⏳ |
| 28 | an operational message reads two words per value: `router-id` is never accepted | fixed | ⏳ |
| 29 | an operational sequence of 0 is no sequence | measured, then fixed | ⏳ |
| 30 | a second `operational` block replaces the first, unless empty | fixed: they add up | ⏳ |
| 31 | with `local-address auto`, a `md5-ip` given is dropped (`resolve.session`) | fixed: kept | ⏳ |
| 32 | `inherit` takes any word, and a list takes a comma as a name (`neighbor._inherit`) | fixed: template names only | ⏳ |
| 33 | an sr-policy `sid` range is checked for the types c, d and e only | fixed: every type | ⏳ |
| 34 | an operational value is checked against 64 bits, then refused past 32 when packed | fixed: 32 bits, said when read | ⏳ |
| 35 | the routes read since the last neighbor or template closed are the next neighbor's | measured, then refused | ⏳ |
| 36 | a route given two next-hops: the first is the attribute, the last the route's | refused, as any attribute given twice | ⏳ |
| 37 | the family of `attributes ... nlri` is the one of its last word | refused when the prefixes mix families | ⏳ |
| 38 | the limits of the last `family` block giving any replace those before | fixed: they add up, a family given twice refused | ⏳ |
| 39 | the MUP `next-hop self` is of the family of the last prefix read, not the route's | fixed: the route's | ⏳ |

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

## Progress

(none yet)

## Failures

(none yet)

## Blockers

(none)

## Resume Point

Plan written. Next: item 1, the template precedence.
