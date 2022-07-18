Version explained:
 - major : codebase increase on incompatible changes
 - minor : increase on risk of code breakage during a major release
 - bug   : increase on bug or incremental changes

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
 * reported: the RIB code so withdraw message before any announce are sent
        this does change the RIB behaviour sending withdrawal when it was not previously
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

