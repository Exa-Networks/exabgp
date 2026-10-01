# Plan: API version per process, detected from what the process writes

**Status:** planning
**Created:** 2026-10-01

## Problem

`exabgp.api.version` is global and defaults to 6. With it, every helper is held to the v6 API:

- `dispatch_v6` only knows commands starting with `daemon`, `session`, `system`, `rib`, `peer` or `group`, so a 5.x program writing `announce route ...` gets `error` for every command (`reactor/api/__init__.py:90`).
- `_select_encoder` replaces `encoder text` with JSON (`reactor/api/processes.py:396`), so a 5.x program parsing text receives JSON.
- `show ...` answers are always JSON, where v4 only gives JSON when the command ends in `json`.

A deployment upgraded from 5.x therefore breaks on every helper until each is rewritten, or until the whole daemon is switched to v4, which then applies v4 to new helpers as well and logs a deprecation warning per process.

Separately, ExaBGP answers each command with `done`. Many 5.x helpers never read their input: 5.x blocked once the 64 KiB pipe was full, 6.0 queues the unread answers in `_write_queue` without a bound.

## What is already there

- `dispatch_v4` accepts both forms: a line starting with a v6 root is passed to `dispatch_v6` unchanged (`dispatch/v4.py:209`), `neighbor ...` goes through the legacy selector parser, everything else through `translate_v4_to_v6`. The two forms do not overlap: no v4 command starts with a v6 root word except `group`, which means the same in both.
- `Response.V4.JSON` is the v6 encoder with the version string patched to `4.0.1` and the v4 FlowSpec next-hop compatibility on. `Response.V4.Text` is the only text encoder.

## Design

Each process carries an API version, `None` until known, then 4 or 6. It is reset when the process is respawned.

### Detection

The first command whose root word decides it fixes the version:

- root in `daemon session system rib peer` gives 6;
- any other root `dispatch_v4` accepts (`announce`, `withdraw`, `neighbor`, `shutdown`, `reload`, `restart`, `show`, `flush`, `clear`, `teardown`, `enable-ack`, `disable-ack`, `silence-ack`, `version`, ...) gives 4;
- `group`, comments and empty lines decide nothing.

`encoder text` in the process block also gives 4 from the start, since only v4 has a text format.

The global `exabgp.api.version`, when set by the operator, overrides detection for every process.

### Behaviour per version

| | Undetected | 4 | 6 |
|---|---|---|---|
| Commands accepted | both, the first decides | v4 only | v6 only |
| `show` answers | as v6 | JSON only when the command ends in `json` | JSON |
| Output, `encoder text` | v4 text | v4 text | n/a (text gives 4) |
| Output, `encoder json` | v6 JSON | v4 JSON (`"exabgp": "4.0.1"`) | v6 JSON |
| Deprecation warning | none | once per process, on detection | none |

### Unread answers

A helper which does not read its input must not grow ExaBGP's memory. `_write_queue` gets a byte bound per process (a named constant). When a process reaches it while the queued data are answers (`done`, `error`), ExaBGP stops answering that process (as `session ack silence` would), drops the queued answers, and logs once that the helper does not read its answers. Events the process subscribed to are never dropped silently: when they alone exceed the bound, the existing broken-process handling applies.

## Decisions (Thomas, 2026-10-01)

1. `exabgp.api.version`, when the operator sets it, forces that version on every process; detection only runs when it is not set.
2. A process is strictly 4 or 6 once detected: a v6 process gets `error` for a v4 line and a v4 process for a v6 line, so a program cannot mix the two forms.
3. Unread answers: a process is not reading when its pipe is full (the non-blocking write fails with EAGAIN, which works on Linux and macOS) and what is queued for it is answers only. ExaBGP then stops answering it, drops the queued answers and logs once. On Linux, `ioctl(FIONREAD)` on our end of its stdin gives the unread byte count for the log (checked: 15 bytes after three `done`, 61455 with a full pipe, 0 for a program which reads).

## Tests

- unit: detection table (each root word, `group`, comment, empty), reset on respawn, `encoder text` forcing 4, override precedence.
- unit: encoder switch from v6 JSON to v4 JSON on detection; text unchanged.
- unit: bounded queue, answers dropped and ack silenced once, events kept.
- functional: the existing API suite runs with `exabgp_api_version=4` (`qa/bin/functional:1945`); a variant without it must pass on detection alone, plus one v6 helper and one v4 helper attached to the same neighbour.

## Documentation

`Writing-API-Programs#how-a-program-talks-to-exabgp` in the wiki holds the only version statement, written so that this change rewrites one section.
