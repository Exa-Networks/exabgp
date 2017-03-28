[![License](https://img.shields.io/pypi/l/exabgp.svg)](https://github.com/Exa-Networks/exabgp/blob/master/COPYRIGHT)
[![PyPI](https://img.shields.io/pypi/v/exabgp.svg)](https://pypi.python.org/pypi/exabgp)
[![PyPI Downloads](https://img.shields.io/pypi/dm/exabgp.svg)](https://pypi.python.org/pypi/exabgp)
[![PyPI Status](https://img.shields.io/pypi/status/exabgp.svg)](https://pypi.python.org/pypi/exabgp)
[![PyPI Wheel](https://img.shields.io/pypi/wheel/exabgp.svg)](https://pypi.python.org/pypi/exabgp)
[![Gitter](https://badges.gitter.im/Exa-Networks/exabgp.svg)](https://gitter.im/Exa-Networks/exabgp?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

## Introduction

[ExaBGP](https://github.com/Exa-Networks/exabgp) provides a convenient way to implement [Software Defined Networking](https://en.wikipedia.org/wiki/Software-defined_networking) by transforming [BGP messages](http://thomas.mangin.com/data/pdf/UKNOF%2015%20-%20Mangin%20-%20Naked%20BGP.pdf) into friendly plain [text or JSON](https://github.com/Exa-Networks/exabgp/wiki/Controlling-ExaBGP-:-API-for-received-messages), which can then be easily handled by simple scripts or your BSS/OSS.

It is routinely used to improve service resilience and provide protection against network or service failures. For example, thanks to the `healthcheck` backend included, anycasted DNS service failures can be detected and handled [gracefully](http://blog.iweb-hosting.co.uk/blog/2012/01/27/using-bgp-to-serve-high-availability-dns/). To help you get started, [Vincent Bernat](https://github.com/vincentbernat) put forward a full lab [explaining](https://vincent.bernat.im/en/blog/2013-exabgp-highavailability.html)  how to best use this feature.

Also, [alone](http://perso.nautile.fr/prez/fgabut-flowspec-frnog-final.pdf) or in conjunction with [fastnetmon](https://github.com/pavel-odintsov/fastnetmon), it provides network operators a cost effective DDOS protection solution.

But it is not its only strength, thanks to modern routers' flow balancing, ExaBGP can also be used to save you money on [load balancers](https://bits.shutterstock.com/2014/05/22/stop-buying-load-balancers-and-start-controlling-your-traffic-flow-with-software/). Other uses include keeping an eye on network changes done by [RIPE](https://labs.ripe.net/Members/wouter_miltenburg/researching-next-generation-ris-route-collectors) or by other networks with [GIXLG](https://github.com/dpiekacz/gixlg/wiki/GIXLG-wiki).

## Who is using ExaBGP ?

These organisations have spoken of, or are using/have used ExaBGP:
[AMS-IX](https://ripe64.ripe.net/presentations/49-Follow_Up_AMS-IX_route-server_test_Euro-IX_20th_RIPE64.pdf),
[Alcatel Lucent](https://www.nanog.org/sites/default/files/wed.general.trafficdiversion.serodio.10.pdf),
[BBC](http://www.bbc.co.uk/blogs/internet/entries/8c6c2414-df7a-4ad7-bd2e-dbe481da3633),
[Blablacar](http://blablatech.com/blog/bgp-routing-to-containers),
[Cisco Systems](http://www.ciscoknowledgenetwork.com/files/452_06-11-14-20140610_v3_BGP_Optimizing_the_SDN-v1-0.pdf?),
[CloudFlare](https://www.slideshare.net/TomPaseka/flowspec-apf-2013),
[Dailymotion](https://github.com/pyke369/exabgp-helpers),
[Facebook](https://code.facebook.com/posts/1734309626831603/dhcplb-an-open-source-load-balancer/),
[MaxCDN](https://blog.maxcdn.com/anycast-ip-routing-used-maxcdn/),
[Microsoft](https://www.nanog.org/sites/default/files/wed.general.brainslug.lapukhov.20.pdf),
[OpenDNS](https://blog.opendns.com/2013/01/10/high-availability-with-anycast-routing/),
[PowerDNS](https://blog.powerdns.com/2016/02/23/an-important-update-on-new-powerdns-products/),
[RIPE NCC](https://labs.ripe.net/Members/wouter_miltenburg/Researchpaper.pdf), ...

Therefore so should [`YOU`](https://en.wikipedia.org/wiki/Bandwagon_effect)! :grin:

## Installation

The program is packaged for Debian, Ubuntu, ArchLinux, Gentoo, Mint, FreeBSD, OSX and OmniOS (and probably more).

The latest version is available on [`pypi`](https://pypi.python.org/pypi), the Python Package Index

```sh
> pip install exabgp
> exabgp --help
> python -m exabgp healthcheck --help
 ```

It is also possible to download the latest archive from github

```sh
> curl -L https://github.com/Exa-Networks/exabgp/archive/3.4.17.tar.gz | tar zx
> ./exabgp-3.4.17/sbin/exabgp --help
> ./bin/healthcheck --help
```

If using `git`, for production deployment, please use the "3.4` branch.

```sh
> git clone https://github.com/Exa-Networks/exabgp.git
> git checkout 3.4
> ./bin/healthcheck --help
```

Multiple versions can be used simultaneously without conflict when ExaBGP is ran from extracted archives and/or local git repositories.

The configuration file and API format change from time to time, but every effort is made to make sure backward compatibility is kept. However users are encouraged to read the [release note/CHANGELOG](https://raw.github.com/Exa-Networks/exabgp/master/CHANGELOG) and check their setup after upgrade.

## Support

[![Testing Status](https://img.shields.io/codeship/d6c1ddd0-16a3-0132-5f85-2e35c05e22b1.svg)]()
[![Codacy Rating](https://www.codacy.com/project/badge/1f5fedb98bfd47bcb9ab868ea53ea210)](https://www.codacy.com/public/thomasmangin/exabgp_2)
[![Landscape Code Quality](https://landscape.io/github/Exa-Networks/exabgp/master/landscape.svg)](https://landscape.io/github/Exa-Networks/exabgp/)
[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/Exa-Networks/exabgp/badges/quality-score.png)](https://scrutinizer-ci.com/g/Exa-Networks/exabgp/)
[![Coverage Status](https://img.shields.io/coveralls/Exa-Networks/exabgp.svg)](https://coveralls.io/r/Exa-Networks/exabgp)
[![Throughput Graph](https://graphs.waffle.io/Exa-Networks/exabgp/throughput.svg)](https://waffle.io/Exa-Networks/exabgp/metrics/throughput)

<!--
[![Testing Status](https://travis-ci.org/Exa-Networks/exabgp.svg)](https://travis-ci.org/Exa-Networks/exabgp)

[![Coverage Status](https://img.shields.io/scrutinizer/coverage/g/exa-networks/exabgp.svg)](https://coveralls.io/r/Exa-Networks/exabgp)
-->

ExaBGP is supported through Github's [issue tracker](https://github.com/Exa-Networks/exabgp/issues). So should you encounter any problems, please do not hesitate to [report it](https://github.com/Exa-Networks/exabgp/issues?labels=bug&page=1&state=open) so we can help you.

During "day time" (GMT/BST) feel free to contact us on [`Gitter`](https://gitter.im/Exa-Networks/exabgp); we will try to respond if available. ExaBGP also has a channel on `Freenode` [`#exabgp`](irc://irc.freenode.net:6667/exabgp) but it is not monitored.

The best way to be kept informed about our progress/releases is to follow us on [Google+](https://plus.google.com/u/0/communities/108249711110699351497) and/or [Twitter](https://twitter.com/#!/search/exabgp). You can also use and subscribe to our low volume [mailing list](https://groups.google.com/group/exabgp-users).

## Documentation

The documentation is known to be imperfect. One could even say wanting, limited, insufficient and lacking, therefore any contribution (however small) toward its improvement is truly welcomed.

Other users did however do a fair bit of [`documentation`](https://github.com/Exa-Networks/exabgp/wiki/Related-articles), just not on the [`wiki`](https://github.com/Exa-Networks/exabgp/wiki). :cry:

To understand how ExaBGP should be configured, please have a look into the [`qa/conf`](https://github.com/Exa-Networks/exabgp/tree/master/qa/conf) folder of the repository where a great many examples are available.

`exabgp --help`  is also a treasure trove of information.


## Related Projects

The following projects are related to ExaBGP

**Network Protection**
  - [fastnetmon](https://github.com/pavel-odintsov/fastnetmon) a DDOS protection solution
  - [exabgp edgerouter](https://github.com/infowolfe/exabgp-edgerouter) Spamhaus and Emerging Threats blocking with Ubiquiti EdgeRouters
  - [exabgp-voipbl](https://github.com/GeertHauwaerts/exabgp-voipbl) advertises local or/and voipbl.org blacklist using unicast or flow route.

**Visualisation**
  - [GIXLG](https://code.google.com/p/gixlg/) a looking glass with visualisation
  - [lookify](https://github.com/Shopify/lookify) another looking glass

**Route Announcement**
  - [ERCO](https://erco.xyz/) web interface
  - [ExaBGPmon](https://github.com/thepacketgeek/ExaBGPmon) web interface
  - [ExaBGPmon Vagrant](https://github.com/DDecoene/ExaBGPmon) Fork of ExaBGPmon with a vagrantfile and install script.
  - [BGPAPI](https://github.com/abh/bgpapi) an HTTP API
  - [BGP commander](https://github.com/crazed/bgpcommander) Integration with etcd
  - [exabgp-healthcheck](https://github.com/sysadminblog/exabgp-healthcheck) a perl based healthcheck program

**Installation**
  - [Chef](https://github.com/hw-cookbooks/exabgp) Cookbook
  - [Ansible](https://github.com/sfromm/ansible-exabgp) Playbook

**Interoperability**
  - [IOS2ExaBGP](https://github.com/lochiiconnectivity/ios2exa) converts Cisco IOS IPv4 BGP LOC Rib dumps to ExaBGP's format
  - [MRTparse](https://github.com/YoshiyukiYamauchi/mrtparse) convert MRT format to ExaBGP

**High availability**
  - [ExaZK](https://github.com/shtouff/exazk) a plugin to interface ExaBGP & ZooKeeper
  - [exazk](https://github.com/ton31337/exazk) a ruby solution to interface ExaBGP & ZooKeeper to achieve service HA
  - [exabgp-healthcheck](https://github.com/shthead/exabgp-healthcheck) A third party healthcheck program in Perl

**Performance**
  - [bgperf](https://github.com/osrg/bgperf) Stress test solution for Bird and Quagga (can be used with other implementations)
  - [super smash brogp](https://github.com/spotify/super-smash-brogp) Stress test BGP
  - [kyro](https://github.com/kvogt/kyro) realtime network performance measurement and optimal routes injection - not really ExaBGP related, they have their own stack, but worth mentioning

**FIB**
  - [IOS-XR Solenoid](https://github.com/ios-xr/Solenoid) a FIB for ExaBGP

**Other BGP implementation**
  - [Full list](https://github.com/Exa-Networks/exabgp/wiki/Other-OSS-BGP-implementations) of known open source BGP implementation
  - [Bird](http://bird.network.cz/) very good C based BGP implementation with powerful route filtering language for network administrators
  - [GoBGP](https://github.com/osrg/gobgp) an implementation with various binding for programmers
  - [RYU](https://github.com/osrg/ryu) for SDN fans

**Commercial**
  - [WanGuard](https://www.andrisoft.com/software/wanguard) DDOS protection from Andrisoft with ExaBGP integration

## Features

RFC support includes ASN4, IPv6, MPLS, VPLS, Flow, Graceful Restart, Enhanced Route Refresh, and AIGP among others.
More information can be found [here](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information)

ExaBGP does **not** perform any FIB manipulation. If this is what you need, you may consider another open source BGP daemon such as [BIRD](http://bird.network.cz/) or [Quagga](http://www.quagga.net/).

[RFC compliance](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information) details the latest developments.
