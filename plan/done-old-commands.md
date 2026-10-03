# Every 4.2 and 5.0 command and configuration statement still works

**Status:** ✅ Complete
**Created:** 2026-10-02
**From:** the 4.2/5.0 compatibility work of `done-agent-reported-bugs.md`

## Goal

Show that every API command and every configuration statement valid in 4.2 or 5.0 is
accepted by main, and makes main announce and withdraw what the old release did. The wire
bytes do not have to match: what is compared is the decoded content.

`qa/bin/test_old_scripts` (the copied functional tests in `qa/old/`) proves what only a
running session shows: helpers, End-of-RIB, reload, teardown. It only covers what its
authors happened to write. This plan covers the grammar itself.

## Design

1. **Grammar from the old code.** A recorder runs the 4.2 and 5.0 trees (Python 3.10) and
   reads their API command registry (`Command.register`) and the keyword tables of each
   section (`known`/`action` in `configuration/static/route.py`, `flow/*`, `l2vpn/vpls.py`,
   `neighbor/*`, ...). Nothing is listed by hand.
2. **Values.** Each keyword gets sample values, harvested from the old configurations,
   tests and documentation, plus a small hand-written table for those never seen. A keyword
   with no sample fails the recorder: coverage is enforced, not hoped for.
3. **Commands.** Every command prefix; for route commands a minimal route, the route plus
   each keyword alone, and combinations.
4. **Recording.** Each release parses every command with its own code and packs the
   UPDATE with its own encoder. Stored in `qa/old/commands-<version>.json`: command,
   accepted or not, UPDATE bytes. CI needs neither Python 3.10 nor the old trees.
5. **Check.** `qa/bin/test_old_commands`: main, as an API 4 helper's command, must accept
   what the old release accepted and announce/withdraw the same routes (decoded). Anything
   else is a failure unless in ALLOWED with its reason. In-process, seconds.
6. **Configuration.** The same for configuration statements: the old release's OPEN and
   UPDATEs for a neighbor using the statement, compared decoded; statements with no wire
   effect are checked for acceptance.

## Steps

1. [x] Deduplicate `qa/old/`: 19 4.2 tests identical to 5.0 and 103 unused files removed
2. [x] Recorder: 5.0 API route commands (`announce/withdraw route|ipv4|ipv6`)
3. [x] Check: main against the 5.0 route corpus, triage, fix or allow
4. [x] Recorder and check: flow, vpls, attributes, eor, route-refresh, operational (5.0)
5. [x] Recorder and check: the other commands (show, teardown, flush, clear, ...), accepted (5.0)
6. [x] 4.2: the same
7. [x] Configuration statements, 5.0 then 4.2
8. [x] Wire into `test_everything`; CHANGELOG not needed (no behaviour of this tree changed)

## Progress

- 2026-10-02: deduplicated `qa/old/` (391 files left); `test_old_scripts` still 34/34 and 72/72.
- `qa/old/recorder.py` runs in the old release's Python: `grammar` dumps the registered API
  commands and every `known` table (5.0: 36 commands, 36 sections); `record` sends each
  command through the release's own `API.process` and handler on a stand-in reactor which
  captures `inject_change`/`inject_eor`/`inject_refresh`/`inject_operational`, then packs
  with the release's own `Update.messages`. First version called the `api_*` parsers
  directly: wrong, the handlers set the action and drop what `ParseStaticRoute.check`
  refuses, so 5.0 packed nothing for `attributes`, `flow`, `vpls`.
- `qa/bin/record_old_commands` harvests commands from the old tree (etc, qa, doc), this
  tree's `qa/encoding` and the wiki, takes the shortest accepted ones of each shape as
  bases, and adds every keyword of the matching sections with each value seen in the
  corpus. Keywords before `nlri` for `attributes`; sub-section keywords skipped.
- `qa/bin/test_old_commands` gives each recorded command to this tree's API 4 dispatcher
  and handler on a stand-in reactor, packs what it injects, and compares routes decoded
  by this tree on both sides. Old UPDATEs are decoded with ADD-PATH if they need it.

- 2026-10-03 caps: `split /32` of a /8 is 16M routes, which 5.0 builds in memory before
  anything can stop it (one run reached 18 GB). Commands splitting into more than 256 routes
  are not generated or harvested; the recorder also stops at 512 messages. Recording takes
  15 s, the corpus is 1.4 MB. Values come from code blocks only (prose gave `IPv6`,
  `configs`), `;` is stripped, a value of the other address family than the base is not
  used, block-form bases are recorded as written (5.0 ignores what follows `}`).
- 5.0 coverage complete: every keyword of every command section has an accepted command.
- Found and fixed on main:
  - `announce ipv4|ipv6 <safi>` refused `atomic-aggregate`, `originator-id`, `cluster-list`,
    `aigp`, `attribute`, `name`, `split`, `watchdog`, `withdraw`, `path-information`
    (grammar `Refused`, recorded as a legacy accident). 5.0 accepted and sent them. Now
    read as on a static route (`AS_ON_A_ROUTE`); `rtc` keeps refusing them.
  - A labelled or VPN route with no label (a `withdraw` given none) was packed with no
    label field: the receiver read the RD as the label. The Compatibility field 0x800000
    is packed now (RFC 8277 2.4), `Label._with_label_field`.
- 5.0 bugs found (allowed): `announce ipv4|ipv6 mpls-vpn` packed the VPN route into the
  unicast NLRI field; an IPv4 flow route accepted IPv6 components.

- 5.0 done: 4130/4130 (575 allowed, 88 undecodable from 5.0). Also fixed: `announce`
  handlers other than `route` did not check routes (VPN without label, link-local
  next-hop without the capability); `next-hop` given twice (first wins now); a withdrawal
  with `next-hop self` of the other address family was refused.

- 2026-10-03 4.2 done: 2541/2541 (225 allowed, 16 undecodable from 4.2, 6 where 4.2 sent
  nothing). The recorder runs 4.2 from `lib/` on Python 3.10 with `pyasyncore`; 4.2 has no
  `_negotiated` (`_negotiated_42` builds the iBGP session its `check_neighbor` did), no
  `API.process` (`API.text`), and a logger which fails with nowhere to write (silenced).
  `qa/old/neighbor-4.2.conf`: 4.2 refuses `family { all; }`. No main bug found; 4.2 bugs
  allowed: `split` ignored on `announce attribute(s)`, a repeated `extended-community` kept
  only the first, `target:<ip>:<n>` sent as a two octet AS community, a `then` of a flow
  route kept only its first action, 224.0.0.0/4 sent as unicast, the draft SRv6 syntax.

- 2026-10-03 configurations done. `recorder.py configurations` loads each configuration in
  the release and records, for each neighbor, its OPEN and the UPDATEs its RIB sends.
  `record_old_configs` harvests every configuration file and documentation code block,
  takes each neighbor statement, `family`/`capability` entry and route (with its block) on
  its own into the minimal neighbor, adds hand statements for keywords nothing used, and
  fails when a keyword of the release's configuration grammar is still unused.
  `test_old_configs` loads the same text from a file (a `\` continuation exists only in a
  file), compares the OPEN by field and capability and the routes the peer ends with.
  4.2: 1141/1141 (21 allowed), 5.0: 1193/1193 (18 allowed), 3.5 s, stage `old-configs`.
  Not differences: the RIB outlives a load by neighbor name (cleared per configuration on
  both sides); a neighbor with no family block gets the families the release knew, less
  RTC in 6.0 (CHANGELOG); a route given twice is sent twice by the old releases and once
  here, the peer keeps the last. No main bug found. Allowed, all argued in the file:
  multi-session (5.0 meant one session per family and sent one), ADD-PATH for flow
  (#1140), an unmatchable flow route dropped (RFC 8955 4.2), the redirect-ip and four
  octet AS changes already allowed for commands, `static { attributes ... nlri }` (5.0
  sent nothing, 4.2 withdrawals), and 4.2's missing hostname capability, misread
  `target:<ip>:<n>`, draft SRv6 syntax and IPv6 flow label routes it never sent.
  Noticed, left: a flow route is in `neighbor.routes` twice, kept from the legacy parser on
  purpose (grammar/tree/flow.py FlowSection); the RIB sends it once.

## Failures

## Blockers

## Resume Point

Done. Possible next: the `api` statements are checked for acceptance only (their effect is
on the helper, not the wire); a helper-side check would need a running session, as
test_old_scripts has.
