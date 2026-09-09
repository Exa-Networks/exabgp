# PATHS-LIMIT Capability

ExaBGP supports the PATHS-LIMIT capability as defined in
[draft-abraitis-idr-addpath-paths-limit-04](https://www.ietf.org/archive/id/draft-abraitis-idr-addpath-paths-limit-04.txt).

PATHS-LIMIT extends ADD-PATH by letting peers advertise the maximum number of
paths per prefix they are willing to receive for each address family. It is
not a limit on the total number of prefixes or routes in that family.

## Configuration

PATHS-LIMIT is configured per-family inside the `add-path` block using the
`limit` keyword:

```
neighbor 192.0.2.1 {
    router-id 10.0.0.2;
    local-address 192.0.2.2;
    local-as 65500;
    peer-as 65501;

    capability {
        add-path send/receive;
    }

    family {
        ipv4 unicast;
        ipv6 unicast;
    }

    add-path {
        ipv4 unicast limit 10;
        ipv6 unicast limit 20;
    }
}
```

### Syntax

Inside the `add-path` block, each line takes one of two forms:

```
afi safi;              # ADD-PATH only, no paths-limit
afi safi limit N;      # ADD-PATH with PATHS-LIMIT (N = 1-65535)
```

- The `limit` keyword is optional. Omitting it means no PATHS-LIMIT for that
  family.
- `N` must be between 1 and 65535.
- The PATHS-LIMIT capability is only emitted on the wire for supported ADD-PATH
  families with a configured limit and `receive` or `send/receive` enabled.
  A send-only speaker does not advertise a receive limit.

### Supported families

PATHS-LIMIT uses ExaBGP's existing ADD-PATH family support; it does not extend it:

- `ipv4 unicast`, `ipv6 unicast`
- `ipv4 labeled-unicast`, `ipv6 labeled-unicast` (`nlri-mpls` is also accepted)
- `ipv4 mpls-vpn`, `ipv6 mpls-vpn`

The configuration parser accepts other families, but they are omitted from both
ADD-PATH and PATHS-LIMIT advertisements. In particular, multicast, FlowSpec,
EVPN, VPLS, and BGP-LS are not enabled by configuring a limit.

`ipv4 mup` and `ipv6 mup` used to be offered for ADD-PATH and are no longer.
`MUP.pack_nlri` writes no path identifier, so offering ADD-PATH for MUP told a
peer to expect four octets ahead of every MUP NLRI which were never sent, and
the peer mis-framed the rest of the field. A limit configured for MUP is parsed
and then ignored, as it is for any family ADD-PATH does not cover.

## Wire format

The PATHS-LIMIT capability uses code 76 (0x4C). Each entry in the capability
is 5 bytes:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|           AFI (2 octets)      |   SAFI (1)    | Max Paths (2) |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Max Paths cont|
+-+-+-+-+-+-+-+-+
```

## Behavior

### Negotiation

- PATHS-LIMIT is only meaningful when ADD-PATH is also negotiated.
- If ADD-PATH is not present on both sides, PATHS-LIMIT is ignored.
- Each side advertises its own limits independently.
- A peer's limit applies only to a family for which ExaBGP negotiated ADD-PATH
  sending; ExaBGP's advertised limit applies to negotiated receiving.
- An empty capability communicates no limits. A zero-valued tuple imposes no
  limit. Only the first tuple for an AFI/SAFI is considered, even if it is zero;
  later duplicates cannot replace it.
- The draft asks a speaker to describe all its families in one instance of the
  capability. ExaBGP accepts a repeated capability and merges it, still taking
  the first tuple for each AFI/SAFI, but it stops recording once the merged
  total reaches what a single instance can carry (51 families). The families
  past that point are ignored and the session is not affected. A truncated
  entry is a different matter and does close the session.

### Outgoing enforcement

When the peer advertises a PATHS-LIMIT for a family, ExaBGP will not send
more paths per prefix than the peer's limit for that family.
This limit persists across update batches and route refreshes. Updating an
already advertised path does not consume another slot.

ExaBGP retains admitted paths rather than running a best-path selection
algorithm. Excess requested paths are held back; withdrawing an admitted path
allows a retained candidate to be advertised. Which paths are chosen is simply
the order they were configured or announced in, since ExaBGP has no view of
which path is better.

Both events are logged, under the `rib` category:

```
rib.paths_limit.withheld family=... prefix=... limit=...
rib.paths_limit.promoted family=... prefix=... limit=...
```

Enable them with `exabgp_log_rib=true`. A route which the peer's limit keeps off
the wire produces no other signal, so this is worth turning on when a limit is
in force.

Be aware that a held back path still appears in `show adj-rib out`. The cache
records what the configuration and the API asked for, and the limit is applied
when updates are generated, so the cache is not a record of what the peer was
sent. For a limited family, read it as the set of paths ExaBGP would advertise
were the peer willing to receive them.

With `adj-rib-out false`, a limited family keeps just enough per-session state to
enforce the limit: a count of what has been sent, and the paths held back so one
can be promoted later. It does not keep the paths it has already sent, so
`adj-rib-out false` means the same thing whether or not the family has a limit:
a route refresh replays nothing and `withdraw` withdraws nothing. The state is
discarded on session reset and is not replayed after reconnect.

### Incoming audit

When ExaBGP advertises a PATHS-LIMIT and the peer sends more paths than
requested, a warning is logged (once per prefix per family). Excess received
paths are not dropped and the session is not closed by this audit.

The audit tracks at most one path beyond the limit for each prefix, so that a
peer which ignores the limit cannot decide how much memory watching it costs.
Once a prefix has gone past the limit and been reported, the tracked count can
fall below what the peer actually holds, and a later violation on that same
prefix may go unreported until the session restarts.

The audit is controlled by the environment variable:

```
exabgp_bgp_paths_limit_audit=true   # default: enabled
exabgp_bgp_paths_limit_audit=false  # disable audit logging
```

## Example

Limit the peer to sending at most 4 IPv4 unicast paths per prefix, with no
limit on IPv6:

```
neighbor 10.0.0.1 {
    router-id 10.0.0.2;
    local-address 10.0.0.2;
    local-as 65500;
    peer-as 65501;

    capability {
        add-path send/receive;
    }

    family {
        ipv4 unicast;
        ipv6 unicast;
    }

    add-path {
        ipv4 unicast limit 4;
        ipv6 unicast;
    }
}
```
