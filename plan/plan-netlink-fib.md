# Plan: programming the Linux FIB over netlink, from a plugin

**Status:** planning. Nothing is changed yet: `src/exabgp/application/netlink.py` and
`lab/netlink/` stay as they are (see Current state).

## Goal

Let routes ExaBGP learns or announces be installed in the Linux kernel's forwarding table
(FIB), through netlink, by an optional plugin. The daemon itself keeps not touching the FIB:
the plugin is a separate process fed by the API, as healthcheck is, so an operator who does
not want it does not run it, and only the plugin needs `CAP_NET_ADMIN`.

## Current state (2026-09-30)

- `lab/netlink/` holds the 2015 netlink code: `netlink.py` (socket, encode/decode of the
  netlink header), `message.py`, `attributes.py` (RTA_* TLVs), `route/` with `address.py`,
  `link.py`, `neighbor.py` and `network.py` (RTM_GETROUTE, RTM_NEWROUTE, RTM_DELROUTE),
  plus `firewall.py`, `tc.py`, `sequence.py` and `old.py` (an earlier version). It was moved
  out of `src/exabgp/netlink/` on 2025-12-07 (218bed958) as unused.
- `src/exabgp/application/netlink.py` is the command which used it (`addr show`,
  `route show|add|delete`). It still imports `exabgp.netlink`, so it fails at import, in the
  pure and the compiled build alike. It compiles, as mypy is told to ignore missing imports.
  Nothing else imports it.
- ExaBGP's documentation says it does not manipulate the FIB (README, CLAUDE.md, the wiki).
  That stays true of the daemon; the plugin changes what the project offers.
- Ze (ExaBGP's successor, github.com/ze-software/ze) programs the FIB itself. Whether this
  is worth doing in ExaBGP rather than pointing users to Ze is the first question below.

## Design

A helper process, `exabgp fib` (name to decide), run from a `process` block:

```
process fib {
    run exabgp fib --table 254 --protocol 186;
    encoder json;
}
neighbor 192.0.2.1 {
    api { processes [ fib ]; receive { parsed; update; } neighbor-changes; }
}
```

- It reads the JSON API (announce, withdraw, neighbor down, End-of-RIB) and keeps its own
  table of what it installed, per neighbor and prefix.
- It writes RTM_NEWROUTE and RTM_DELROUTE: RTA_DST, RTA_GATEWAY, RTA_OIF when the next hop
  is on a connected interface, RTA_PRIORITY, RTA_TABLE, with the routing protocol RTPROT_BGP
  (186) so its routes are recognisable, and flushable, with `ip route show proto bgp`.
- ExaBGP has no best path selection. The helper needs a rule for the same prefix from two
  neighbors: the simplest is a metric per neighbor (RTA_PRIORITY), letting the kernel pick;
  ECMP (RTA_MULTIPATH) is a later step.
- On start it flushes its protocol's routes from its table, then installs as updates arrive.
  A neighbor going down withdraws its routes, unless it negotiated Graceful Restart, where
  they stay until its End-of-RIB or restart time, as ExaBGP's adj-rib-in now does.
- Batching: several netlink messages per send, acknowledged with NLM_F_ACK, so a full table
  does not cost one syscall per route; errors (EEXIST, ENOENT, ENETUNREACH) are logged per
  route and do not stop the helper.

The alternative, an in-daemon plugin interface, is not proposed: it puts a privileged
operation in the daemon, which drops privileges, and a second plugin mechanism beside the
process API.

## Phases

### Phase 0: decide

- Worth it in ExaBGP, or point to Ze?
- Name and packaging: a subcommand of `exabgp`, or a separate entry point.
- Scope of the first release: IPv4 and IPv6 unicast, one table, no ECMP, no VRF.

### Phase 1: bring the netlink code back

- Move `lab/netlink/` back under `src/exabgp/netlink/`, leaving `old.py`, `firewall.py` and
  `tc.py` in lab unless phase 0 wants them.
- Type it to `mypy --strict`, make it compile with mypyc (the rest of the package does), and
  apply `.claude/EXA_STYLE.md`: every length checked before it is read, bounded loops, named
  constants for the netlink numbers.
- Tests from recorded netlink messages (encode and decode, no root needed), and a Linux-only
  test in a network namespace (`unshare -rn`) which adds, reads back and deletes a route.

### Phase 2: the read-only command

- Fix `application/netlink.py` against the restored module: `addr show` and `route show`
  first, as they need no privilege. Register it as an `exabgp` subcommand if phase 0 says so.

### Phase 3: route install and removal

- RTM_NEWROUTE and RTM_DELROUTE for IPv4 and IPv6, with the attributes above, NLM_F_ACK,
  batching, and error handling per route. Tests in the namespace.

### Phase 4: the FIB helper

- The API consumer described above, with its own state, the neighbor-down and Graceful
  Restart handling, and the flush on start.
- A functional test: ExaBGP receiving routes from the test peer (qa/sbin/bgp), the helper
  installing them in a namespace, the test reading the kernel table.

### Phase 5: documentation

- A wiki page and a doc page: what it installs, the table and protocol numbers, the
  privilege it needs (`CAP_NET_ADMIN`, or run as root), how to remove what it installed.
- Update the "ExaBGP does not manipulate the FIB" statements: the daemon does not, an
  optional helper can.

### Later

- ECMP (RTA_MULTIPATH), VRF tables, MPLS routes, and non-Linux systems (BSD route sockets)
  are out of the first scope.

## Open questions

- Phase 0's question first: ExaBGP or Ze.
- How the helper chooses between two neighbors announcing the same prefix, beyond a metric.
- Whether the helper should also react to the routes ExaBGP itself announces (the API sends
  them with `send` events) or only to received ones.
