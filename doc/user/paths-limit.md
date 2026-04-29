# PATHS-LIMIT Capability

ExaBGP supports the PATHS-LIMIT capability as defined in
[draft-abraitis-idr-addpath-paths-limit](https://datatracker.ietf.org/doc/draft-abraitis-idr-addpath-paths-limit/).

PATHS-LIMIT extends ADD-PATH by letting peers advertise the maximum number of
paths they are willing to receive for each address family. This prevents a
sender from advertising more paths than the receiver can use.

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
- The PATHS-LIMIT capability is only emitted on the wire when at least one
  family has a limit configured.

### Supported families

Any family supported by `add-path` can have a limit:

- `ipv4 unicast`, `ipv4 multicast`, `ipv4 nlri-mpls`, `ipv4 mpls-vpn`, etc.
- `ipv6 unicast`, `ipv6 mpls-vpn`, etc.
- `l2vpn vpls`, `l2vpn evpn`
- `bgp-ls bgp-ls`, `bgp-ls bgp-ls-vpn`

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

### Outgoing enforcement

When the peer advertises a PATHS-LIMIT for a family, ExaBGP will not send
more paths per prefix than the peer's limit for that family.

### Incoming audit

When ExaBGP advertises a PATHS-LIMIT and the peer sends more paths than
requested, a warning is logged (once per prefix per family). This is
controlled by the environment variable:

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
