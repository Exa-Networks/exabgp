Version explained:
 - major : codebase increase on incompatible changes
 - minor : increase on risk of code breakage during a major release
 - bug   : increase on bug or incremental changes

Version 6.0.0:
 * Incompatible: the "role { otc send|disable; }" sub-option and the route-level
   "otc none" instruction are removed. RFC 9234 section 5 ends with "The operator
   MUST NOT have the ability to modify the procedures defined in this section",
   and both existed to do exactly that: with the marking off, a route handed to a
   customer carries nothing to say it was ours to give away, which is the leak the
   RFC exists to stop. Outbound marking is now unconditional for IPv4 and IPv6
   unicast, and still applies to no other family. A configuration containing either
   option is refused at parse time with a message naming the RFC, rather than
   accepted and quietly ignored; delete the line.
 * Feature: Parse and generate Only to Customer attributes (RFC 9234) on static,
   API, IP, labelled and VPN routes. Support numeric/dotted ASNs, per-session
   "otc self" and role assertions.
   Add role configuration and OPEN negotiation, unicast outbound marking/refusal,
   withdrawal of refused replacements, and ingress leak annotations and warnings.
   Configuration checks account for automatic marking and export refusal.
   This is partial RFC 9234 support: helpers still own ingress OTC insertion
   and ineligible-route exclusion.
 * Feature: RTC, route target membership (RFC 4684, AFI 1 SAFI 132), issue #1109.
   It was already negotiated by default, since "family { all; }" and a neighbor with no
   family block include every family ExaBGP decodes, but it could neither be listed in a
   family block nor announced. "family { ipv4 rtc; }" now selects it, and membership is
   announced and withdrawn from the announce and static sections and from the API:
   "announce ipv4 rtc origin-as 65001 route-target 65001:100 next-hop self", or
   "rtc default" for the zero-length default route target. The field is origin-as,
   because every RTC UPDATE also carries the ORIGIN attribute and "origin igp" keeps
   its meaning. Received membership reaches the API as JSON, unchanged in shape for a
   full route target. ExaBGP signals membership only: it does not filter the VPN routes
   it sends by the membership its peer advertises, which section 5 allows and
   discourages, and which is recorded as a gap in qa/rfc/rfc4684.toml.
 * Fix: an RTC prefix shorter than 96 bits is read as the prefix it is. RFC 4684
   section 4 carries membership as a prefix of 32 to 96 bits in as many octets as the
   length needs; the decoder took 13 octets for any of them, so the NLRI after a
   short prefix was read from the wrong place, or the UPDATE refused as truncated. A
   short prefix is reported with "prefix-length" and "route-target-prefix" and a null
   "route-target", as half a route target is not one.
 * Incompatible: an extended community "target:" or "origin:" whose global
   administrator is an AS above 65535, or is written with a trailing L, is encoded as
   the Four-Octet AS Specific type of RFC 5668 (0x02). It was encoded as the IPv4
   address type (0x01), so "target:4200000000:100" went out as the address
   250.86.234.0 and etc/exabgp/parse-community.conf's "target:120000L:123" as
   "target:0.1.212.192:123". A peer sees a different community on the wire; a dotted
   address and an AS below 65536 are unchanged.
 * Compatibility: MP_REACH_NLRI is now the first path attribute of the UPDATEs we send,
   and one UPDATE carries one NLRI field only. RFC 7606 section 5.1 asks for both: it
   SHALL be first, and a message MUST NOT hold more than one of a non-empty Withdrawn
   Routes field, a non-empty NLRI field, MP_REACH_NLRI or MP_UNREACH_NLRI. An IPv4
   announce and an IPv4 withdraw used to share one message and are two now, the
   withdrawal first, which keeps the withdraw-before-reannounce ordering the shared
   message gave. Batching is untouched: 200 prefixes are still exactly two messages.
   100 recorded wire captures moved with this, every one of them by the MP attribute
   changing position, and the JSON they are checked against did not change at all.
 * Compatibility: an OPEN carries one Capabilities Optional Parameter holding every
   capability TLV, where each capability used to be wrapped in a parameter of its own,
   so a two-family neighbour with asn4 and route-refresh sent six. RFC 5492 section 4.
   Past 253 octets the RFC 9072 extended form widens the one parameter rather than
   splitting the set, and a session with no capability to send still sends no parameter.
 * Compatibility: the Graceful Restart "Restart State" bit is set on the first OPEN a
   process sends and on no reconnection after a session has been established. RFC 4724
   section 4.2 forbids setting it unless the speaker has restarted, and we claimed a
   restart on every reconnection for the life of the process. The first OPEN still sets
   it, because ExaBGP persists nothing between runs and cannot know which case it is in,
   and asking a peer not to wait for our End-of-RIB is the cheaper way to be wrong. The
   "restart" command and a reload which changed the neighbour still set it.
 * Compatibility: several NOTIFICATION answers a peer could not act on are corrected.
   An unrecognised message type is 1/3 Bad Message Type where it was 1/0 Unspecific
   (RFC 4271 6.1). A Bad Message Length carries the erroneous Length field as its data,
   as 6.1 requires, rather than an English sentence. An unrecognised OPEN Optional
   Parameter is 2/4, which leaves 2/0 for one which is recognised and malformed so a
   peer can tell the two apart (6.2). Every error in MP_REACH_NLRI or MP_UNREACH_NLRI
   is 3/9 Optional Attribute Error rather than 3/0, as RFC 4760 section 7 asks.
 * Fix: the reserved octet of MP_REACH_NLRI is ignored on receipt, as RFC 4760 section 3
   says it should be. We answered a non-zero value with a NOTIFICATION, so one byte a
   later document may give meaning to cost the peer every route it had in every family.
 * Fix: a label stack ends where the NLRI length says it ends rather than on a sentinel
   value. RFC 8277 section 2.4 makes the Compatibility field meaningless and says it MUST
   be ignored on reception; we read those three octets as a label and stopped only on the
   bottom-of-stack bit, 0x800000 or 0x000000, so a conforming peer's withdraw carrying
   any other value was answered with "the label stack of the NLRI never ends" and a
   NOTIFICATION. True for SAFI 4 and SAFI 128. A single label with the bottom-of-stack
   bit clear is accepted too, which section 2.2 requires of a session without the
   Multiple Labels capability, and ExaBGP has never had that capability.
 * Fix: a malformed attribute no longer takes the session down where the RFC prescribes
   something else. Every one of these was a peer, sometimes several hops away, choosing
   when our adjacency dropped.
   - COMMUNITIES, EXTENDED COMMUNITIES and IPv6 Address Specific Extended Communities
     are treat-as-withdraw (RFC 7606 7.8, 7.14 and 7.15). A non-finite FlowSpec
     traffic-rate is therefore answered with a withdrawal rather than a NOTIFICATION.
   - a BGP Prefix-SID which cannot be processed is discarded and the route kept (RFC 8669
     section 6), an empty one included. An SRGB TLV of the wrong size used to leave the
     decoder as a Python exception and was reported to the peer as 1/0, a Message Header
     Error for an attribute fault.
   - a Tunnel Encapsulation attribute holding a sub-TLV which does not end where its TLV
     ends, or arriving without the transitive bit, is treat-as-withdraw (RFC 9012 section
     13). Five bytes ended the session.
   - a NEXT_HOP path attribute of any length but four is treat-as-withdraw (RFC 7606
     7.3). MP_REACH still accepts sixteen, which is where that length belongs.
   - an AS_PATH segment declaring no AS numbers is malformed (7.2), and a malformed
     AS4_PATH discards the attribute rather than withdrawing every prefix in the UPDATE.
   - an MP_REACH_NLRI or MP_UNREACH_NLRI whose flags claim transitive resets the session
     (RFC 7606 5.3 and 3(j)). The routes used to vanish with no withdrawal, no
     NOTIFICATION and one debug line, which is the outcome worse than a reset.
   - an attribute arriving with any of the four unused low bits of the Attribute Flags
     octet set is recognised. RFC 4271 4.3 says they MUST be ignored on receipt and we
     keyed the attribute registry on them, so an ORIGIN with flags 0x41 was not
     recognised and the route was withdrawn.
 * Fix: peer input which read past its own payload. An MVPN Source-AD, Shared-Join or
   Source-Join route compared a Multicast Source Length divided by eight against 4 and
   16, so a length of 129 to 135 passed the IPv6 arm, walked off the payload and raised
   an IndexError, which is not a decoder result and reached the reactor. Two octets. The
   quiet half of the same arithmetic read a length of 33 to 39 as a 32 bit address the
   peer never sent.
 * Fix: a MAC/IP Advertisement route is accepted only with a MAC Address Length of 48,
   which is what RFC 7432 9.2.1 allows. A route declaring 0, 24 or 47 was accepted, the
   six octets were read from their fixed offset anyway, and every API client was handed
   "00:11:22:33:44:55/24", a MAC prefix length nobody had sent.
 * Fix: a FlowSpec NLRI of 240 octets or more is read back. RFC 8955 4.1 puts the length
   in the low twelve bits of two octets and we shifted by sixteen, so a 300 octet NLRI,
   on the wire as f12c, was read as needing 65580 bytes and refused. pack_nlri has always
   written the correct form, so ExaBGP failed this against itself, and the refusal is
   raised where a well formed UPDATE from a conforming peer closed the adjacency instead
   of invalidating one NLRI.
 * Fix: an empty FlowSpec NLRI is treat-as-withdraw. A filter with no component matches
   every packet, so a zero length NLRI from a peer was a rule against all traffic.
 * Compatibility: FlowSpec operators no longer carry their reserved and AND bits into
   what we report. "03 89 06" rendered as "protocol 09tcp", "0C 8D 05" as "fragment
   0Ddont-fragment+first-fragment" and "03 C1 06" as "&=tcp", an AND against a pair which
   does not exist. Numeric and bitmask operators reserve different bits, so each
   component takes its own mask, and AND is cleared on the first operation of a component
   where it has no meaning. The DSCP of "mark" is masked to six bits where the whole
   octet was being reported as "mark 193".
 * Compatibility: a negative FlowSpec traffic-rate is read as zero, which is discard all
   traffic, and refused on encoding. RFC 8955 section 7.1 requires both.
   traffic-rate-packets has always done it and traffic-rate, thirty lines above it, did
   neither: a peer asking for a flow to be discarded entirely was reported as
   "rate-limit:-100", and nothing programming hardware from that reads it as discard.
 * Compatibility: an IPv6 FlowSpec prefix component sizes its pattern from the length
   minus the offset, in both directions, as RFC 8956 3.1 requires. Example 1 of that
   document decoded to an invalid NLRI before, and the packing side wrote a pattern the
   decoder could not read back. Packing now also zeroes the bits below the component's
   own mask, so "fe80::1/1" goes out as "80" where it used to go out as "fe": a prefix
   presenting bits it does not match describes something which does not exist.
 * Compatibility: a FlowSpec component type which repeats, or which arrives before a
   lower type, is treat-as-withdraw, as section 10 asks for through RFC 7606. The wire
   order was discarded and the filter re-rendered in RFC order, so the API reported a
   filter the peer had not sent, and two type 3 components, which section 4.2 ANDs and
   which can therefore never both match, were merged into "protocol [ =tcp =udp ]",
   turning a rule matching nothing into a rule matching both. Several source or
   destination prefixes are still accepted, because vendors send them and ExaBGP writes
   them, so refusing them would stop it reading back what it had written.
 * Compatibility: the fragment bitmask is split per family, so an IPv6 flow no longer
   reports a Don't Fragment bit IPv6 does not have. RFC 8955 figure 4 has DF, IsF, FF and
   LF where RFC 8956 figure 1 has only LF, FF and IsF.
 * Incompatible: a flow route whose source and destination prefixes are not all of one
   address family is refused, in the configuration and on the API, where it used to be
   accepted and changed (issue #1188). "source 10.0.0.0/24; destination 2001:db8::/32;"
   loaded as "source 10.0.0.0/24" alone, so a rule meant for one destination matched
   every destination; two destinations of different families went out as one rule; and
   "announce ipv4 flow" packed an IPv6 prefix into an IPv4 flow NLRI. A configuration
   holding such a rule now fails to load, naming the line and both prefixes, and an API
   command sending one gets an error back instead of a success. Split the rule in two,
   one per family.
 * Incompatible: the same goes for the other components of a flow route which mean
   something else, or nothing, in the other family. "flow-label" in an IPv4 rule is
   type 13, which IPv4 does not have, so the peer treated the whole NLRI as malformed;
   "dscp" in an IPv6 rule matched the 8 bit traffic class with the value meant for the
   6 bit DSCP, and "traffic-class" in an IPv4 rule the reverse; "fragment
   dont-fragment" in an IPv6 rule asked for a bit IPv6 does not define. Each is refused
   now, in whichever order the rule lists its components. "protocol" and "next-header"
   are the same type 3 in both families and are still accepted either way, as is a
   fragment component which does not ask for dont-fragment. A rule whose only family
   specific component is IPv6 (flow-label, traffic-class) is an IPv6 flow route; it was
   packed as an IPv4 one.
 * Compatibility: the IPv6 route-target redirect of RFC 8956 6.1 works (issue #927).
   "redirect [2001:db8::1]:100;" was a syntax error, the community was encoded as type
   0x0002, a plain RFC 5701 route-target rather than 0x000d, in the eight octet extended
   community attribute rather than attribute 25, and the address was installed as the
   route's next-hop. All four are fixed. What an API program receives changes twice: a
   0x000d community, until now an empty JSON "string" and hex in the text encoder, reads
   "redirect [2001:db8::1]:100" in both, and the pre-RFC draft value 0x800b, until now
   "redirect 2001:db8::1:100" in the text encoder, is hex there as it already was in
   JSON. A program matching the old text, where the number could not be told apart from
   the last group of the address, needs the brackets.
 * Fix: BGP-LS no longer refuses input RFC 9552 protects. An unrecognised Protocol-ID
   closed the session, and IANA has assigned 7, 8 and 9 since RFC 7752, so a peer doing
   BGP-LS with Segment Routing was answered with a NOTIFICATION. The gate is removed from
   all four NLRI types rather than widened, because 8.2.2 forbids judging an NLRI on the
   contents of a TLV field at all and a longer whitelist only moves the cliff to the next
   IANA assignment. An unknown Node Descriptor sub-TLV was fatal the same way, so 516 BGP
   Router Identifier closed the session; it is kept whole now and rendered under a name
   carrying its code, so it propagates byte for byte and two unknown codes do not
   collide.
 * Compatibility: a Node Descriptor sub-TLV may appear once, and the sub-TLVs of one
   descriptor must be in ascending order of type code (RFC 9552 5.2.1, 5.1 and 8.2.2). A
   peer repeating one, or sending them out of order, is answered with a NOTIFICATION. The
   check compares type codes and reads no value and no registry, so an unrecognised
   sub-TLV is still kept and propagated. Known deviation: 8.2.2 asks for the NLRI to be
   discarded where we reset the session, and that is recorded as a gap in the ledger.
 * Compatibility: a TLV three RFCs forbid to repeat now gets the answer its own document
   asks for, and they do not agree with each other. A repeated Label-Index or Originator
   SRGB inside a Prefix-SID keeps the first and drops the rest from both the parsed
   attribute and the bytes we re-advertise (RFC 8669 section 6), leaving unknown TLV types
   alone because the same section grants them propagation. A repeated Preference sub-TLV
   in a Tunnel TLV is disregarded in the JSON only, because RFC 9012 section 13 asks in
   the same breath for every sub-TLV to be propagated (RFC 9830 2.4.1 supplies the MUST
   NOT). Two SR Policy TLVs in one attribute are treat-as-withdraw (RFC 9830 2.4). A
   malformed sub-TLV is kept as an unrecognised one, with its bytes, rather than
   inventing a Preference of zero out of a short value.
 * Fix: a tunnel TLV's framing is checked even for a tunnel type we cannot decode. RFC
   9012 section 13 requires the final octet of a TLV to be the final octet of its final
   sub-TLV, and we checked it only where a decoder for the tunnel type existed, which is
   type 15 and nothing else. Nothing is interpreted by the check, which the same section
   also requires.
 * Compatibility: the JSON output gains two keys, and nothing in it is renamed or
   retyped. The question a consumer has is whether its parser still works, and the answer
   is that it does.
   - "link-local-next-hop" appears on an announce whose MP_REACH carried a 32 octet IPv6
     Next Hop, which RFC 2545 section 3 makes a global address followed by a link-local
     one. The second address was decoded and thrown away, so that JSON could not be told
     from the JSON for a plain 16 octet field, which is the one thing a 32 octet next hop
     needs to say. "next-hop" keeps meaning the global address, which is what RFC 2545
     has always said it means. An RFC 8950 pair reports its link-local too.
   - "enlp-name" appears beside the numeric "enlp" of an SR Policy tunnel encapsulation,
     which rendered as 4 where __str__ said "no-push" from a table in the same file.
     "enlp" is still an integer, and a test holds it to that.
 * Fix: a withdrawal is sent even when the announcement's attributes do not fit. One
   budget was computed from the announce attributes and the method returned outright when
   it reached zero, so roughly 4060 octets of path attributes made a 27 octet
   withdraw-only UPDATE disappear: nothing on the wire, no log an operator would connect
   to it, and a stale route left on the peer pointing at a prefix we had stopped
   advertising. With MP families the same return sat ahead of that family's MP_UNREACH
   and ahead of every later family, so one family whose attributes did not fit took the
   withdrawals of all of them. RFC 4271 4.3 makes the Path Attributes field optional and
   RFC 4760 section 3 says an UPDATE carrying MP_UNREACH_NLRI need not carry any other
   attribute, so the announce budget cannot bear on a withdrawal. Only the announcement
   is refused now, and its log no longer says "attributes_too_large" about a withdrawal.
 * Fix: the AS path is reconstructed the way RFC 6793 counts it. An AS4_PATH whose only
   segment was an AS_SET deleted the entire AS_SEQUENCE of the AS_PATH it was merged into,
   because "all but the last len4" was written as a slice which empties the list when len4
   is zero: "(65001 23456)" with an AS4_PATH of "[100000]" came out as "[ 100000 ]" with
   65001 gone, and a peer chooses what it puts in its AS4_PATH. The reconstruction now
   counts AS numbers as RFC 4271 9.1.2.2 counts them, takes whole leading segments from
   the AS_PATH until the count is reached, and coalesces adjacent sequences afterwards.
   Four-octet AS handling is corrected with it: the AS4_PATH we build drops confederation
   segments and is omitted entirely when nothing is left, since an empty one is malformed
   under section 6; a received AS4_PATH no longer folds a confederation segment into what
   we publish; an AGGREGATOR which is not AS_TRANS drops both AS4_ attributes and one
   which is AS_TRANS drops itself, as 4.2.3 requires; and AS4_PATH and AS4_AGGREGATOR
   from a four-octet peer are discarded rather than merged, as 4.1 requires.
 * Fix: each half of a "community <asn>:<value>" is bounded at sixteen bits, and each
   field of a "large-community" at thirty-two. Both halves were checked against the
   ceiling of the "0x..." form instead, so "community 1:65536" was accepted and carried
   out of the value into the AS field: ExaBGP announced 2:0 to every peer and reported
   2:0 back through the API, a community belonging to an AS the operator never named,
   with nothing anywhere saying a number had been changed. "community 65536:1" and
   "large-community 1:2:4294967296" passed the same check and left the parser as a struct
   error, so a typo in a configuration file came out as a traceback with no line named.
   The message now says which half was wrong and what its range is.
 * Fix: a neighbor holding an operational section loads again. It failed with "'tuple'
   object has no attribute 'afi_safi'", on a configuration shipped in this repository.
 * Fix: incoming-ttl and outgoing-ttl each do their one job, in both directions. GTSM
   (RFC 5082) is a minimum TTL accepted from the peer and a TTL we send with, and neither
   knob was applied to both kinds of session. A session we opened got outgoing-ttl and no
   inbound check at all, so every session this side initiated ran without the half which
   rejects a forged packet from off-link, whatever was configured. A session the peer
   opened never got outgoing-ttl, and inherited from the listening socket a sending TTL
   equal to the minimum we accept, where RFC 5082 section 3 has a GTSM sender use 255. An
   accepted connection now takes the sending TTL of the neighbour it matched: outgoing-ttl
   when configured, else 255 when incoming-ttl is, else the kernel default. For the usual
   "incoming-ttl 255" that is what passive sessions already sent, so no working GTSM pair
   changes behaviour on the wire.
 * Fix: the IPv4 inbound TTL check is installed on Linux and FreeBSD. CPython exports
   socket.IP_MINTTL on no platform at all, so the lookup failed everywhere and the check
   had never been installed on any host, while the warning which reported it named the
   platform as the reason. The option number now comes from the kernel headers, 21 on
   Linux and 66 on FreeBSD, which is what the IPv6 side has always done. macOS has no
   equivalent option and says so, rather than quietly setting the outgoing TTL instead
   and leaving an operator who configured ttl-security with a session, no warning and no
   inbound protection. Still open, and recorded: the listening socket is shared per
   address and port, so neighbours behind it with different incoming-ttl values get
   whichever was set last.
 * Fix: "exabgp cli reset" says when it reset nothing. No socket in any search location,
   no fifo, a connection refused because the daemon is not running, and a write which
   failed part way through all printed nothing and exited 0, so a script or a CI job
   checking the status was told the reset had succeeded when no byte had left the process.
   Each of the four names what went wrong on stderr and exits 1. There is still no
   acknowledgement to wait for, so 0 means the command reached the transport.
 * Fix: an unusable "exabgp_api_socketpath" is reported rather than ignored. The search
   fell through to the standard locations, where it can attach to a different daemon's
   socket than the one the operator named.
 * Fix: the API and the CLI report failures they used to swallow. A failed ack, which
   stops the reactor sending "done" and times out every CLI command with nothing saying
   why; a socket file which could not be removed and then outlives the process; a pipe
   whose reader has gone, which returned 0 and had the caller retry the same line for
   ever; the relay thread of "exabgp migrate" giving up and dropping every line after it;
   a history file which could not be read and was then overwritten at exit. The CLI also
   no longer prints its "the daemon has restarted" warning for a truncated pong, says so
   when a shutdown signal could not be delivered rather than reporting the session over
   while it carries on, and no longer caches an empty neighbour list for five minutes
   after one failed query, which left "peer <TAB>" offering no neighbours at all.
 * Fix: a listening socket sets SO_REUSEADDR and IPV6_V6ONLY independently. They were set
   inside one try, so a platform refusing the first skipped the second and the listener
   accepted IPv4-mapped connections matching no configured neighbour.
 * Fix: the configuration schema names a section whose import failed instead of answering
   as though the section did not exist, which sent the operator hunting a typo rather
   than a broken install.
 * Fix: the flow helper reloads the switch policy when it removes a rule. ACL.remove
   deleted the rule file and stopped, where insert and clear both run "cl-acltool -i", so
   a DROP rule stayed programmed after ExaBGP had withdrawn the route and kept dropping
   traffic for a flow ExaBGP had forgotten, until the next announce or a session reset
   happened to reload the policy directory.
 * Fix: the ADD-PATH path identifier is taken off the wire for EVPN, BGP-LS, MVPN, MUP,
   SR-Policy, FlowSpec, VPLS and RTC. Each read its first field from the identifier's
   first byte and left the four octets in the buffer, so every NLRI after the first in the
   same UPDATE was read from the wrong offset (RFC 7911 section 3). No live session
   reaches this, because the capability is offered only for unicast, labelled unicast and
   VPN, but the offline tools build the capability from the configured families
   unfiltered, so "exabgp decode", "exabgp encode" and "configuration validate" did.
   The encoders still write no path identifier for those families, which is why they are
   not offered.
 * Feature: doc/RFC_COMPLIANCE.md, a generated table of what ExaBGP does about every
   normative sentence of the RFCs it implements, published with the code. 24 RFCs and 213
   binding requirements, of which 207 are proven by tests driving real wire bytes,
   positive and negative, and 40 requirements we do not meet, each carrying a reason and
   several of them demonstrated by a test which fails on purpose rather than described in
   a plan file. Every quote in the table is checked against the RFC as published, held in
   qa/rfc/text/, on every run, so a requirement a document does not contain cannot appear
   in it. Generated by "./qa/bin/check_rfc_compliance --markdown" from the ledgers under
   qa/rfc/, which qa/rfc/README.md explains, and the count of untested requirements per
   RFC can only fall.
 * Fix: Compare every message in route validation roundtrips.
 * Fix: Report configured encoding errors without a traceback.
 * Fix: Reject failed and empty route serialization during validation.
 * Fix: Refresh established handler context after neighbor reload.
 * Fix: Fold route replacements into deduplicated refresh snapshots.
 * Fix: Admit outgoing paths only at yielded update boundaries.
 * Fix: Preserve path admissions across live RIB resets.
 * Fix: Budget MP UPDATE fragments independently and withdraw first.
 * Fix: Suppress empty UPDATEs when MP withdrawals are disabled.
 * Fix: Clear native NLRI after emitting its UPDATE.
 * Fix: Preserve IPv4 multicast SAFI in UPDATE messages.
 * Fix: Construct schema IP announcements through NLRI settings.
 * Fix: Preserve ASN identities in offline negotiation.
 * Fix: Preserve four-octet ASNs when building and merging paths.
 * Fix: Recover negotiated ASNs from numeric ASN4 capabilities.
 * Fix: Advertise the effective local ASN in OPEN capabilities.
 * Fix: ADD-PATH is no longer offered for "ipv4 mup" and "ipv6 mup". MUP NLRI carry no
   path identifier on the wire, so a peer which accepted ADD-PATH for MUP was told to
   expect four octets ahead of every MUP NLRI which ExaBGP never sent, and mis-framed
   the rest of the NLRI field. RFC 7911 section 3. MUP returns to the ADD-PATH families
   when its encoder writes a path identifier.
 * Fix: An NLRI queued twice under different attributes and then withdrawn no longer sends
   the replaced announce after the withdraw, which left the peer holding a route ExaBGP had
   just withdrawn. Announcing the same NLRI twice without withdrawing it still sends both,
   as before.
 * Fix: Complete PATHS-LIMIT enforcement for existing ADD-PATH families.
   - Keep peer limits across update batches, replacements, and route refreshes.
   - Retain suppressed candidates and promote them when an advertised path is withdrawn.
   - Group promoted paths the way announced ones are grouped.
   - Log a path the peer's limit keeps off the wire, and log it again when it is promoted.
   - Ignore later duplicate capability tuples even when the first limit is zero.
   - Reject trailing tokens after an ADD-PATH family limit.
   - Ignore, without closing the session, PATHS-LIMIT families past what one capability can carry.
   - Bound the incoming audit at one path per prefix beyond the advertised limit.
   - Keep only the withheld paths for enforcement, so a limit no longer makes
     "adj-rib-out false" replay and withdraw routes for that family alone.
   - Backfill the prefixes a batch of withdrawals touched in the order they were
     withdrawn, rather than in the order their hashes fell.
 * Compatibility: BGP-LS ip-reachability-tlv JSON key changed from "ip" to "prefix"
   - Now includes prefix length in CIDR notation (e.g., "10.134.2.88/30")
 * Compatibility: BGP-LS Adjacency SID JSON key changed from "sr-adj" to "sr-adjs"
   - Now outputs as array of objects instead of duplicate keys
 * Compatibility: BGP-LS Remote Router ID JSON key changed to "remote-router-ids"
   - Now outputs as array of strings instead of duplicate keys
   - IPv4 and IPv6 router IDs properly merged into single array
 * Compatibility: three more BGP-LS members become arrays, completing what 5.0.13
   left to this release. Each repeated its JSON key when the peer sent the TLV more
   than once, and a JSON parser keeps only one of a duplicate pair.
   - "area-id" becomes "area-ids" (RFC 9552 5.3.1.2, a node may be in several areas)
   - "sr-prefix-sid" becomes "sr-prefix-sids" (RFC 9085 2.3.1, one per algorithm)
   - "srv6-locator" becomes "srv6-locators" (RFC 9514 7.1, one per algorithm)
   - Each is an array whether one TLV arrives or several, so the member keeps one type
   - Prefix-SID also emitted four loose members with no object around them
 * Fix: BGP-LS reserved bits are ignored on receipt rather than refused or read.
   RFC 8667 2.2.1, which RFC 9085 defers to: "Other bits: MUST be zero when originated
   and ignored when received".
   - Thirteen flag TLVs refused any octet whose reserved bits were not all zero, and
     LinkState carries DISCARD, so a peer setting one lost its whole BGP-LS attribute.
     That is the forward compatibility failure reserving bits exists to prevent: every
     ExaBGP peer would discard the attribute on the day a later RFC assigns one.
   - The Multi-Topology descriptor (TLV 263) read all sixteen bits of a field which is
     four reserved bits and a 12 bit MT-ID (RFC 9552 5.2.2.1), so a peer setting them
     reported MT-ID 2 as 61442. Identity is the wire bytes, so the same link in the
     same topology also indexed twice; that half is unchanged and is noted in the test.
   - Nothing accepted before renders differently: a reserved bit could only ever have
     been zero to get through.
 * Compatibility: BGP-LS renders a byte string by what RFC 9552 says it carries, and
   the two kinds were being rendered as one.
   - The opaque envelopes (1025, 1097, 1157) carry IGP TLVs this decoder does not look
     into, so they render hex. 1097 and 1157 decoded them as text with replacement
     characters, so anything not valid UTF-8 reached the API as U+FFFD and the value the
     peer sent could not be recovered. 1025 already rendered hex, so the three did not
     agree with each other either.
   - The names (1026 Node Name, 1098 Link Name) are read leniently. RFC 9552 5.3.1.3 and
     5.3.2.7 both say the field "is encoded in 7-bit ASCII" and make RFC 5890 ToASCII the
     sender's job, so a peer putting raw UTF-8 on the wire is not conformant. ExaBGP
     accepted only ASCII and discarded the whole BGP-LS attribute otherwise, which is a
     router losing its router-ids, metrics and SIDs over a descriptive field. Non-ASCII
     names now render as UTF-8, best effort. A conformant name is unaffected, since
     UTF-8 is a superset of ASCII.
 * Compatibility: a BGP-LS attribute TLV which repeats where the RFC does not allow it to
   is rendered as an array under its own key, and the attribute survives. Measured before
   any of this work: 33 of the 38 non-repeating TLVs collided, and the member was silently
   overwritten, so a consumer read one of the two and could not tell. An earlier state of
   this release answered that by discarding the whole attribute, citing RFC 9552 5.3.2.
   That section is a table of Link Attribute TLVs and holds no such rule, 5.3.2.1 says the
   opposite for auxiliary Router-IDs, and the three syntactic checks of 8.2.2 are all
   lengths, so the refusal threw away every TLV a peer had sent to avoid one ambiguous
   JSON key. The ambiguity is real and the answer is a rendering one: a key more than one
   TLV wants is written once, as an array. A TLV arriving alone renders exactly as before,
   and a TLV ExaBGP does not implement is neither refused nor merged away.
 * Compatibility: a relative program path in a "run" command resolves to the first
   candidate which exists, not the last. The search order is /etc/exabgp, then the
   directory holding the configuration file, then $PATH in order, and the scan used
   to continue past a match and keep whichever candidate it found last. A helper
   sitting next to the configuration was therefore shadowed by any same-named
   executable further down $PATH. Anyone relying on that shadowing needs an absolute
   path now.
 * Fix: an IPv4 route-distinguisher written with the wrong number of octets says so.
   '1.2.3:100' and '1.2.3.4.5:100' were already refused, but by RouteDistinguisher
   counting the bytes it was handed, so the operator was told "requires exactly 8
   bytes, got 7" and never which token caused it.
 * Compatibility: Drop support for Python 3.7
 * Feature: Add type annotations to the codebase for better type safety
 * Change: **BREAKING** - The engine now runs on asyncio
   - An async/await event loop replaces the generator-based reactor, there is no way back
   - The full unit and functional test suites pass on the asyncio engine
   - It brings modern event loop integration and easier integration with other asyncio code
 * Feature: Dynamic shell completion generation for Bash, Zsh, and Fish
   - Install with: `exabgp shell install [bash|zsh|fish]`
   - Auto-detects current shell if not specified
   - Complete subcommands, options, and .conf files
 * Feature: Enhanced interactive CLI (exabgpcli, or exabgp cli)
   - Intelligent tab completion for commands and neighbors
   - JSON pretty-printing for responses
   - Command descriptions and help text
   - Dual transport support (Unix sockets + named pipes)
   - '?' key for inline help
   - Graceful signal handling (Ctrl+C)
 * Feature: Health monitoring API commands (ping and status)
 * Fix: Python 3.12+ compatibility improvements
 * Fix: Split concatenated SAFI values in AFI.implemented_safi()
 * Fix: CLI graceful exit via signal-based shutdown
 * Fix: RIB race conditions and iterator bugs in async mode
 * Add: Complete test suite runner (qa/bin/test_everything)

Version 5.0.0:
 * Compatibility: The text encoding of AS-SEQUENCE in the AS-PATH has changed
 * Compatibility: The AS-PATH JSON format has changed
 * Compatibility: The BGP-LS Adjacency SID JSON format has changed
 * Compatibility: The command line format has changed
   whilst trying to keep backward compatibility for most usual commands
 * Feature: drop support for python2, well it is classed as feature, your opinion may vary
 * Fix: support for more than one BGP-LS Adjacency SID per link
   patch: tomjshine
 * reported: the RIB code so withdraw message before any announce are sent
   this does change the RIB behaviour sending withdrawal when it was not previously
 * Fix: parsing of SID in BGP-LS
 * Change: do not include attribute infos in updates if only sending withdrawals
   patch: Denis Krienbühl
 * Fix: Flowspec fragment (issue 1027)
 * Fix: left-over process (issue 1029 - can not be backported as python3 only)
   patch: Vincent Bernat
 * Feature: allow Ipv6 redirect
   patch: rzalamena
 * Fix: AddPath parsing issue (issue 1041)
 * Feature: Added show neighbor json to the CLI
 * Feature: use as-path with a series of [] () [{}]({}) : [] sequence, () set, {} for confed
 * Feature: support for Poetry
   patch: Ahmet Demir
 * Feature: drop support for deprecated Prefix-SID Sub-type (type-2, type-4)
   patch: proelbtn
 * Feature: add support for Prefix-SID Sub-type
   defined in draft-ietf-bess-srv6-services-11 (type-5, type-6)
   patch: proelbtn
 * Compatibility: Generic LSID are now returning lists (otherwise keys are not unique in JSON)
 * Compatibitily: Many TLV could be returned many times and were not given as list
   local-node-descriptors, remote-node-descriptors, interface-address, neighbor-address
 * Compatibility: General use of plural for the following keys
   interface-address -> interface-addresses, neighbor-address -> neighbor-addresses
 * Compatibility: change JSON for sr_capability_flags to be sr-capability-flags and data format
 * Compatibility: change node-descriptors to be list
 * Compatibility: remove L from target in JSON extended communities
 * Fix: issue with extended community generation (still not supporting ASN)
 * Feature: add support for setting BGP path ID for healthcheck.py advertised routes
 * Feature: allow routes advertised by healthcheck.py to be filtered to specific neighbors
 * Compatibility: now using 'daemon' instead of 'syslog' as syslog facility
 * Feature: Support for BGP-MUP SAFI and Extended Community
   defined in draft-mpmz-bess-mup-safi-02
   patch: Takeru Hayasaka
 * Feature: Support for the 'ipv4' and 'ipv6' options in the Announce statement to exabgp-cli
   patch: Takeru Hayasaka
 * Compatibility: remove "alias" not-a-fragment which should be not expressed as !is-fragment
 * Compatibility: the JSON string changed
 * Compatibility: "route refresh" is now "route-refresh"
 * Compatibility: Hostname capability (FQDN) is no longer sent by default - must be explicitly enabled
 * Compatibility: Python 3.13.x is now supported
 * Feature: Complete SRv6 (Segment Routing over IPv6) support for BGP-LS
   - SRv6 Capabilities TLV and SRv6 Locator TLV
   - SRv6 End.X SID TLV and SRv6 LAN End.X SID
   - SRv6 Endpoint Behavior TLV
   - SRv6 SID NLRI
   patch: multiple contributors
 * Feature: RFC 9072 Extended Optional Parameters Length for BGP OPEN
 * Feature: Software version capability for BGP (draft-abraitis-bgp-version-capability)
 * Feature: RFC 6514 MCAST-VPN Route Types 5, 6, 7 support
 * Feature: MUP (Mobile User Plane) improvements
   - Add Source Address to MUP Type 1 ST Route
   - Improved MUP Type2SessionTransformedRoute encoding and parsing
 * Feature: Add 'source-interface' parameter to peer configuration for binding TCP connections
 * Feature: Add '--ip-ifname' argument to healthcheck for setting IP addresses on physical interfaces
 * Feature: Add '--debounce' flag to healthcheck.py
 * Feature: Add 'processes-match' keyword for regex-based process matching in configuration
 * Feature: Add 'neighbor <*>' support in API for bulk route announcements to all neighbors
 * Feature: Refactor 'tcp.once' to 'tcp.attempts' for configurable connection retry limits
 * Feature: Add ACK control API commands: 'disable-ack', 'enable-ack', 'silence-ack' for per-connection ACK management
 * Feature: Add API debug command for troubleshooting
 * Feature: Add '--pipename' CLI option to allow multiple CLI instances with different named pipes
 * Feature: Add '--label-exact-match' support for exact loopback interface label matching in healthcheck
 * Feature: Announce user-defined loopback IPs when '--ip' not configured in healthcheck
 * Feature: Official container support via GitHub Container Registry (ghcr.io/exa-networks/exabgp)
 * Fix: TOCTOU (Time-of-Check-Time-of-Use) race condition in configuration parser
   Added comprehensive validation for process executables (setuid/setgid checks, file type validation)
 * Fix: Multiple bugs in EVPN implementation discovered during test coverage improvements
 * Fix: ADM/ASM unpacking issue (bytes vs string type mismatch) in operational messages
 * Fix: Shutdown communication bug (bytes/string formatting in RFC 8203 handling) in NOTIFICATION
 * Fix: Route-refresh handling (data type mismatch between reactor and API)
 * Fix: IPv6 route-target flowspec redirect encoding per RFC 8956/RFC 5701
 * Fix: Handling of non-encapsulated IPv6 in flowspec
 * Fix: RIB injection with 'neighbor <*>' - only fail if NO peer can accept route
 * Fix: Allow 'withdraw' attribute in API announcements
 * Fix: Accept 'no_export' and 'no_advertise' community names as specified in RFCs
 * Fix: Do not fail on missing nexthop in JSON API responses
 * Fix: Do not JSON-encode ACK messages without explicit option
 * Fix: Version reporting when using zipapp
 * Fix: Parser.py to allow symlinks and correct executable permission checks
 * Fix: Provide warning when closing connection causes issues
 * Fix: Critical logging bugs that could affect error reporting
 * Fix: Various Python 3.8 compatibility issues

Version 4.2.25
 * Fix: regression in 4.2.23 introduced by doctopt changes

Version 4.2.24
 * Fix: remove unused vendored code breaking 4.2.23

Version 4.2.23
 * Fix: update doctopt to master to fix issues with python3.13
 * Fix: issue with code with python 3.13
 * Fix: workaround for deprecated asyncore

Version 4.2.22
 * Fix: route reload for offline neighbors #1126
   patch: Malcolm Dodds
 * Fix: make sure we compare next-hop self and next-hop IP correctly (#1153)
   reported: gitneep
 * Compatibility: remove "not-a-fragment" "!is-fragment" should be used instead
 * Upgrade six to the latest version

Version 4.2.21
 * Fix: regressing on announcing routes from the API #1108

Version 4.2.20
 * Fix: correctly filter routes announced by the API to the right peer #1005
 * Feature: healthcheck neighbor filtering and path-information backport of #1098 and #1099
 * Fix: backport #1101 fix parsing of FlowSpec TCPFlags with NS
 * Fix: backport #1102 fix parsing of Fragment with IPv6 destinations/sources
 * Fix: bug in CLI when failing to read data

Version 4.2.19
 * Feature: force PGP signing of tags
 * Feature: backport ICMP types
 * Fix: backport healthcheck setup_ips requiring a label
   backport by: Steven Honson

Version 4.2.18
 * Feature: add ICMP experimental codes
   reported: enag11
 * Feature: PGP signing releases

Version 4.2.17
 * Feature: add flags ECE, CW and NS to TCP, (not sure if any flowspec implementation uses them) #1053
   reported by: enag11
 * Fix: bug with IGP Metric #1056
   patch by: hkml2000

Version 4.2.16
 * Fix: bacckport of fix for #1051 tcp-flag operators != and &!= return syntax error
   reported by: enag11

Version 4.2.15
 * Fix: #1035 Socket remains in CLOSED state after the interface goes down
   patch: borjam
 * Fix: #1041 backport

Version 4.2.14
 * Fix: issue reading data from the peer
   reported by: isjerryxiao
 * Feature: allow IPv6 redirect
   patch by: rzalamena
 * Fix: fix decoding of path information (inbound vs outbound)
   reported by: isjerryxiao

Version 4.2.13
 * Fix: issue when there is no route to the peer and the connection looked like it established with the API
   reported by: iddq
 * Fix: healthcheck was not ending if/when exabgp did
   reported by: mzealey
 * Fix: issue with poller
   reported by: emilstahl97

Version 4.2.12
 * Fix: issue with flow fragment (issue #1027)

Version 4.2.11
 * Feature: new release code allowing the creation of zipapp

 Version 4.2.10:
 * Fix: cache invalidation on clear command
 patch by: Boris Murashov

Version 4.2.9
 * Fix: healthcheck --sudo, --debug and --no-ack are not exclusive
   reported by: sincerywaing

Version 4.2.8:
 * Fix: restore python -m exabgp

Version 4.2.7:
 * Feature: logging parsing in debug mode will now print the JSON of updates
 * Fix: issue during restart
 * Fix: add ipv6 mpls to add-path
   patch by: adrian62
 * Fix: aggregator parsing when no space are used around ()
   reported by: thomas955
 * Fix: high CPU load to do sleeptime in second and not ms
   reported by: Gary Buhrmaster
 * Change: BGP-LS TE-RIDs are now reported as a list (as Arista reports more than one)
   patch: tomjshine
 * Fix: bad parsing in some case when capability next-hop was used
   reported: alexejli

Version 4.2.6:
 * Fix: prevent the deletion of IP addresses not added by the healthchecker

Version 4.2.5:
 * Fix: Fix loopback detection without label issue
   patch by: Ruben Herold

Version 4.2.4:
 * Change: display next-hop in flow redirect (fixes a bug with route generation too)
   reported by: Cathal Mooney

Version 4.2.3:
 * Fix: issue with sending data toward API
   reported by: jkldgoefgkljefogeg
 * Fix: bug in spin prevention (true vs True)
 * Fix: peer and local ID for show neighbor commands

Version 4.2.2:
 * Fix: issue with new respawn feature breaking the API

Version 4.2.1:
 * Feature: use vendored ip_address module for healthcheck
 * Feature: respawn option under the process (disable re-starting the api program on failure)
 * Feature: support for single announcement for the healthcheck

Version 4.2.0:
 * Feature: Support additional sub-type of BGP-Prefix-SID for SRv6-VPN
   patch by: Hiroki SHIROKURA
 * Fix: issue with pypi release (can not pip install)
   reported by: Thomas Faivre
 * Fix: on 'restart' config could improperly interference with current config which leads to inconsystent state and crash
   patch by: Alexander Petrovsky
 * Feature: "rate-limit" (per neighbor) limit the number of BGP message(s) handled per second
 * Feature: support draft-ietf-idr-flowspec-redirect-02 (previously only simpson was supported)
   patch by: Eli Lindsey
 * Feature: BGP LS IPv6 parsing support
   patch by: Tinus Flagstad
 * Feature: healthcheck handle loopback for non-Linux machines
 * Fix: use local IP for router-id when the peer is auto-deteted (and not the remote IP)
 * Fix: potential python3/python2 bytes vs string issues when generating updates
 * Fix: label is mandatory when using RD, force it, and perform better checks on the configuration
 * Fix: sending route-refresh message via the API was broken
   reported by: Konrad Zemek
 * Fix: make sure exabgpcli does not hang when exabgp.api.ack is set to False
   patch by: basyron
 * Fix: not correctly recording AFI for next-hop self use
 * Fix: removal of ip address by healthcheck
   patch by: wavezhang
 * Fix: healthcheck on ^C during time.sleep, exit gracefully
 * Fix: healthcheck do not fail if the IP address exist when we are trying to add it
 * Fix: healthcheck correctly remove the IP address on going down if it was added
 * Fix: bug when parsing passive keyword alone (was false not true)
 * Fix: was not always terminating with error code 0 when all was good
   patch by: badrabubker
 * CHANGE: large change to the configuration code (should not have any effect but the devil is in the details)
 * CHANGE: using next-hop self could lead to route generated with a IPv6 next-hop in the IPv4 next-hop
   This COULD have been accepted by peers. This version does prevent such generation.
 * CHANGE: resolve symlink when reading the file and not when parsing the configuration
   reported by: juise (with alternative patch - thank you)
 * CHANGE: the reactor was changed from using select to poll (removing the 1024 limit on connections)
 * CHANGE: rewrote setup.py, moving release code into another file

Version 4.1.5:
 * Deleted: could not install via pip install

Version 4.1.4:
 * Deleted: could not install via pip install

Version 4.1.3:
 * Deleted: could not install via pip install

Version 4.1.2
 * Feature: exabgpcli autocomplete
 * Fix: exabgpcli was not correctly removing data on the pipe in case of issues

Version 4.1.1
 * CHANGE: some message are now printed using the log routes option and not parser anymore
 * Fix: bug with functional testing code when using python3
   patch by: Cooper Lees
 * Fix: bug with ExaBGP cli not working
   reported by: jlixfeld (thank you to Cooper Lees for providing time and a test env. to reproduce)

Version 4.1.0
 * CHANGE: when redifining a single parameter option using inheritence the value will be replaced
 * CHANGE: FlowSpec TRUE and FALSE value have been updated to use the latest RFC and are therefore inverted from previous versions
 * CHANGE: an invalid netmask for a network will now cause ExaBGP to fail the parsing of the route (it can stop ExaBGP from starting with bad routes)
 * Feature: support for extended next-hop (RFC 5549)
 * Feature: implemented API for "clear adj-rib out" and "flush adj-rib out"
 * Fix: regression pointed in #873
   patch: Malcolm Dodds
 * Fix: do not crash when trying to be helpful in presenting notification message
   reported by: Adam Jacob Muller
 * Fix: issue while handling ranged neighbors
   patch: Wenxin Wang
 * Fix: accumulating families when using multiple peers
   patch: Martin Topholm (reviewed)
 * Fix: could not reload configuration
   reported by: gbock
 * Feature: better RFC5575bis support, better treat as withdraw
   patch: Christoph Loibl
 * Fix: Fix issue when using peer ASN discovery
   patch: Zac Medico
 * Fix: MD5 encoding
   reported by: Adam Jacob Muller (with an initial idea for a patch)
 * Fix: ignore unknown BGP-LS SID
   reported by: MosesN
 * Fix: badly deciding when to send or not AddPath from parsing the Capability
   reported by: ivan-balan

