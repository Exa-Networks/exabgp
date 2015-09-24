[![License](https://img.shields.io/pypi/l/exabgp.svg)](https://github.com/Exa-Networks/exabgp/blob/master/COPYRIGHT)

[ExaBGP](http://github.com/Exa-Networks/exabgp) allows engineers to control their network from commodity servers.
Think of it as [Software Defined Networking](http://en.wikipedia.org/wiki/Software-defined_networking) using [BGP](http://en.wikipedia.org/wiki/BGP) by transforming [BGP messages](http://thomas.mangin.com/data/pdf/UKNOF%2015%20-%20Mangin%20-%20Naked%20BGP.pdf) into friendly plain [text or JSON](https://github.com/Exa-Networks/exabgp/wiki/Controlling-ExaBGP-:-API-for-received-messages).

Current documented use cases include [DDOS mitigation](http://perso.nautile.fr/prez/fgabut-flowspec-frnog-final.pdf), [network visualisation](https://code.google.com/p/gixlg/wiki/sample_maps), [service high availability](http://vincent.bernat.im/en/blog/2013-exabgp-highavailability.html),
[anycast](http://blog.iweb-hosting.co.uk/blog/2012/01/27/using-bgp-to-serve-high-availability-dns/).

Find what users have [done with it](https://github.com/Exa-Networks/exabgp/wiki/Related-articles).

 The program is packaged for Debian, Ubuntu, ArchLinux, Gentoo, Mint, FreeBSD, OSX and even OmniOS, but the rate of development mean that some features may only be available on latest version.

 ```sh
> pip install exabgp
> exabgp --help
 ```

```sh
> curl -L https://github.com/Exa-Networks/exabgp/archive/3.4.9.tar.gz | tar zx
> ./exabgp-3.4.9/sbin/exabgp --help
```

##Features

**ASN4** [RFC 4893](http://www.ietf.org/rfc/rfc4893.txt) /
**IPv6** [RFC 4760](http://www.ietf.org/rfc/rfc4760.txt) /
**MPLS** [RFC 4659](http://tools.ietf.org/html/rfc4659) (with vpnv6) /
**VPLS** [RFC 4762](http://tools.ietf.org/html/rfc4762) /
**Flow** [RFC 5575](http://tools.ietf.org/html/rfc5575) /
**Graceful Restart** [RFC 4724](http://www.ietf.org/rfc/rfc4724.txt) /
**Enhanced Route Refresh** [RFC 7313](http://tools.ietf.org/html/rfc7313) /
**AIGP**[RFC 7311](http://tools.ietf.org/html/rfc7311) /
and **[more](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information)**.

raszuk-idr-**[flow-spec-v6-03](http://tools.ietf.org/html/draft-ietf-idr-flow-spec-v6-03)** / draft-ietf-idr-**[flowspec-redirect-ip-00](http://tools.ietf.org/html/draft-ietf-idr-flowspec-redirect-ip-00)** /
draft-ietf-idr-**[add-paths-08](http://tools.ietf.org/html/draft-ietf-idr-add-paths-08)** / draft-ietf-idr-**[bgp-multisession-07](http://tools.ietf.org/html/draft-ietf-idr-bgp-multisession-07)** / draft-scudder-**[bmp-01](http://tools.ietf.org/html/draft-scudder-bmp-01)**

[ExaBGP](http://github.com/Exa-Networks/exabgp) does **not** perform any **FIB** manipulation. If this what you need, use another open source BGP daemon such as [BIRD](http://bird.network.cz/) or [Quagga](http://www.quagga.net/).

##Support

[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/Exa-Networks/exabgp/badges/quality-score.png)](https://scrutinizer-ci.com/g/Exa-Networks/exabgp/)
[![Landscape Code Quality](https://landscape.io/github/Exa-Networks/exabgp/master/landscape.svg)](https://landscape.io/github/Exa-Networks/exabgp/)
[![Coverage Status](https://img.shields.io/scrutinizer/coverage/g/exa-networks/exabgp.svg)](https://coveralls.io/r/Exa-Networks/exabgp)
[![Codacy Badge](https://www.codacy.com/project/badge/1f5fedb98bfd47bcb9ab868ea53ea210)](https://www.codacy.com/public/thomasmangin/exabgp_2)
[![Testing Status](https://travis-ci.org/Exa-Networks/exabgp.svg)](https://travis-ci.org/Exa-Networks/exabgp)

<!-- [![Coverage Status](https://img.shields.io/coveralls/Exa-Networks/exabgp.svg)](https://coveralls.io/r/Exa-Networks/exabgp) -->

The way way to keep informed is to follow us on [Google+](https://plus.google.com/u/0/communities/108249711110699351497), [twitter](https://twitter.com/#!/search/exabgp) and / or subscribe to our low volume [mailing list](http://groups.google.com/group/exabgp-users).
For more information, please consult any of the [wiki pages](https://github.com/Exa-Networks/exabgp/wiki), in particular the [RFC compliance](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information), [FAQ](https://github.com/Exa-Networks/exabgp/wiki/FAQ)
 and [changelog](https://raw.github.com/Exa-Networks/exabgp/master/CHANGELOG).

ExaBGP is supported through Github [issue tracker](https://github.com/Exa-Networks/exabgp/issues) on a best effort basis. So should you encounter a bug please [report it](https://github.com/Exa-Networks/exabgp/issues?labels=bug&page=1&state=open) so we can help you resolve it.

During "day time" ( GMT ) feel free to ask us questions using instant messaging via [Gitter](https://gitter.im/Exa-Networks/exabgp) or [#exabgp](irc://irc.freenode.net:6667/exabgp) on Freenode.

Multiple versions can be used simulteanously without conflict when [ExaBGP](http://github.com/Exa-Networks/exabgp) is ran from extracted archives and / or local git repositories.

The configuration file format changes from version to version, but effort are made to make sure backward compatibility is kept, however users are encouraged to read the release note and check their setup after upgrade.

##Commercial Support

You do not need commercial support to get help ! We try to be reactive to any problem raised, and hopefully are not too bad at it.

That said, some organisation are  unable to deploy an application without commercial support, therefore it is available if your organisation requires it but is by no way required.

##Who is using it ?

These organisations have spoken of, or are using/have used [ExaBGP](http://github.com/Exa-Networks/exabgp):

[ALCATEL LUCENT](http://www.nanog.org/sites/default/files/wed.general.trafficdiversion.serodio.10.pdf),
[AMSIX](https://ripe64.ripe.net/presentations/49-Follow_Up_AMS-IX_route-server_test_Euro-IX_20th_RIPE64.pdf),
[BBC](http://www.bbc.co.uk/),
[CLOUDFLARE](http://www.slideshare.net/TomPaseka/flowspec-apf-2013),
[DAILYMOTION](https://twitter.com/fgabut),
[FACEBOOK](http://velocityconf.com/velocity2013/public/schedule/detail/28410),
[INTERNAP](http://www.internap.com/),
[OPENDNS](http://www.opendns.com/),
[MAXCDN](http://blog.maxcdn.com/anycast-ip-routing-used-maxcdn/),
[MICROSOFT](http://www.nanog.org/sites/default/files/wed.general.brainslug.lapukhov.20.pdf),
[NEO TELECOM](http://media.frnog.org/FRnOG_18/FRnOG_18-6.pdf),
[POWERDNS](https://www.powerdns.com/),
[RIPE NCC](https://labs.ripe.net/Members/wouter_miltenburg/Researchpaper.pdf),
[VIDEOPLAZA](http://www.videoplaza.com),
and many more ...

Please let us know if you use it.

##Related Projects

 * [GIXLG](https://code.google.com/p/gixlg/) a looking glass with visualisation using ExaBGP
 * [BGPAPI](https://github.com/abh/bgpapi) an HTTP API to ExaBGP
 * [ExaBGP Chef Cookbook](https://github.com/hw-cookbooks/exabgp) automate ExaBGP's installation
 * [IOS2ExaBGP](https://github.com/lochiiconnectivity/ios2exa) converts Cisco IOS IPv4 BGP LOC Rib dumps to ExaBGP's format
 * [exabgp-voipbl](https://github.com/GeertHauwaerts/exabgp-voipbl) advertises local or/and voipbl.org blacklist using unicast or flow route.

## Self Promotion

Exa Networks has also developed a high-performance and very flexible filtering [HTTP proxy](https://github.com/Exa-Networks/exaproxy) (allowing cookie manipulation and other goodies).
