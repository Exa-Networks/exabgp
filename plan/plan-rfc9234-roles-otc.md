# RFC 9234 - BGP Roles and Only-To-Customer (OTC)

**Status:** Planning; specification reviewed against the code, implementation not started
**Issue:** [#1346](https://github.com/Exa-Networks/exabgp/issues/1346)
**RFC:** [RFC 9234](https://www.rfc-editor.org/rfc/rfc9234.html)
**Reference implementation:** ze, `internal/component/bgp/plugins/role/`
**Created:** 2026-09-02
**Last Updated:** 2026-09-13

## Overview and conformance boundary

RFC 9234 defines:

| Piece | Wire | Purpose |
|-------|------|---------|
| BGP Role capability | OPEN capability code **9**, one-octet value | declares the local speaker's eBGP relationship |
| OTC attribute | path attribute code **35**, optional transitive, four-octet ASN | marks a route as only to customer |
| Procedures | ingress marking, egress marking, leak detection and prevention | enforce propagation restrictions |

Roles are `0 provider`, `1 rs`, `2 rs-client`, `3 customer`, `4 peer`. Valid local/remote pairs
are provider/customer, customer/provider, rs/rs-client, rs-client/rs and peer/peer.

This plan delivers **partial RFC 9234 support**: Role negotiation, OTC wire/config/API support,
automatic egress marking and refusal, and ingress leak reporting. It deliberately does **not**
implement the mandatory ingress OTC insertion in RFC 9234 Section 5. Do not describe the combined
feature, or either wire-only phase, as full RFC 9234 conformance.

ExaBGP does not redistribute from its adj-rib-in, perform best-path selection, or install a FIB.
Helpers can nevertheless relay received routes through the announcement API. Those helpers must
enforce ingress ineligibility and insert missing ingress OTC before redistribution; the helper
contract below makes that responsibility explicit.

Role configuration is eBGP-only. Section 5's automatic marking, eligibility checks and leak
reporting apply only to **AFI 1 or 2, SAFI 1**. Attribute recognition and malformed-attribute
handling are separate from that family gate. The RFC discourages these procedures within a
confederation and prohibits Roles on Complex relationships; neither case gains a policy override
in this feature. Confederations are out of scope: ExaBGP models no confederation membership
outside AS_CONFED segments in `aspath.py`, so no confederation-aware behaviour is specified or
tested here. The ASNs used by Section 5 are named explicitly below, never inferred from the
ordinary local-AS stamping rule.

## Configuration and role meaning

```
neighbor 192.0.2.1 {
    local-as 65001;
    peer-as 65002;

    role {
        local provider;       # our local role; the remote AS is our customer
        strict disable;       # default; enable requires the remote Role capability
        otc send;             # default; disable stops marking what we send
        add-meta enable;      # default; disable stops the meta group in the API output
    }
}
```

`role {}` is a neighbour subsection beside `capability {}` and `tcp-ao {}`. The token is `local`,
not ze's `import`. ze's keyword needed a sentence of documentation to explain that it names **our
local role** rather than the neighbour's role or a destination filter, and needing that sentence is
the argument against it. ExaBGP has no configuration compatibility with ze, and this plan already
accepts divergent JSON envelopes, so the clearer token wins. `local customer` means the neighbour is
our provider. Keep the block form rather than a bare `role provider;` because `strict` sits beside it.

- A present `role {}` block requires `local`, with exactly one of the five role names.
- `strict` accepts `enable|disable` and defaults to `disable`. `strict enable` without `local`,
  and an empty `role {}` block, are configuration errors rather than silently inactive policy.
- `otc` carries the direction in its value, exactly as `add-path` does, and defaults to `send`. It
  is the session default for routes that say nothing; a route carrying an `otc` token of its own
  overrides it in either direction.

  | Value | Meaning | Accepted today |
  |-------|---------|----------------|
  | `send` | mark the routes we advertise, RFC 9234 egress procedure 1 | yes, the default |
  | `disable` | mark nothing | yes |
  | `receive` | mark the routes we accept, RFC 9234 ingress procedure 3 | no |
  | `send/receive` | both | no |

  RFC 9234 marks in **both** directions, and this feature implements only the first, so direction
  has to be expressible. `add-path` is the existing answer in this language to a capability that
  works in two directions, `disable|receive|send|send/receive` on one token, and reusing it means
  ingress marking lands as a new value rather than a second knob and a rename. Do not reintroduce a
  direction-in-the-name variant: `egress` and `ingress` appear nowhere in this configuration
  language, and any name hardcoding one direction needs replacing the moment the other exists.

  `receive` and `send/receive` parse and are then rejected, with an error naming ingress marking as
  unimplemented rather than the value as unknown. A reader who tries them has understood the model
  correctly and deserves to be told what is missing, not that they typed something meaningless.
  Implementing ingress marking is then purely additive: accept the two values, change nothing else.

  **Enabled, it adds, and only that.** Of the three things adding could mean:


  | | | Basis |
  |---|---|---|
  | adds | yes, and only when the outgoing route carries no OTC at all | RFC 9234 Section 5, egress procedure 1: *"If a route is to be advertised to a Customer, a Peer, or an RS-Client ... and the OTC Attribute is not present, then when advertising the route, an OTC Attribute MUST be added"* |
  | replaces | never, whatever the existing value, including one that already equals our own ASN | RFC 9234 Section 5: *"Once the OTC Attribute has been set, it MUST be preserved unchanged"* |
  | appends | never, and it could not: *"an optional transitive Path Attribute ... with Attribute Type Code 35 and a length of 4 octets"*, so a route carries one or none | RFC 9234 Section 5 |

  Replacing and appending are not configurable and never will be. A configuration option exists to
  let an operator choose between permitted behaviours, and offering either of those would be
  offering a way to violate a MUST. That the RFC permits one action and forbids the rest is exactly
  why this is a boolean: whether to mark at all is the only choice left. Egress procedure 1 adds only where the attribute is absent,
  and egress procedure 2 decides what happens to a route that already has one, so an existing value
  is never a candidate for replacement, it is a candidate for refusal.
  A route carrying `otc self`, `otc <role-name>` or `otc <asn>` already has its attribute resolved
  before serialization, so `otc send` sees a route that carries one and leaves it
  alone. That is the
  same rule, not a special case, and the preservation requirement above is why.
  It gates **only** that automatic outbound insertion, which is RFC 9234 egress procedure 1.
  It does not gate egress procedure 2: a route that already carries OTC is still refused towards a
  provider, an RS or a peer under `otc disable`, because that half is the leak prevention and
  turning off
  marking must not quietly turn off protection. It does not gate ingress leak reporting either, and
  it never strips an OTC the operator set explicitly.
  `otc disable` in the role block is a deliberate divergence from a MUST in RFC 9234 egress
  procedure 1. Log it
  once per session at warning level so it is visible to whoever debugs a missing mark later, and do
  not describe a session configured that way as conformant.
- `add-meta` accepts `enable|disable` and defaults to `enable`. It controls whether the `meta` group
  is added to announcement entries in the API output for this neighbour. It is the only control over
  that group: there is no per-route override, because the group is ExaBGP's reporting and not
  something a route asks for.
  It gates the group, not the detection. Classification still runs, the warning log is still emitted
  and refusals still happen with `add-meta disable`, and unlike `otc` it needs no direction,
  because reporting only happens in one, so silencing the API stream never silences the
  operator's log or weakens leak prevention. It is for a deployment whose helpers do not read the
  group and would rather not carry it on every announcement.
  It covers the whole `meta` group rather than `route-leak` alone, so anything later added there
  obeys the same switch and no second knob is invented for it.
  Like the role block's `otc` it negotiates nothing, so it reloads without dropping the session.
- Validate the effective neighbour after template inheritance, not just the subsection in isolation.
- With a role configured, require explicit `local-as` and `peer-as` and reject equal ASNs.
  Reject `auto` for either ASN in this configuration. Automatic ASNs remain supported when no role
  is configured; their unresolved values must not masquerade as evidence that a session is eBGP.
- Two of the four settings restart a session and two do not, and `Neighbor.__eq__()` is what
  decides: `Reactor.reload()` (`src/exabgp/reactor/loop.py:618`) calls `reestablish()` on any
  neighbour that compares unequal. Compare `local` and `strict` there and deliberately not `otc`
  or `add-meta`, which would otherwise bounce BGP to change a JSON key.

  | Setting | In `Neighbor.__eq__()` | Reload behaviour |
  |---------|------------------------|------------------|
  | `local` | yes | changes the Role capability in the OPEN, so the session must restart |
  | `strict` | yes | changes whether a missing remote Role rejects the session, decided at OPEN |
  | `otc` | no | live, applied through `reconfigure()` |
  | `add-meta` | no | live, affects only what the API prints for the next received UPDATE |

  Reachable is not the same as effective. `reconfigure()` replaces `Peer.neighbor` with the new
  object (`src/exabgp/reactor/peer/peer.py:356`), but the live `Negotiated` still holds the
  neighbour it was built with (`negotiated.py:46`), so a serializer reading
  `negotiated.neighbor.session.role_otc` would read the pre-reload value for the life of the
  session. Give `Negotiated` an explicit `role_otc` field and update it where the peer loop
  consumes `_neighbor` (`peer.py:728`). Do not repoint `Negotiated.neighbor` instead: that would
  also make `outgoing_ttl` and `link_local_prefer` follow a reload, a separate behaviour change
  owed its own test and changelog line. `local` and `strict` need none of this, since a restart
  rebuilds `Negotiated`.
- How far a live `otc` change reaches depends on where a route came from, and the answer is a
  constraint rather than new retained state. Keeping full routes so that any of them could be
  re-marked would rebuild the adj-rib-out an operator running `adj-rib-out false` explicitly
  turned off, at the same memory cost, which is not a trade this feature makes on their behalf.

  | Route source | adj-rib-out cache on | cache off |
  |--------------|----------------------|-----------|
  | configured | the explicit replay covers it; `in_cache()` would otherwise swallow the requeue, since a changed `otc` does not change the route's own attributes | requeued by every reload, so it goes out again and picks up the new marking with nothing added |
  | API | the explicit replay covers it | nothing retains it, so it keeps the marking it was sent with |

  Configured routes are requeued because the configuration parse rebuilds the neighbour before
  the reactor compares any peer: `ParseNeighbor.post()` calls `make_rib()` and then
  `_init_neighbor()` (`src/exabgp/configuration/neighbor/__init__.py:710`), which walks
  `neighbor.routes` and calls `add_to_rib_watchdog()` on each (`:605` to `:610`), reaching
  `add_to_rib()` (`rib/outgoing.py:233`). `add_to_rib()` drops a route only when `in_cache()`
  says it is already known (`:332`), and `in_cache()` returns False immediately when caching is
  off (`rib/cache.py:67`).

  The explicit replay is the caching-enabled path: when `otc` changes on reload the peer marks a
  replay pending and, in the block that consumes `_neighbor`, replays its adj-rib-out through
  `OutgoingRIB.resend()` (`outgoing.py:167`), which walks `cached_routes()`. With caching off
  `Cache.update_cache()` has stored nothing, so API routes cannot be replayed at all. Log that
  once at warning level, naming what is excluded rather than claiming nothing is sent, so the
  operator is not left comparing their configuration against a packet capture:

  ```
  role.otc.reload.partial reason=no-adj-rib-out-cache neighbor=192.0.2.1 otc=send
                          applies-to=configured-routes,new-announcements
                          excludes=routes-announced-through-the-api
  ```

  This is a property of the RIB rather than of OTC: `announce route-refresh` on a neighbour with
  `adj-rib-out false` has the same reach today. Document it that way.
- A live `otc` change moves bytes, never eligibility, which bounds what it can break. Automatic
  marking applies when advertising to a customer, a peer or an RS-client; egress procedure 2
  refuses a route that already carries OTC towards a provider, a peer or an RS. Routes we
  originate carry no OTC before marking, and marking happens at serialization, after eligibility
  has been decided on the route's own attribute. Turning the knob on cannot create a new refusal.
- No `export` token: the core has no source-neighbour provenance for API-originated announcements.
  This does not imply that all helper-originated announcements were locally originated in the
  routing-policy sense.

Without a role, send no local Role capability, activate no OTC routing gate or automatic marking,
and emit no derived role/leak metadata. This is **not** a byte-for-byte compatibility promise for
all input: capability/attribute recognition, named OTC JSON, and malformed OTC treat-as-withdraw
apply even without local role configuration. Differing duplicate Role capabilities remain an OPEN
error even when no local role was advertised.

## Session behavior

When the local role is configured, send exactly one Role capability. If the remote capability is
also present, validate the pair against the five allowed pairs. A mismatch produces
`NOTIFICATION (2, 11)` Role Mismatch.

- Register `(2, 11): 'Role Mismatch'` in `Notification._str_subcode`. That table stops at
  `(2, 10)` today, so without the entry every role notification logs `unknow reason`.
- Identical duplicate Role capabilities are treated as one; differing duplicates produce `(2, 11)`.
  The unpacker must compare with the previously decoded capability before the registry entry is
  overwritten. `Capability.unpack()` already hands the previously decoded instance to
  `unpack_capability()` as `instance`, so that comparison needs no new plumbing. Role `0` is valid;
  use absence checks, never truthiness, for configured roles.
- A missing remote capability is accepted with strict mode disabled. Resolve the **effective**
  remote role as the complement of the local role and run the same procedures as for a confirmed
  pair. Strict mode enabled rejects the missing capability with `(2, 11)`.
- Store a role-negotiation error separately from multisession state and return it through
  `Negotiated.validate()`, which `Protocol.validate_open()` already consumes. Merely storing a
  tuple in `_negotiate()` does not send a notification.
- Enforce a one-octet capability value, with `Notify(2, 0)` on invalid length, matching the house
  convention for a malformed capability. Reject unassigned values 5-255 with `Notify(2, 11)`: such
  a value names a Role no allowed pair can satisfy, so Role Mismatch is the honest subcode.
  Peer input must never be validated with `assert`.

Expose the local role as `role` and effective remote role as `peer_role` in the existing negotiated
API envelope when configured. The underscore is deliberate: that envelope already reads
`message_size`, `hold_time` and `add_path`, and one hyphenated key inside it would be the odd one
out. Per-NLRI keys keep the hyphenated house style, hence `route-leak` below.

Follow that envelope's current placement. `_negotiated()` is spliced into the OPEN and the UPDATE
encoders as well as the `negotiated` message, so this is session state repeated on every message
that already carries it, not a new promise to emit it once. The OPEN JSON describes what was
actually received: do not invent a received capability when `peer_role` was inferred.

## OTC attribute and input/output contract

```
neighbor 192.0.2.1 {
    local-as 65001;
    role { local provider; }

    static {
        route 10.0.0.0/24 next-hop 192.0.2.254 otc provider;
    }
}
```

Three separate questions decide whether an OTC attribute reaches the wire, and each has its own
control. Keep them apart in the implementation as well as in the documentation, because collapsing
any two of them is what makes this feature confusing to operate.

| # | Question | Control | Scope |
|---|----------|---------|-------|
| 1 | Do we negotiate OTC with the peer? | `role { local <name>; strict <enable\|disable>; }` present or absent | session |
| 2 | Do we add OTC to what we send this peer? | `role { otc <send\|disable>; }`, default `send` | session |
| 3 | What does this one route do regardless? | the `otc` token on the route | route |

Those three decide what reaches the wire. What reaches the API is separate and has one control,
`role { add-meta <enable|disable>; }`, covering the `meta` group described under ingress reporting.

Axis 1 is the Role capability in OPEN, the pair validation and the whole RFC 9234 machinery. Without
it there is no negotiated relationship, so axis 2 has nothing to derive a mark from. Axis 2 is the
session default for routes that say nothing. Axis 3 overrides axis 2 for one route, in either
direction.

The `otc` token on a route takes exactly one of these values, so they never combine and there is no
precedence to define:

| Value | Sent? | Value on the wire |
|-------|-------|-------------------|
| absent | follow axis 2 | local ASN when axis 2 adds one |
| `none` | never, even when axis 2 marks | none |
| `self` | always, even when axis 2 is disabled | local ASN of the session announcing it, resolved at the peer |
| `<role-name>` | always, even when axis 2 is disabled | local ASN, with the named relationship asserted |
| `<asn>` | always, even when axis 2 is disabled | that literal ASN |

```
announce route 10.0.0.0/24 next-hop 192.0.2.254            # axis 2 decides
announce route 10.0.0.0/24 next-hop 192.0.2.254 otc none   # never marked
announce route 10.0.0.0/24 next-hop 192.0.2.254 otc self   # marked with our ASN on each session
announce route 10.0.0.0/24 next-hop 192.0.2.254 otc provider  # same, and the relationship checked
announce route 10.0.0.0/24 next-hop 192.0.2.254 otc 65001  # marked with a literal
```

- `none` exists because the role block's `otc` is all or nothing. A helper driving the API needs to exempt one
  announcement without disarming the session.
- `self` and `<role-name>` both resolve to the neighbour's `local-as`, since a route leaving ExaBGP
  is only ever egress-marked and RFC 9234 rule 4 always stamps the local AS. They differ in what
  they assert, not in what they encode. `self` states only that the value comes from the session, and
  works on a neighbour with no `role {}` block. `<role-name>` additionally asserts the relationship
  the route is being marked for and is checked against `role { local ... }`: `otc customer` under
  `role { local provider; }` is a configuration error, and the role form on a neighbour with no role
  block is a configuration error too, because there is nothing to check the assertion against.
- `<asn>` sets a literal and asserts nothing. It is what inline `exabgp encode` uses, since the
  synthetic neighbour `create_configuration_with_routes()` builds carries no role and no session to
  resolve against, and it is what a test asserting exact bytes should use. `exabgp encode -c` reads a
  real configuration, so every form works there.
- Forcing the attribute on does not disable leak prevention. A route carrying OTC by any of these
  spellings is still "OTC already present" for the egress table, so it is still refused towards a
  provider, an RS or a peer under rule 5. `otc self` on a route announced to your provider gets that
  route refused, which is the RFC working as specified and will look like a bug the first time: say
  so in the documentation. `otc none` is how such a route is sent.
- `otc none` on a session with no role configured, or with axis 2 disabled, is a no-op rather than an
  error. A helper should not have to know the session configuration to write a safe announcement.

Two mechanisms implement axis 3, both of them already present in the codebase:

- `self` and `<role-name>` borrow the `next-hop self` parser precedent and then diverge from it on
  where the value is settled. The parser produces an unresolved sentinel carrying what was
  asserted. `Neighbor.resolve_self()` validates the role name against `role { local ... }` and
  rejects a disagreement; that check needs no ASN, and it belongs early, where the operator sees
  it. The **value** is resolved by the serializer against `Negotiated.local_as`, not at parse
  time.

  Resolving it early would be wrong. `local-as auto` is supported on a neighbour with no role
  block, `otc self` is documented to work on one too, and `Session.local_as` stays at `ASN(0)`
  until OPEN settles the real number (`src/exabgp/bgp/neighbor/session.py:51`). An early
  resolution would stamp `AS0` on exactly that combination. `next-hop self` does not have the
  problem because a local address is known at configuration time, and an ASN under `auto` is not.
  Automatic marking already resolves at the serializer, so this adds no mechanism.

  Two consequences. The `OutgoingRIB` unresolved-sentinel guard stays as it is, covering
  `next-hop self` only: an unresolved OTC sentinel is expected in the RIB and must not be refused
  there. And `index()` sees the sentinel, because it is a rendered attribute, so a route with
  `otc self` groups separately from the same route with an explicit ASN even when the two resolve
  to the same number. That is right rather than merely tolerable, since they carry different
  instructions, and it needs none of the identity machinery the `none` case needs below.
  `exabgp encode` with no session cannot resolve `self` or a role name and says so; the numeric
  form is what inline encoding and byte-exact tests use, and the ze parity vectors hold.
- `none` is an internal pseudo-attribute alongside `INTERNAL_NAME`, `INTERNAL_SPLIT` and
  `INTERNAL_WATCHDOG`: in `AttributeCollection.INTERNAL`, `NO_GENERATION = True`, never packed. It
  travels with the route from the API command to the serializer, which is where the insertion
  decision is taken. Both collection renderers skip everything in `INTERNAL`, so a suppressed route
  reads like an ordinary unmarked one in `show adj-rib out` and in JSON, which is consistent with the
  other four and is why suppression logs at debug level with neighbour, family and prefix. Do not add
  a rendering path for it without deciding to make the other four visible too.
- Every form reaches static configuration for free, since static routes and `announce route` share
  `ParseStaticRoute.known`. Accept them there rather than special-casing the API.

Invisible in rendering is not the same as invisible in identity, and `none` has to be part of
route identity even though it never renders. `AttributeCollection.index()` builds its key from
`_generate_text()`, which skips every code in `INTERNAL`, so a suppression marker would be
invisible to the key while deciding what goes on the wire. That is the one combination the
internal set was never asked to hold: `name`, `split`, `watchdog`, `withdraw`, `discard` and
`treat-as-withdraw` are process decisions about a route, and suppression is a decision about its
bytes. Two call sites turn that blindness into wrong output:

- `Cache.in_cache()` (`src/exabgp/rib/cache.py:73`) accepts a route as a duplicate when
  `cached.attributes.index()` equals the new one. Announcing a prefix, then announcing the same
  prefix with `otc none`, is a suppression-only replacement: the two indexes match, the
  announcement is swallowed, and the peer is never told. Zero updates, no log, no error.
- `OutgoingRIB._update_rib()` (`src/exabgp/rib/outgoing.py:364`) keys `_new_attr_af_nlri` by
  `route.attributes.index()` and keeps one collection per key in `_new_attribute`, which
  `_announce_updates()` packs once for every route in the bucket. Two prefixes whose attributes
  differ only in suppression land in the same bucket, and the collection that survives is
  whichever was written last, so both get marked or neither does according to insertion order.
  Path-limit promotion (`outgoing.py:480`) groups on the same key and has the same exposure.

The answer is a policy-aware identity, not a visible attribute:

- Add `AttributeCollection.INTERNAL_IDENTITY`, the internal codes that change what is packed.
  `INTERNAL_OTC_NONE` is its only member.
- `index()` appends a marker for each member present, after the existing text and next-hop part.
  Nothing is appended when no member is present, so every attribute set in the tree keeps the
  index bytes it has today and existing vectors stay byte-identical. Assert that in a test rather
  than assuming it.
- `_generate_text()`, `_generate_json()`, `json()`, `__repr__` and `representation` are untouched,
  so a suppressed route still reads like an unmarked one, as decided above.
- `sameValuesAs()` already compares internal codes, so `AttributeCollection.__eq__` and
  `Route.__eq__` were never affected. Only the derived key is.

`INTERNAL_SPLIT` changes what is emitted as well and is equally invisible to `index()`. It
predates this work and adding it to the identity set would move existing index bytes, so it is
recorded here and left alone.

Normal decoded attribute JSON contains a numeric ASN:

```json
{ "attribute": { "origin": "igp", "as-path": [65002], "otc": 65002 } }
```

Implement OTC as a packed-bytes-first attribute with `OPTIONAL | TRANSITIVE`,
`TREAT_AS_WITHDRAW = True`, a four-byte length check, Buffer input, and decimal ASN text rendering.
Use the existing ASN parser and enforce the unsigned four-octet range without truncation. The
attribute is always four octets, independent of whether four-octet AS_PATH support was negotiated.

Wire registration alone does not enable the documented syntax or JSON:

- Add `otc` to both `ParseStaticRoute.schema` and `ParseStaticRoute.known`, bound to the new
  `static.parser.otc()` function, for static configuration, API `announce route`, and default encode.
  That parser accepts `none`, `self`, a role name or an ASN, returning the suppression marker, an
  unresolved sentinel, an unresolved sentinel carrying the asserted role, or a resolved attribute.
- Add leaves to the IP, VPN and labelled announcement schemas with an explicit OTC-producing
  validator, using the existing `Leaf.validator` override. A bare `ValueType.INTEGER` returns an
  `int`, which is not an attribute and cannot be passed to `AttributeCollection.add()`. The static
  side can name a `ValueType` alone because its `known` dictionary supplies the real parser
  function; the announcement schemas have no such dictionary, which is why they need the override.
  `MEDValidator` and `LocalPrefValidator` in `configuration/validator.py` are the shape to copy.
- Parse the ASN with `ASN.from_string()`, which already rejects negative, non-decimal and
  out-of-range input and already accepts dotted notation. `otc 1.1` therefore renders back as
  `65537`: assert the decimal value on round-trip, not textual identity with the input.
- Add an integer `otc` entry in `AttributeCollection.representation`. `CODE.names` and a class
  `json()` method alone do not control the collection renderer. Preserve existing generic-mode
  output conventions rather than introducing another rendering path.
- Exercise text/JSON output and both default and family-qualified encode paths through their
  actual parsers, not only attribute construction.

RFC 9234 Section 5 is explicit about both of the receive cases the wire can produce.

*"The OTC Attribute is considered malformed if the length value is not 4. An UPDATE message with a
malformed OTC Attribute SHALL be handled using the approach of 'treat-as-withdraw' [RFC7606]."*
RFC 9234 says nothing about the attribute appearing twice, so RFC 7606 Section 3(g) governs:
*"If any other attribute (whether recognized or unrecognized) appears more than once in an UPDATE
message, then all the occurrences of the attribute other than the first one SHALL be discarded and
the UPDATE message will continue to be processed."* The notification case in that paragraph is
reserved for MP_REACH_NLRI and MP_UNREACH_NLRI, so a repeated OTC keeps the first occurrence and the
session stays up. ExaBGP's attribute collection already implements exactly this, so OTC needs no
duplicate handling of its own and must not be given any.

Malformed OTC length invokes the existing RFC 7606 treat-as-withdraw path. Announced NLRI become
withdrawals before leak classification. The existing JSON renderer suppresses internal diagnostic
attributes: this feature promises **withdrawal behavior, not an `"error"` reason** for malformed
OTC. Do not add a malformed case to `route-leak`, and do not claim that the dormant presentation
entry for internal errors is emitted. Packet reporting remains the existing way to inspect the
received bytes.

## Route-aware procedures

### Family scope and withdrawals

Classify each actual announcement using its NLRI `(afi, safi)`. Do not infer one family for the
entire UPDATE from MP_REACH, MP_UNREACH, or their absence. A message may combine native IPv4
announcements with MP announcements or withdrawals of a different family.

On receive, `UpdateCollection` already partitions semantic announces and withdraws and removes
MP_REACH/MP_UNREACH from its attribute collection. On send, MP attributes are generated after common
attribute packing. Consequently `AttributeCollection` cannot discover the required family from
those attributes in either direction.

Only IPv4/IPv6 unicast announcements participate in role-based procedures. Withdrawals, EOR and
attributes-only messages do not acquire automatic OTC or a leak classification. Never block a
withdrawal because retained route attributes contain OTC. Non-unicast announcements bypass these
procedures, including when they share an input UPDATE or semantic collection with unicast routes.
Preserve any explicit valid OTC unchanged, as RFC 9234 Section 5 requires of an attribute once
set; family bypass is not permission to strip it.

### Egress eligibility before serialization

Evaluate whether the route **already** carries OTC before considering automatic insertion:

| Local role | Effective remote role | OTC absent on announcement | OTC already present |
|------------|-----------------------|----------------------------|---------------------|
| provider | customer | add local ASN | allow, preserve value |
| customer | provider | allow without insertion | refuse announcement |
| rs | rs-client | add local ASN | allow, preserve value |
| rs-client | rs | allow without insertion | refuse announcement |
| peer | peer | add local ASN | refuse announcement |

An automatically inserted OTC on a permitted peer announcement must not be mistaken for a
pre-existing OTC and rejected by a second pass.

The "add local ASN" cells are what the role block's `otc` and the route's own `otc` both act on.
The two share a name and nothing else: the first takes a direction, the second takes a value, and
they sit in different places. `role { otc disable; }` empties them for every route on the session,
`otc none` on a route
for one route on every session, and `otc self`, `otc <role-name>` and `otc <asn>` fill them for one
route whatever the session says. None of them touch any other cell of the table: a route that ends
up carrying OTC is refused towards a provider, an RS or a peer however that OTC got there. The "OTC already present" column is
unaffected in both settings, whether the attribute arrived from the wire, from the API or from an
`otc <role>` in the configuration.

Refusal is a **route-level** decision, never an attribute `skip` entry. The existing `skip` dict
omits an attribute but leaves NLRI to be sent; using it for OTC would remove the leak marker and
advertise the forbidden route. Returning empty attribute bytes is not a refusal either.

Apply eligibility in outgoing route selection, before grouping and advertised/path-limit
bookkeeping. Pass the session context from both protocol update send paths. Apply the same
selection to queued announcements, refresh/resend and candidate promotion; rejected routes must
not consume an advertised path slot or be reported as successfully advertised.

Define replacement behavior per neighbour, family, prefix and ADD-PATH identifier:

- An ineligible route with no prior advertisement emits no announcement.
- If a previously advertised route becomes ineligible, withdraw that previous advertisement.
  Suppressing its replacement alone leaves stale routing state at the peer.
- Explicit withdrawals always proceed through the normal withdrawal path. A blocked replacement
  must not cancel a queued withdrawal.
- Replacing a blocked route with an eligible route permits a new announcement.
- Refresh must not resurrect blocked routes. Session teardown clears session-specific admission
  state, and reconnect reevaluates retained desired routes under the new session policy.

This must work with adj-rib-out caching disabled and with or without negotiated path limits.
Neither existing mechanism can answer "was this prefix advertised?" in that configuration:
`OutgoingRIB._admit_path()` returns before touching `_path_selection` when the family has no path
limit, and the adj-rib-out cache is optional. The eligible-to-blocked withdrawal therefore needs
state that does not exist today, and it is the largest single piece of work in Phase 3.

Specify it as its own change rather than a line in the file table:

- **What triggers it.** Roles and strict mode force a session reestablishment on reload, and the
  session policy is fixed for the life of a session. So on a live session a route can only become
  ineligible by being replaced: the API, or a configuration reload, announces the same neighbour,
  family, prefix and ADD-PATH identifier with an OTC that the previous announcement did not carry,
  on a session facing a provider, an RS or a peer. That is the only transition to implement.
- **Where the state lives.** A per-neighbour set of advertised route indexes inside `OutgoingRIB`,
  written where the route is handed to the update generator. Reuse `Route.index()` so that the
  ADD-PATH identifier is part of the key, and reuse `_path_selection` bookkeeping where a path
  limit already populates it rather than tracking the same fact twice. Indexes are all it holds:
  it answers "was this prefix advertised?", and it is not a replay source. It does not need to
  be one, because the only transition above arrives as a replacement announcement which carries
  the NLRI a withdrawal needs.
- **When it is emptied.** When the session it describes ends, and at no other time. That is not
  what `reset()` means today. Teardown reaches `reset()` as intended, through `Peer._reset()`
  (`src/exabgp/reactor/peer/peer.py:270`), `neighbor.reset_rib()` and `RIB.reset()`
  (`src/exabgp/rib/__init__.py:97`). A configuration reload reaches it as well: reload calls
  `make_rib()`, which calls `RIB.enable()`, which reuses the cached `OutgoingRIB` to preserve
  state and then calls `outgoing.clear()` when `adj_rib_out` is false (`rib/__init__.py:80`, and
  the same branch in `__init__` at line 52), and `clear()` is `clear_cache()` plus `reset()`.
  A neighbour running `adj-rib-out false` therefore keeps its `OutgoingRIB` across a reload and
  has its tracking wiped: announce a route, reload, then replace it with an announcement carrying
  OTC on a provider-facing session, and the replacement is refused while nothing remembers the
  prefix was advertised, so no withdrawal goes out and the peer keeps a route we have decided we
  must not give it.

  Add `OutgoingRIB.session_reset()`, which clears the advertised set and then does everything
  `reset()` does. `RIB.reset()` calls it instead of `outgoing.reset()`, and `Peer._reset()` is
  the only caller of `RIB.reset()`, so that path stays disconnect-only. `clear()` keeps calling
  plain `reset()`, so a reload drops queues and cache while the record of what the peer already
  holds survives.

  `self._path_selection = {}` moves out of `reset()` into `session_reset()` with it
  (`outgoing.py:110`). It is the same kind of record: where a family has a negotiated path limit
  it is what says which paths were advertised, and protecting only the new set would leave
  limited families losing theirs on every reload. That also fixes a bug which predates this work.
  With `limit 1`, advertising path A, reloading, then announcing path B admits B because
  `selection.advertised` is empty again and the limit counts from zero, and the peer ends up
  holding two paths for a prefix it was promised one of. Two things make preservation safe:
  `RIB.enable()` calls `delete_cached_family()` before `clear()`, which already prunes
  `_path_selection` for families no longer configured (`outgoing.py:119`), and a path-limit
  change is a capability change, so `Neighbor.__eq__` compares it through `self.capability ==
  other.capability` and the session restarts, reaching `session_reset()` anyway. A limit never
  changes under a surviving `_path_selection`.

  `reset()` also advances `_session_epoch`, which aborts an `updates()` generator mid-batch, so a
  reload with `adj-rib-out false` abandons an in-flight batch as though the session had gone.
  That predates this work and is left alone, but a test written for the reload case should not
  be surprised by it.
- **What bounds it.** One entry per advertised route, so it is bounded by the adj-rib-out the
  operator already asked for. Say so in the code with a named constant or an assertion tying its
  size to the route count, per Tiger Style.
- **What stays separate.** Desired-route state and advertised state must remain distinguishable:
  a blocked route is still desired, still listed by `show adj-rib out`, and becomes advertisable
  again the moment a replacement carries no OTC.

A refusal is silent on the wire: the peer is simply never told about a route the operator asked for.
The log line is the only trace, so it answers the same questions the leak annotation does, with the
same field discipline. One fact per field, every key naming what it holds, no bare numbers:

```
rib.otc.refused reason=otc-restricted neighbor=192.0.2.1 peer-role=provider peer-as=AS65002
                expected-peer-role=customer,rs-client family="ipv4 unicast" prefix=10.0.0.0/24
                route-otc=AS65001
```

| Field | Holds |
|-------|-------|
| `reason` | the fault alone: the route is restricted by its OTC and this peer may not receive it |
| `peer-role` | the effective role of the peer we were about to announce to |
| `peer-as` | that peer's AS number, so the line identifies its session on its own |
| `expected-peer-role` | the roles that could have received it, which is why this one could not |
| `route-otc` | the AS in the OTC the route already carried, the thing that restricts it |
| `family`, `prefix` | which route was withheld |

- `reason` is `otc-restricted` for all three refusing rows. What differs between them is `peer-role`,
  exactly as `invalid-otc` is one reason across three roles on the ingress side. Never fold the role
  into the reason.
- `expected-peer-role` mirrors `expected-otc`: it names the rule that was broken rather than
  restating the observation, so a reader who has never heard of OTC learns that a route carrying one
  may only go downstream to a customer or an RS client, which is the whole of RFC 9234 rule 5.
- `route-otc` is written `AS<n>`, never a bare number, for the same reason `received-otc` is.
- A refusal must not close an otherwise healthy BGP session, and the line is logged at warning level
  because a route the operator configured is not reaching its peer.
- If a JSON event for refusals is ever added, it reuses these field names. Do not invent a second
  vocabulary for the same facts.

### Egress insertion after admission

Insert OTC only while producing the outgoing attributes for an eligible, in-scope announcement,
using `Negotiated.local_as`. Whether to insert is the axis 2 and axis 3 question already settled
above: the route's own `otc` token decides when it has one, the session knob decides otherwise.
A route carrying `otc self` or `otc <role-name>` arrives here already resolved, so the serializer
inserts a value it was given rather than one it derives.

`Negotiated.local_as` is `sent_open.asn`, the real local ASN: `ASN.trans()` is applied at pack time
for AS_PATH and AGGREGATOR only, and OTC carries four octets whether or not ASN4 was
negotiated. A four-octet local ASN talking to a peer without ASN4 support must still stamp the real
number, never AS_TRANS, and a test must cover exactly that pairing. Never mutate the shared `AttributeCollection`,
its cached text/JSON/index, or stored desired-route attributes.

Make the family/announcement context explicit at the serializer boundary. Partition mixed-family
collections before selecting output attributes; do not reuse one automatically stamped attribute
blob for both in-scope and out-of-scope families.

Choosing attributes per family is not sufficient on its own, because the families cannot be told
apart on the wire as things stand. `UpdateCollection.messages()` puts IPv4 unicast and IPv4
multicast in one list (`src/exabgp/bgp/message/update/collection.py:327` and `:355`) and packs
both into the legacy NLRI field, which carries no AFI or SAFI at all. Probed directly:

```
unicast   bytes 180a0000 family (ipv4, unicast)
multicast bytes 180a0000 family (ipv4, multicast)
identical on the wire: True
```

A receiver reads that field as IPv4 unicast, because RFC 4271 gives it no other meaning, so an
IPv4 multicast route announced through it arrives as unicast and for the same prefix can
overwrite a correctly marked unicast route. Splitting the block by SAFI before packing would
produce two messages with identical bytes and fix nothing: the distinction was never on the wire.

Put the families where the wire says which is which, which is MP_REACH_NLRI and MP_UNREACH_NLRI
(RFC 4760). Narrow the `is_v4` test at `collection.py:327` and `:355` to `SAFI.unicast`, and IPv4
multicast falls through to the MP branches, which already key on `nlri.family().afi_safi()`.
Announces qualify at line 334 because an IPv4 multicast route carries a defined next-hop AFI, and
withdraws reach `mp_withdraws` at line 362 with no further change. The legacy block becomes
unicast-only by construction, so no per-SAFI split is needed there at all. Expect byte-exact
functional encoding expectations to move for any test announcing IPv4 multicast, and update them
as part of the change rather than after it.

This is a pre-existing defect rather than one this feature introduces: ExaBGP advertises IPv4
multicast as IPv4 unicast today whenever the family is negotiated. It deserves its own commit,
its own tests and its own issue, and it has to land before the egress work, which cannot enforce
a family scope the wire does not carry. Tests must assert the decoded family, not only whether
OTC is present.

`messages()` does also pack `attr` once and reuse it across the legacy block and every MP family,
but the RIB never hands it a multi-family collection: `_generate_updates()` keys on
`(attr_index, family)` and `_announce_updates()` builds one `UpdateCollection` per family
(`src/exabgp/rib/outgoing.py:530` and `:558`). The shared blob therefore only matters for
collections built outside the RIB, such as an API request supplying attributes and NLRI directly.
Preserve sorted attribute encoding, correct
message-size accounting and fragmentation after insertion. Keep ORIGIN/AS_PATH/LOCAL_PREF default
callables unchanged unless their actual contract needs changing.

### Ingress leak reporting

For each supported family with announcements, a pre-existing OTC means:

| Effective remote role | What was acceptable | Leak condition | Reason |
|-----------------------|---------------------|----------------|--------|
| customer | none | OTC present | `invalid-otc` |
| rs-client | none | OTC present | `invalid-otc` |
| peer | OTC equal to the remote ASN | OTC differs | `invalid-otc` |
| provider or rs | any OTC, or none | never | not a leak |

Compare with `Negotiated.peer_as`, which `_negotiate()` already resolves from the ASN4 capability
when the OPEN carried AS_TRANS. Never compare against the raw OPEN ASN or an AS_PATH guess.
Classify after malformed-attribute conversion and before API dispatch, in `Protocol.read_message()`
between `Message.unpack()` and the `for_api` dispatch.

`read_message()` returns `_UPDATE` without parsing when adj-rib-in is off, no process subscribes to
updates and routes are not logged. A configured role must defeat that fast path, otherwise the
promised leak warning cannot exist. Accept the cost knowingly: a full-table session that opted out
of parsing now parses every UPDATE. That is the price of the warning, it applies only to sessions
that configured a role, and it is the reason no drop-mode knob is offered on top of it.

A detected leak remains visible to subscribed helpers and is cached in adj-rib-in when that cache
is enabled. RFC ineligibility is not a requirement to hide wire observations; ExaBGP has no Loc-RIB
selection to exclude it from. Helpers performing route selection must exclude these announcements.

The leak report belongs on each **affected announced NLRI**, not at UPDATE level, and it goes under
a `meta` object rather than beside `nlri`.

The keys of an announcement entry describe what the peer put on the wire: the prefix, and where the
encoding carries them, the path identifier, labels and route distinguisher. A leak report is none of
those. It is ExaBGP's own conclusion about the route, produced by a check the peer knows nothing
about, and sitting it beside `nlri` would claim otherwise. `meta` says what it is, keeps wire data
and observation apart for anything parsing the entry, and gives later observations somewhere to go
that is not another sibling of `nlri`.

Inside it, write the report for the engineer who has never heard of RFC 9234. They are reading a log
because something broke, they see a key called `route-leak`, and it has to say why the route was
reported without sending them to the RFC first: what was wrong, who sent it, what we required, what
we got.

```json
{
  "update": {
    "attribute": { "otc": 65003 },
    "announce": {
      "ipv4 unicast": {
        "192.0.2.1": [
          {
            "nlri": "10.0.0.0/24",
            "meta": {
              "route-leak": {
                "reason": "invalid-otc",
                "peer-role": "peer",
                "peer-as": "AS65002",
                "expected-otc": "peer-as",
                "received-otc": "AS65003"
              }
            }
          }
        ]
      }
    }
  }
}
```

```json
{
  "nlri": "10.0.0.0/24",
  "meta": {
    "route-leak": {
      "reason": "invalid-otc",
      "peer-role": "customer",
      "peer-as": "AS65002",
      "expected-otc": "none",
      "received-otc": "AS65003"
    }
  }
}
```

| `peer-role` | `reason` | `expected-otc` |
|-------------|----------|----------------|
| `customer` | `invalid-otc` | `none` |
| `rs-client` | `invalid-otc` | `none` |
| `peer` | `invalid-otc` | `peer-as` |

**`meta.route-leak` is self-sufficient.** It describes the issue completely on its own, and reading
it requires nothing from the entry around it, the shared attribute block, the neighbour envelope or
the RFC. An entry grepped out of a stream, one prefix quoted into a ticket or a single log line is
still a complete report. Every rule below follows from that, including the two deliberate
duplications: `peer-as` repeats the envelope and `received-otc` repeats `attribute.otc`.

- One field, one concept. `reason` is the fault and nothing else: the route carried an OTC this
  peer was not entitled to send. Who sent it is a different fact and lives in `peer-role`, what was
  required is a third and lives in `expected-otc`. `invalid-otc-from-customer` welded the fault to the
  relationship, which meant a consumer wanting to group by fault had to parse the string apart, and
  the set of reasons grew every time a role was added.
- `peer-role` is the effective remote role, whether confirmed by the peer's Role capability or
  inferred as the complement of the local role. It is the same vocabulary as the `peer_role` key in
  the negotiated envelope, so a reader learns one set of role names for the whole API.
- `peer-as` is the peer's AS number, always present whatever the role. Without it
  `expected-otc: peer-as` says which rule applied but not which AS satisfied it, and the report
  cannot be traced back to a peer. The envelope carries the ASN too; a report that needs its
  envelope attached is not self-sufficient, so it is repeated here.
- `expected-otc` and `received-otc` are the comparison the classifier made, in that order. Each
  name says which field it is about, so a reader scanning the object never has to work out what was
  expected or what was received: it is in the key. Bare `expected` and `received` would leave that
  to inference the moment the object gains a field, and this one already has three others.
- **No value in this object is a bare number.** A bare `65003` could be an ASN, a timestamp, a
  counter or an index, and a reader who does not know the feature has no way to tell. Every value
  says what it is, so the object can be read aloud.
- `expected-otc` is the rule that was broken, not a value: `none` when the peer role may send no
  OTC at all, `peer-as` when it may only send its own. Where it names `peer-as` it names a field of
  this same object, so the ASN is one line away and the reader never has to work out which AS that
  was. Putting `AS65002` there instead would have said what was wanted while losing why.
- `received-otc` is the AS that set the marker, written `AS<n>` in the notation an operator already
  reads everywhere else. It repeats `attribute.otc`, and that repetition is the point: the attribute
  block belongs to the whole UPDATE while this report belongs to one prefix, so a reader holding the
  report alone must still see what arrived. It is the one concrete value in the object, and it is the one the reader
  needs, because it belongs to neither of us and that is what makes the route a leak.
- Both keys are therefore always strings. Nothing in the object changes type between events, and a
  consumer that wants to branch reads `reason`, which is a fixed set.
- `peer-as` is `Negotiated.peer_as`, the value the classifier actually compared, not the configured
  `session.peer_as` the envelope reports. Where they differ the annotation shows what was compared.
- The warning log carries the same three values, so the log and the JSON never disagree and neither
  needs the other to be understood.
- This renames the three strings ze uses. Parity now covers the wire, the role names and the concept
  rather than the diagnostic vocabulary: a classification that does not say what was wrong was not
  worth keeping for symmetry with another product.

The route's own OTC is reported in `attribute` exactly as before, whether or not `meta` is present.
The attribute block is the faithful decode of what the peer sent, and it must not change because we
did or did not flag something: an OTC that never triggers a leak is still an attribute the peer sent
and still belongs in the output. The two are separate contracts and render accordingly, `attribute`
carrying a number like every other ASN-bearing attribute in ExaBGP's JSON, `meta` carrying `AS<n>`
because it has to read on its own.

`meta` is absent entirely when `add-meta` is disabled, and on clean announcements, unsupported
families, withdrawals, EOR and updates without a configured local role: an empty wrapper on every prefix would cost more than it
says. No `valid` flag, generic `validation` wrapper or derived ingress stamp report is added, and
`meta` gains no other key in this feature.

Per-NLRI JSON is produced by the NLRI itself through `JSON._nlri_to_json()`, and in compact mode an
INET NLRI renders as a bare string rather than an object, so there is nowhere to hang `meta`. Give
`_nlri_to_json()` an optional metadata argument and render the object form when metadata is
present. The NLRI keeps producing its own wire keys and never learns what `meta` contains; the
encoder adds the wrapper. That is what keeps the observation out of the NLRI object, which the plan
requires anyway since NLRI objects must not be mutated. `INET.json()` already prefers the object form over compact whenever the NLRI carries extra
content, so a leaked prefix appearing as an object in compact output follows existing behaviour
rather than inventing a rule. Losing the report because of a display mode is not acceptable, and the
same hook covers the `v4_json` path. Clean prefixes in compact mode keep rendering as bare strings.

Own classification as semantic `UpdateCollection` metadata: `route_leaks`, a map from family to a
small frozen record holding reason, peer role, peer AS, expected OTC and received OTC as finished
strings, empty by default and
bounded to the two supported families. Format them into the record at classification time, where the
negotiated ASNs are at hand, so the JSON encoder and the logger both read the same finished values
and cannot drift. All affected announcements of one family share
the session and the common OTC, so every field is per family and per-prefix storage is unnecessary.
Build the record once at classification time; the renderer formats it and derives nothing. Populate it
before `Processes._update()` passes `update.data` to the renderer; putting it only on the wire
`Update` wrapper loses it. Do not place this metadata in the cached `AttributeCollection` or mutate
NLRI objects. Render it only on the corresponding announcement entries, inside `meta`.

Leak metadata is an API event annotation, not a persisted `Route` attribute or a new promise for
`show adj-rib in`. The warning log carries the annotation's fields under the same names, with
neighbour, family and prefix besides, so an operator who only has the log learns as much as one
reading the API stream and neither has to translate between two vocabularies:

```
update.otc.leak reason=invalid-otc neighbor=192.0.2.1 peer-role=customer peer-as=AS65002
                expected-otc=none received-otc=AS65003 family="ipv4 unicast" prefix=10.0.0.0/24
```

An operator reading the log should not need the JSON to know what was compared. No drop-mode knob.
Wire packet reports remain unchanged, while semantic API output continues to reflect existing
RFC 7606 transformations.

### Deliberate ingress-marking divergence and helper responsibility

`role { otc receive; }` and `role { otc send/receive; }` are rejected, because accepting either
would promise the ingress marking below that this feature does not implement. The error says so in
those words. When that work lands it accepts the two values and nothing else about the token
changes.

RFC 9234 Section 5 requires adding the remote ASN as OTC to an unmarked route received from a
provider, peer or RS. This feature does not add that attribute to adj-rib-in or normal attribute
JSON. This preserves the chosen observation interface, but it is a **conformance limitation**, not
evidence that ingress marking protects nobody.

A helper redistributing received routes must:

1. Exclude leak-classified announcements from eligible routes.
2. For IPv4/IPv6 unicast received from a provider, peer or RS without OTC, attach OTC equal to the
   remote ASN before redistributing the route, including over an internal session.
3. Preserve an existing valid OTC and its value, and process withdrawals normally.

The negotiated `role`/`peer_role`, remote ASN and received attributes provide the necessary inputs.
The core cannot reconstruct a received route's provenance from an arbitrary later API announcement.
Full ingress support would require a separately specified distinction between received and
effective routing attributes; it is not silently delivered by this plan.

## Parity with ze

Retain the five role names and the integer OTC ASN. The leak vocabulary deliberately diverges:
ze's `otc-from-customer` and `otc-asn-mismatch` fold the fault, the relationship and the check into
one string, and ExaBGP reports them as separate fields. Parity covers wire
behaviour and vocabulary, not configuration syntax: ze's `import` token becomes `local` here, as
argued above. Envelopes follow each product's conventions: ExaBGP uses the per-announcement JSON
above and lowercase `otc`;
ze's decoded attribute envelope is `{ "name": "otc", "value": 65000 }`.
`Role.json()` uses `{ "name": "role", "value": "customer" }`.

Shared vectors are attribute `c02304 0000fde8` -> ASN `65000`, and capability **payload** `03` ->
`customer`; the complete capability TLV is `09 01 03`. Test semantic decoding as well as the value
types. Identical names do not imply identical routing behavior: ingress marking deliberately differs.

The original draft records ze-side `SupportsAttr`/`--attr` framework work. That is a separate
repository deliverable whose current status must be checked there before claiming cross-product
parity. It is not an ExaBGP implementation prerequisite or permission to expand this change into ze.

## Implementation

### Phase 1 - Role capability and session lifecycle

| File | Change |
|------|--------|
| `src/exabgp/bgp/message/open/capability/capability.py` | code 9 and display name |
| `src/exabgp/bgp/message/open/capability/role.py` (new) | Role encoding, length/value validation, duplicate comparison, JSON/text |
| `src/exabgp/bgp/message/open/capability/__init__.py` | registry import and export |
| `src/exabgp/bgp/message/open/capability/capabilities.py` | generate one local Role capability |
| `src/exabgp/bgp/message/open/capability/negotiated.py` | local/effective remote roles, pair/strict validation, error state consumed by `validate()`, sentinel defaults |
| `src/exabgp/bgp/message/notification.py` | `(2, 11): 'Role Mismatch'` in `_str_subcode` |
| `src/exabgp/bgp/neighbor/session.py` | `role`, `role_strict`, `role_otc` and `role_add_meta` fields beside the existing tcp-ao fields |
| `src/exabgp/bgp/neighbor/settings.py` | the same four fields for settings conversion |
| `src/exabgp/bgp/neighbor/neighbor.py` | compare `local` and `strict` in outer `Neighbor.__eq__()` and deliberately not `otc` or `add-meta`, config dump |
| `src/exabgp/configuration/role.py` (new) | neighbour subsection parser using existing Section patterns |
| `src/exabgp/configuration/configuration.py` | parser registration and clear lifecycle |
| `src/exabgp/configuration/neighbor/__init__.py` | schema, inherited settings mapping, explicit-AS and eBGP validation |
| `src/exabgp/configuration/encoder.py` | JSON configuration encoding |
| `src/exabgp/reactor/api/response/json.py` | conditional role fields in the existing negotiated envelope |

Keep `local` as a token/dictionary key, not a Python identifier. Two fields do not earn a new
module: tcp-ao is the precedent for the subsection parser *and* for where the fields live, and its
four fields sit flat in `session.py` and `settings.py`. Model the subsection on
`configuration/tcpao.py`; use the neighbour's post-inheritance validation boundary. Verify reload
through the existing `Reactor` comparison/reestablishment path rather than changing only field-group
equality. Exercise `Protocol.validate_open()` to prove that stored errors actually reject a session.

### Phase 2 - OTC attribute and complete parser/rendering integration

| File | Change |
|------|--------|
| `src/exabgp/bgp/message/update/attribute/attribute.py` | code 35 and display name |
| `src/exabgp/bgp/message/update/attribute/otc.py` (new) | packed attribute, four-byte validation, treat-as-withdraw, ASN factories/rendering |
| `src/exabgp/bgp/message/update/attribute/__init__.py` | registry import |
| `src/exabgp/bgp/message/update/attribute/collection.py` | integer OTC presentation entry, `INTERNAL_OTC_NONE` in `INTERNAL` |
| `src/exabgp/bgp/message/update/attribute/attribute.py` | `INTERNAL_OTC_NONE` code beside the other internal codes |
| `src/exabgp/configuration/static/parser.py` | OTC-producing parser using existing ASN conventions |
| `src/exabgp/configuration/static/route.py` | static schema and known-parser registration |
| `src/exabgp/configuration/announce/ip.py`, `vpn.py`, `label.py` | OTC leaves with explicit OTC-producing validators |
| `src/exabgp/configuration/validator.py` | `OTCValidator`, modelled on `MEDValidator`, accepting a role name or an ASN |
| `src/exabgp/bgp/neighbor/neighbor.py` | resolve the OTC role sentinel in `resolve_self()`, validate it against the configured role |
| `src/exabgp/rib/outgoing.py` | extend the existing unresolved-sentinel guard to OTC |
| `tests/unit/` | attribute round-trip, bounds, malformed length, shared ze vectors |

Reuse the existing treat-as-withdraw conversion, not attribute discard or session reset for a
well-framed OTC with the wrong payload length. Preserve existing handling for truncated attribute
framing. Do not introduce a new diagnostic JSON feature under the assumption that it already exists.

### Phase 3 - route-aware procedures and semantic reporting

| File | Change |
|------|--------|
| `src/exabgp/rib/outgoing.py` | route eligibility, replacement withdrawals, advertised-state lifecycle, refresh/promotion integration before path-limit admission |
| `src/exabgp/rib/__init__.py` | `RIB.reset()` calls the new session-scoped clear; `RIB.enable()` and `RIB.__init__()` keep calling `clear()`, which must preserve advertised state |
| `src/exabgp/reactor/protocol.py` | pass session policy through both outbound update paths; classify ingress before API dispatch; respect roles in parsing fast-path decisions |
| `src/exabgp/bgp/message/update/collection.py` | IPv4 multicast to MP_REACH/MP_UNREACH as its own landing; family-aware output partitioning/insertion context; bounded per-update leak metadata |
| `src/exabgp/bgp/message/update/attribute/collection.py` | explicit non-mutating OTC insertion context, never route refusal in `skip` |
| `src/exabgp/reactor/api/response/json.py` | annotation argument on `_nlri_to_json()`, leak reason on affected announced NLRI only |
| `qa/encoding/*.conf`, `*.ci` | explicit OTC, automatic OTC under `role { local provider; }`, no automatic OTC under `role { local customer; }` |
| `etc/exabgp/` | one example configuration carrying a `role {}` block |
| `doc/`, `CHANGELOG` | role/OTC syntax, JSON keys, and the stated conformance boundary |

Keep classification on semantic data and admission on route state. `Processes._update()` already
hands `UpdateCollection` to encoders; use that handoff rather than a parallel metadata channel.
Migrate all callers of any changed serializer/RIB interface, including direct encode/pack consumers
and both protocol update send paths. Standalone encoding with no role continues to encode explicit
OTC without inventing a session policy.

Phases 1 and 2 may ship separately, labelled **wire/config/API support only**. Neither includes
automatic route-leak prevention until Phase 3 is implemented and verified.

## Acceptance scenarios

Use existing unit and functional suites for observable boundary and state-transition regressions.
No test should merely assert registry wiring or the presence of a source-code string.

### Session and configuration

- A reload changing only `otc`, or only `add-meta`, leaves the session established and logs no
  reestablishment. A reload changing `local` or `strict` restarts it.
- A reload changing `otc` on an established session changes what the serializer marks, proving
  the value is not snapshotted into `Negotiated` at OPEN time.
- Reload changing `otc` with adj-rib-out caching enabled: previously advertised routes are sent
  again with the new marking, whatever their source.
- Reload changing `otc` with caching disabled, configured route: announced again with the new
  marking. Same reload, API-announced route: not announced again, and the partial-reload warning
  names the API as what it excludes.

- All five capability values round-trip, including provider `0`; invalid lengths and unassigned
  values reject without Python exceptions.
- All 25 local/remote pairs yield the specified establishment or `(2, 11)` result through the
  notification consumer, not merely a stored tuple. The notification renders as `Role Mismatch`
  rather than `unknow reason`, which is what proves the subcode was registered.
- An unassigned role value 5-255 is rejected with `(2, 11)`, and a wrong capability length with
  `(2, 0)`, neither raising a Python exception.
- Identical duplicates are accepted; differing duplicates reject, including without a configured
  local role. No generated OPEN advertises duplicate Role capabilities.
- Omitted strict mode accepts a missing remote capability, and each complement fallback takes the
  same routing branches as a confirmed pair. Strict mode rejects the missing capability.
- Empty role blocks and strict-only blocks fail; template-inherited `local`, `strict`, `otc` and
  `add-meta` work.
- `role { otc ... }` accepts `send` and `disable`; `receive` and `send/receive` are rejected with an
  error naming ingress marking as unimplemented, not the value as unknown; anything else is an
  unknown value.
- The role block's `otc` and a route's `otc` do not share a value set: neither accepts the other's
  values, and a route still parses its own `otc` on a neighbour whose role block sets one.
- `otc <role>` matching the configured role resolves to `local-as`; a non-matching name fails; the
  same route under a neighbour with no `role {}` block fails; all five names resolve identically.
- `otc self` resolves to `local-as` on a neighbour with a role and on one without, which is the
  difference between the two spellings.
- One route announced to two neighbours with different `local-as` is marked with each neighbour's
  own ASN, which is what "resolved at the peer" has to mean.
- An unresolved OTC sentinel never reaches the RIB, proven by the existing guard rather than by
  inspecting the parser.
- `otc <role>` and `otc self` are rejected by inline `exabgp encode`, which builds a neighbour with
  no role and no session, and accepted by `exabgp encode -c` with a real configuration.
- Changing the role block's `otc` or `add-meta` on reload keeps the session up; changing `local` or
  `strict` reestablishes it.
- `add-meta disable` removes the group from the API output while the warning log, the refusals and
  the classification behind them continue unchanged.
- Equal ASNs and either automatic ASN are rejected when a role is configured; ordinary no-role
  automatic-AS configurations retain their behavior.
- Role-only and strict-only reloads reestablish the session and change the effective negotiation.
- Negotiated JSON distinguishes effective fallback state from actual received OPEN capabilities;
  no-role sessions acquire no derived role fields.

### Attribute, configuration and API

- OTC round-trips with two- and four-octet AS_PATH negotiation; test a four-octet ASN and numeric
  bounds, rejecting overflow/negative configuration without truncation.
- A four-octet local ASN facing a peer that did not negotiate ASN4 stamps the real ASN, never
  AS_TRANS, while AS_PATH on the same message still carries AS_TRANS.
- Dotted input such as `otc 1.1` is accepted and renders as `65537`.
- Static block, inline API route, family-qualified IP/VPN/label announcement, default encode and
  family-qualified encode accept OTC through their real parser paths, in both spellings where the
  path has a neighbour to resolve against.
- A resolved role-named OTC is indistinguishable downstream from a numeric one: same bytes, same
  JSON, same text, same `index()`, and it shares the attribute cache with the numeric form.
- Normal JSON emits integer `otc`, text renders a reusable decimal ASN, and generic output follows
  existing conventions. Check the shared ze vectors and complete capability TLV.
- Wrong OTC lengths convert supported legacy and MP announcements into withdrawals without
  resetting the session or emitting `route-leak`; no malformed-OTC `"error"` diagnostic is promised.
- Explicit OTC decode and malformed handling work without role configuration and independently
  of whether automatic procedures apply to the NLRI family.
- CLI round-trip:
  `./sbin/exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4 otc 65000" | ./sbin/exabgp decode`.
- Announce a prefix, then announce the same prefix and next hop with `otc none`: the second
  announcement reaches the peer as a real update instead of being swallowed as a duplicate, with
  adj-rib-out caching both on and off.
- Announce two prefixes with otherwise identical attributes, one `otc none` and one not, in both
  insertion orders: exactly one carries OTC on the wire in both runs.
- An attribute set holding no identity-bearing internal code produces the same `index()` bytes as
  before the change.
- `otc self` on a neighbour with `local-as auto`: the OPEN settles the ASN and the announcement
  carries that ASN, never `AS0`. Same for `otc <role-name>`, and a name disagreeing with the
  configured role is still refused at configuration time, before any session exists.
- `exabgp encode` with `otc self` and no session: a clear error rather than `AS0`.

### Egress and family boundaries

- Exercise every row of the egress table with OTC absent and present; a peer receives newly
  stamped routes but not routes that already carried OTC.
- An outgoing route that already carries an OTC equal to our own local ASN is left exactly as it is:
  the value is not rewritten, no second attribute appears, and the wire bytes match what was stored.
- A received UPDATE carrying two OTC attributes keeps the first, discards the second and continues
  to be processed with the session up, per RFC 7606 Section 3(g).
- Repeat the three marking rows with `role { otc disable; }`: no attribute is added, and the refusal rows
  still refuse, which is the test that proves the knob did not disable the protection.
- Cover the route-level override in both directions against both session settings: `otc none` with
  the session marking leaves that route bare while its neighbours in the same UPDATE are stamped,
  and `otc self`, `otc <role-name>` and `otc <asn>` each mark their route with the session knob
  disabled while the routes around them stay bare.
- `otc none` never appears on the wire, and is a no-op rather than an error on a session with no
  role configured or with marking already disabled.
- A route forced to carry OTC by any spelling is still refused towards a provider, an RS and a peer,
  which is what proves forcing the attribute did not disarm rule 5.
- A route carrying `otc <role>` is refused towards a provider, an RS and a peer exactly as a route
  carrying a wire-received OTC is, with `otc` enabled and disabled alike.
- Check actual serialized announcements, not just packed attribute bytes: refusal sends neither
  the forbidden NLRI nor a marker-stripped version, preserves session health, and logs the route
  with every field above, since the log is the only trace a refusal leaves.
- Shared attributes sent to customer/provider destinations produce the appropriate per-session
  result without changing stored attributes or cached text/JSON/index.
- Cover eligible -> blocked withdrawal, blocked -> eligible announcement, explicit withdrawals
  with OTC, refresh/resend, reconnect, and candidate promotion under path limits.
- Repeat relevant transitions with adj-rib-out cache disabled and path limits absent; ensure
  rejected routes neither consume slots nor survive remotely as stale advertisements. The
  eligible-to-blocked withdrawal in exactly that configuration is the test that proves the new
  advertised-route state exists, since neither the cache nor `_path_selection` can answer it.
- Advertised-route state is empty after a disconnect, so a reconnect re-announces rather than
  believing the peer still holds the previous advertisement.
- Native IPv4 and MP IPv6 unicast receive the procedures; VPNv4, EVPN, FlowSpec and multicast do
  not. Cover both MP_REACH and MP_UNREACH-only traffic.
- IPv4 unicast and IPv4 multicast announced together produce OTC on the unicast NLRI only, which
  requires the serializer to split them into separate messages. Assert the resulting wire bytes,
  not only the attribute contents.
- Mixed native IPv4 announcements plus out-of-scope MP withdrawals still check the IPv4 routes.
  Mixed in-scope/out-of-scope announcements receive only the applicable marking/classification.
- Withdraw-only, EOR and attributes-only output acquire no automatic OTC. Preserve withdrawals
  in mixed messages when announcements are rejected.
- OTC insertion respects message-size boundaries and fragmentation without contaminating another
  family's output attributes.
- Functional encoding includes explicit OTC, automatic OTC with `role { local provider; }`,
  and no automatic OTC with `role { local customer; }`.
- Announce IPv4 multicast: the UPDATE carries MP_REACH_NLRI and decodes as `(ipv4, multicast)`,
  not as unicast. Withdraw it: the UPDATE carries MP_UNREACH_NLRI and decodes the same way.
- Announce the same prefix as IPv4 unicast and IPv4 multicast on a marking session: the unicast
  route carries OTC, the multicast route does not, and neither decodes as the other.
- A session teardown empties the advertised set and `_path_selection`; a reload does not.
- With a negotiated path limit and `adj-rib-out false`: advertise a path, reload, then announce a
  replacement carrying OTC on a provider-facing session, and check the original is withdrawn.
- With `limit 1` and `adj-rib-out false`: advertise path A, reload, announce path B, and check
  that A stays advertised and B is held as a candidate, with nothing announced and nothing
  withdrawn by the reload. Today the reload empties `selection.advertised`, so B is admitted as
  though the slot were free and the peer ends up holding both.
- A reload that drops a family still clears that family's `_path_selection`.

### Ingress reporting and observation boundary

- The report appears under `meta` on exactly the affected announcement entries; clean routes,
  unsupported families and withdrawals sharing the UPDATE carry no `meta` key at all.
- With `add-meta disable` no entry carries `meta`, while the warning log, the refusals and the
  classification behind them are byte-for-byte what they were with it enabled.
- Nothing outside `meta` changes on an annotated entry: the wire keys an NLRI renders are identical
  to the ones it renders when the route is clean, and `attribute.otc` renders identically whether
  the route leaked or not.
- The report can be read with the rest of the message removed: reason, peer role, peer AS, what was
  required and what arrived are all inside it.
- The object carries `reason`, `peer-role`, `peer-as`, `expected-otc` and `received-otc` in all
  three cases.
- `peer-as` is present for every role, so a leak entry identifies its peer without the envelope.
- `reason` is `invalid-otc` in all three; the cases differ in `peer-role` and `expected-otc`, never
  folding the role into the reason.
- `peer-role` reports the inferred complement when the peer sent no Role capability, and the
  confirmed role when it did.
- `expected-otc` is `none` for a customer and an RS client, and `peer-as` for a lateral peer.
- `received-otc` renders as `AS<n>`, never a bare number, including for a four-octet ASN.
- `peer-as` carries the negotiated peer ASN, proven by a session where the negotiated peer ASN and
  the configured one differ, and by a four-octet peer reached behind AS_TRANS.
- The leak warning and the refusal warning use the field names of their JSON counterpart, so a
  reader moving between the log and the API stream never has to translate.
- The refusal log names `reason`, `peer-role`, `peer-as`, `expected-peer-role` and `route-otc`, and
  identifies its session without the surrounding context.
- A leak is reported for the family it affects and not for another sharing the UPDATE.
- A leak is reported for every affected prefix of the family and for no other.
- Compact JSON renders a leaked prefix as an object carrying `meta` and a clean prefix as a bare
  string, in both the current and the `v4_json` renderer.
- A peer's matching four-octet ASN is accepted; a mismatch reports `expected-otc: peer-as`,
  `peer-as` as the four-octet value and `received-otc: AS<n>`, in the JSON and in the log alike.
- Leaks reach subscribed helpers and enabled adj-rib-in caches; classification survives the
  wire-to-semantic API handoff without leaking through shared attribute-cache state.
- Role-enabled parsing still produces the promised warning when API delivery and adj-rib-in
  caching are disabled. No new API subscription is enabled implicitly.
- An unmarked provider/peer/RS route stays unmarked in ExaBGP's observation output, as documented;
  its effective role/remote ASN are available for helper-side marking.

Run `./qa/bin/test_everything` before declaring the implementation complete. This document revision
is not an implementation test result.

## Decisions and resume point

The configuration is organised around three questions which do not have to agree with each other:
whether OTC is negotiated with the peer, whether it is added to what we send that peer, and what a
given route does regardless. The route-level token takes exactly one of `none`, `self`,
`<role-name>` or `<asn>`, so an explicit value and `none` cannot combine.

`otc` in a route takes a role name as well as an ASN, and the role name is the documented form. All
five names resolve to the neighbour's local ASN, because a static route is only ever egress-marked
and egress procedure 1 always stamps the local ASN, so the name asserts the relationship rather than
selecting a value, and it is rejected when it disagrees with the configured role. The numeric form
stays for inline `exabgp encode`, which builds a neighbour with no role, and for tests asserting
exact bytes.

The session knob is `otc send|disable`, copying what the language already does: `add-path` expresses
a two-direction capability as `disable|receive|send|send/receive` on one token, and OTC is a
two-direction capability. Three earlier names were discarded and each failed differently, which is
worth keeping. `add-otc enable|disable` did not say which direction it governed, and RFC 9234 marks
in both. `otc-egress add|none` imported `egress`, a word this configuration language uses nowhere,
and dressed a two-state choice as an enum. `outgoing-otc enable|disable` used the language's own
`outgoing-ttl`/`incoming-ttl` vocabulary but still hardcoded one direction into a name, so ingress
marking would have arrived as a second knob.

The RFC settles what the value may be. An OTC must be *"preserved unchanged"* once set and the
attribute is four octets, so replacing and appending are not behaviours an operator may choose. What
is left is which directions to mark in, which is what `add-path` encodes.

`add-meta enable|disable`, default enable, covers the reporting side in the same shape. It gates the
`meta` group and nothing else, so a deployment whose helpers ignore the group can drop it without
losing the warning log, the refusals or the detection. It has no per-route override, because the
group is ExaBGP's reporting rather than something a route asks for, and it covers the whole group so
anything later added there needs no second knob.

The leak annotation lives under `meta` because the entry's other keys are what the peer put on the
wire and a leak report is ExaBGP's conclusion about them. `meta.route-leak` is self-sufficient by
design: it describes the issue without the entry around it, the attribute block, the envelope or the
RFC, which is what justifies repeating the peer ASN and the received OTC inside it. The attribute
block is untouched and keeps reporting the OTC whether or not the route was flagged.

It carries one fact per field. `reason` is the fault, `invalid-otc`; `peer-role` and `peer-as` are
who sent it; `expected-otc` and `received-otc` are the check, each key naming the field it concerns.
Two earlier shapes failed the test that an engineer who has never read RFC 9234 must understand the
report on its own. `otc-from-customer` classified what arrived without saying what was wrong.
`invalid-otc-from-customer` fixed that but welded two concepts into one string, so a consumer
grouping by fault had to parse it apart and the reason set grew with every role. An AS is written
`AS65003` rather than a bare `65003` that could as easily have been a timestamp, and nothing in the
object changes type between events. The warning log emits the identical sentence from the same
formatter, so the two cannot drift. This replaces ze's three strings, a deliberate divergence:
parity covers the wire, the role names and the concept, not a diagnostic vocabulary that packed
three facts into one field.

Several decisions are about ExaBGP rather than the RFC, and they are the larger part of the work.
`(2, 11)` is missing from `Notification._str_subcode`. There is no advertised-route state to
withdraw from when no path limit is configured. `AttributeCollection.index()` is derived from a
renderer that skips `INTERNAL`, so a suppression marker needs an identity of its own. `Neighbor.__eq__`
decides what a reload restarts, so only the two settings carried in the OPEN belong in it.
`OutgoingRIB.reset()` is reached by a reload as well as a teardown, so what the peer has been told
needs a lifetime of its own. IPv4 unicast and multicast are indistinguishable on the wire today.
And `local-as auto` means an OTC value cannot be resolved before OPEN. Each is settled above, in the
section it belongs to.

Note for review: `AttributeCollection` skips everything in `INTERNAL` in both renderers, so a route
suppressed with `none` is indistinguishable from an unmarked one in `show adj-rib out` and in JSON,
and a debug log is the only trace. Making it visible means deciding to make `name`, `split`,
`watchdog` and `withdraw` visible too, which is out of scope here.


**Settled scope:** retain ze's role names and leak reasons, but not its configuration token; no
export filter; strict disabled by default; explicit ASNs for role-enabled sessions; no
shared-attribute mutation; route-level refusal with withdrawal transitions; per-announcement leak
annotation; no new malformed diagnostic; no ingress marking. The last decision is an explicit
partial-conformance boundary with helper responsibilities.

**Progress:** the specification is settled; implementation and implementation tests remain
unstarted. **Failures:** no implementation test failures recorded.
**Blockers:** none for ExaBGP implementation; ze parity validation remains separate repository work.

**Specification verification:** every active JSON example parses; all full file references resolve
or name explicitly planned files; the five-row egress table agrees with RFC 9234. The document is
checked by parsing it as CommonMark and confirming the Implementation and Acceptance sections are
headings outside any code block, not by counting fence delimiters: a closing fence carrying prose
on the same line leaves the count even while swallowing half the document. No implementation suite
was run for this documentation-only edit.

**Resume point:** implement Phase 1 with its session/configuration acceptance scenarios, including
the restart/live split of the four role settings. Then Phase 2, with the `index()` identity change
landed and tested before any OTC suppression is parsed. Then the IPv4 multicast move to
MP_REACH/MP_UNREACH, which is a pre-existing defect owed its own commit, tests and issue, and has
to land before the egress work. Then the route-state transitions and semantic reporting in Phase 3,
which is not one change either: the advertised-route state is large enough to land, test and review
on its own before the leak reporting goes on top. Do not promote this plan to completed status on
the strength of documentation checks.

## References

- [RFC 9234 Sections 4-6](https://www.rfc-editor.org/rfc/rfc9234.html#section-4) - Role capability,
  OTC attribute, the ingress and egress procedures, and the preservation requirement
- [RFC 7606 Section 3](https://www.rfc-editor.org/rfc/rfc7606.html#section-3) - treat-as-withdraw,
  and 3(g) for an attribute appearing more than once
- [RFC 4760](https://www.rfc-editor.org/rfc/rfc4760.html) - MP_REACH_NLRI and MP_UNREACH_NLRI
  carry the AFI/SAFI the legacy NLRI field does not
- [Cloudflare BGP Role explanation](https://blog.cloudflare.com/rfc9234-bgp-role-model/)
- ze `internal/component/bgp/plugins/role/` and `yang/ze-role.yang`
- `src/exabgp/configuration/tcpao.py` - neighbour subsection pattern
- `.claude/exabgp/REGISTRY_AND_EXTENSION_PATTERNS.md` - registries
- `.claude/exabgp/WIRE_SEMANTIC_SEPARATION.md` - wire/semantic ownership
- `.claude/exabgp/PACKED_BYTES_FIRST_PATTERN.md` - immutable OTC storage
