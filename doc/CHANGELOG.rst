Version explained:
 - major : codebase increase on incompatible changes
 - minor : increase on risk of code breakage during a major release
 - bug   : increase on bug or incremental changes

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

