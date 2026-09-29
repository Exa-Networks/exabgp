# The default domain name is the host name

**Status:** 📋 Planning (decision needed)
**Created:** 2026-09-29
**From:** `done-testing-gaps.md` task 7

## Problem

`exabgp.util.dns.domain()` is:

```python
value = socket.getfqdn()
__domain_name = value.split('.')[0] if value else 'localhost'
```

That is the first label of the FQDN, the host name again, not the domain. It has been so
since the function was written (2015, `7f759ffef` moved it). `HostName()` uses it as the
default domain name, so every installation without a configured `domain-name` sends its
host name twice in the Hostname capability: `router1.example.com` goes out as host
`router1`, domain `router1`.

`tests/unit/test_util.py::TestDNS::test_domain_is_what_follows_the_host` demonstrates it as
a strict xfail.

## Constraint

An installation which works today keeps working. A peer, or a tool reading what peers log,
may have come to expect the current value. Correcting it changes what goes on the wire for
everyone who did not configure `domain-name`.

## Options

1. Fix it: everything after the first label, and empty (capability sent with no domain)
   when the FQDN has no dot. Release note it.
2. Keep sending what we send, rename nothing, and document that the default is the host
   name; turn the xfail into a test of the documented behaviour.

## Steps

1. [ ] Thomas: option 1 or 2
2. [ ] Implement, the xfail becomes a passing test either way
3. [ ] `./qa/bin/test_everything`

## Progress

## Failures

## Blockers

Step 1.

## Resume Point

Step 1.
