# HostName capability: accepted length vs re-encoded length

**Status:** ✅ Done
**Started:** 2026-09-29
**From:** `done-cve-exa-style-followup.md`, "Not fixed, noted here"

## Problem

`HostName.unpack_capability` accepts up to 255 bytes for the host name and for the domain
name, because each has a one byte length. `extract_capability_bytes` truncates both to
`HOSTNAME_MAX_LEN` (64). A peer hostname longer than 64 bytes does not survive a re-encode.

ExaBGP never re-announces a peer's hostname capability, and the value is escaped on output,
so nothing is exposed today. It is still a decoder accepting what it cannot re-encode, which
EXA_STYLE.md 1.1 asks it not to do.

- File: `src/exabgp/bgp/message/open/capability/hostname.py`

## Constraint

An installation which works today keeps working. Refusing a long hostname with a `Notify`
would drop a peering which comes up today, so the fix is on the encode side, not the decode
side.

## Found while starting

draft-walton-bgp-hostname-capability-02 sets no maximum: each length is one octet, so 255.
`HOSTNAME_MAX_LEN = 64` is our own choice, and it only bounds what we send.

The truncation cut bytes, not characters. A configured name of 63 ASCII bytes and an `é`
was sent as 64 bytes ending half way through the `é`, which our own decoder refuses with a
`Notify`, so two ExaBGP speakers with such a name could not peer. Fixed: `_truncate()`
cuts at a character boundary.

The same shape in `Software.extract_capability_bytes`: the length byte was the length in
characters, not bytes. Our own version string is ASCII, so this never reached the wire,
but a decoded peer version wider than ASCII re-encoded with the wrong length. Fixed.

## Steps

1. [x] Test and fix: truncation splitting a UTF-8 character (fails on HEAD, passes now)
2. [x] Test and fix: Software length counted characters (fails on HEAD, passes now)
3. [x] Decided 2026-09-29: keep 64. Raising it would change what we send for a configured
       name longer than 64 bytes, which a peer that works today might not accept, and we
       never re-announce a peer's hostname, so a decoded name not round-tripping costs nothing
4. [x] `./qa/bin/test_everything` (25/25, 2026-09-29, with 64 kept)

## Progress

`hostname.py`, `software.py`, two tests in `tests/unit/test_input_validation.py`.

## Failures

## Blockers

None.

## Resume Point

Done.  The decode/encode length mismatch stays, by decision, see step 3.
