# domain() returned the host name

**Status:** ✅ Done 2026-09-29
**From:** `done-testing-gaps.md` task 7

## Problem

`exabgp.util.dns.domain()` was:

```python
value = socket.getfqdn()
__domain_name = value.split('.')[0] if value else 'localhost'
```

the first label of the FQDN, the host again, not the domain. It had been so since 2015.

## What it reached (corrected)

The first version of this plan said every installation without `domain-name` sent its
host name twice in the Hostname capability. It did not. Checked on 2026-09-29:

- the daemon builds the capability as `HostName(neighbor.host_name, neighbor.domain_name)`
  (`capabilities.py`), both from the configuration and both defaulting to `''`, never
  `None`, so the `host()`/`domain()` fallback in `HostName.__init__` never runs
- with no `host-name` configured, `extract_capability_bytes()` returns `[]` and the
  capability is not sent at all
- the decoder's `HostName()` overwrites both fields with what the peer sent
- `warn()` in `application/server.py` calls `domain()` only to time the resolver

So nothing wrong ever went on the wire, and correcting it changes nothing a peer sees.

## Decision

Fix it (Thomas, 2026-09-29). A bare host with no domain gives `''`, not `localhost`:
`localhost` is not a domain, and `HostName` already writes an empty domain as a zero length.

## Done

- `domain()` returns what follows the first label, trailing root dot removed, `''` when
  there is none
- the cache uses `None` for "not resolved", so `''` is cached like any other answer and a
  host without a domain does not ask the resolver on every call
- `tests/unit/test_util.py::TestDNS`: the strict xfail became five parametrised cases
  (FQDN, trailing dot, `.local`, bare host, empty) and a caching test for the empty answer

## Resume Point

Done.
