##Overview

[ExaBGP](http://github.com/Exa-Networks/exabgp) was not designed to transform a general purpose server into a router, but to allow engineers to control their network.
Think of it as [Software Defined Networking](http://en.wikipedia.org/wiki/Software-defined_networking) using [BGP](http://en.wikipedia.org/wiki/BGP).

This program is packaged for **Debian**, **Ubuntu**, **ArchLinux**, **Gentoo**, **Mint**, **FreeBSD**, **OSX**, **OmniOS**, but some features may only be available on latest version.

[ExaBGP](http://github.com/Exa-Networks/exabgp) does **not** perform any **FIB manipulation**, you will need to write your own LocalRIB and FIB code if this what you need the feature, or simpler, use another open source BGP daemon such as [BIRD](http://bird.network.cz/) or [Quagga](http://www.quagga.net/).

[ExaBGP](http://github.com/Exa-Networks/exabgp) transform [BGP messages](http://thomas.mangin.com/data/pdf/UKNOF%2015%20-%20Mangin%20-%20Naked%20BGP.pdf) into friendly plain [text or JSON](https://github.com/Exa-Networks/exabgp/wiki/Controlling-ExaBGP-:-API-for-received-messages) which can be easily manipulate by scripts.

It allows the creation of tools such as :
 * [advanced looking glasses](https://code.google.com/p/gixlg/wiki/sample_maps) graphically display the routing of prefix
 * [service high availability](http://vincent.bernat.im/en/blog/2013-exabgp-highavailability.html) which automatically isolate dead server / broken services
 * [DDOS mitigation](http://perso.nautile.fr/prez/fgabut-flowspec-frnog-final.pdf)
 * or [anycasted](http://blog.iweb-hosting.co.uk/blog/2012/01/27/using-bgp-to-serve-high-availability-dns/) server

So have a look and take control your network from any unix servers.

```sh
> wget https://github.com/Exa-Networks/exabgp/archive/3.4.2.tar.gz
> tar zxvf 3.4.2.tar.gz
> cd exabgp-3.4.2
> ./sbin/exabgp --help
```

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
[MICROSOFT](http://www.nanog.org/sites/default/files/wed.general.brainslug.lapukhov.20.pdf),
[NEO TELECOM](http://media.frnog.org/FRnOG_18/FRnOG_18-6.pdf),
[RIPE NCC](https://labs.ripe.net/Members/wouter_miltenburg/Researchpaper.pdf)
[VIDEOPLAZA](http://www.videoplaza.com)
as well as researchers.

Please let us know if you use it too  ...

##Features

### Previously on ExaBGP ...

 * receive / send routes
   * **IPv4**/**IPv6** support, [RFC 4760](http://www.ietf.org/rfc/rfc4760.txt) routes with arbitrary next-hops
   * **Flow** support, [RFC 5575](http://tools.ietf.org/html/rfc5575)
   * **MPLS** support, [RFC 4659](http://tools.ietf.org/html/rfc4659) (with vpnv6)
   * **VPLS** support, [RFC 4762](http://tools.ietf.org/html/rfc4762)
   * **ASN4** support, [RFC 4893](http://www.ietf.org/rfc/rfc4893.txt)
   * **Graceful Restart** support, [RFC 4724](http://www.ietf.org/rfc/rfc4724.txt) support
   * **Enhanced Route Refresh**, [RFC 7313](http://tools.ietf.org/html/rfc7313) support
   * **AIGP**, [RFC 7311](http://tools.ietf.org/html/rfc7311) support
   * **And [more](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information)**
 * support for some drafts
   * [draft-raszuk-idr-flow-spec-v6-03](http://tools.ietf.org/html/draft-ietf-idr-flow-spec-v6-03)
   * [draft-ietf-idr-flowspec-redirect-ip-00](http://tools.ietf.org/html/draft-ietf-idr-flowspec-redirect-ip-00)
   * [draft-ietf-idr-add-paths-08](http://tools.ietf.org/html/draft-ietf-idr-add-paths-08)
   * [draft-ietf-idr-bgp-multisession-07](http://tools.ietf.org/html/draft-ietf-idr-bgp-multisession-07) (partial)
   * [draft-scudder-bmp-01](http://tools.ietf.org/html/draft-scudder-bmp-01)
 * runs on any Unix server (with no dependencies).
 * BSD licence, integrate [ExaBGP](http://github.com/Exa-Networks/exabgp) in your own application stack - no strings attached !

##More information

If you are using [ExaBGP](http://github.com/Exa-Networks/exabgp) from source (or git), it **does not need to be installed** on your server ( using "python setup.py install" ).

Multiple versions can be used simulteanously without conflict, using them as follow. To do so, please run [ExaBGP](http://github.com/Exa-Networks/exabgp) from its extracted archive, or your local git repository.

##Curious

Want to know how the code is changing ? Have a question ?

I regularly post on [ExaBGP G+ Group](https://plus.google.com/u/0/communities/108249711110699351497) about ExaBGP current developments and sometimes [blog](http://thomas.mangin.com/categories/networking.html) about BGP.

You can as well follow us on twitter, or subscribe to our low volume [mailing list](http://groups.google.com/group/exabgp-users).
You can as well keep an eye on what we are doing on [twitter](https://twitter.com/#!/search/exabgp).

For more information, please consult any of :

 * the [RFC compliance](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information) pages
 * the [wiki](https://github.com/Exa-Networks/exabgp/wiki) with some some talks and presentations, ...
 * and [the FAQ](https://github.com/Exa-Networks/exabgp/wiki/FAQ)
 * the [changelog](https://raw.github.com/Exa-Networks/exabgp/master/CHANGELOG)

ExaBGP **does not have any dependences on any third party libraries** and will run out of the box on any Unix system with a recent version of python installed.

##Problem ?

No software is perfect, so should you encounter a bug please [report it](https://github.com/Exa-Networks/exabgp/issues?labels=bug&page=1&state=open) so we can help you resolve it.

##Commercial support

ExaBGP is supported through Github [https://github.com/Exa-Networks/exabgp/issues](issue tracker) on a best effort basis. We try to be reactive to any problem raised. However commercial support is available if your organisation requires it.

### New on 3.4 stable ...
 * Important speed improvements
 * **VPLS**, [RFC 4762](http://tools.ietf.org/html/rfc4762) support
 * Better (but sometimes incompatible) JSON format
   * new OPEN message
   * detailled FlowSpec
   * UPDATE sequence number
   * new EOR object
   * possibility to group raw and parsed information in one object
 * new capability configuration section (kept backward compatibility for this release)
 * option to respawn dead helper if they die
 * removal of the option exabgp.tcp.timeout ( not needed anymore )
 * Large rewrite of UPDATE parsing
 * Integrate [Orange BAGPIPE](https://github.com/Orange-OpenSource/bagpipe-bgp) work
   * EVPN NLRI
   * RTC, encapsulation attributes
   * not yet exposed through the configuration file
 * removal of dependency on argparse for python 2.6 ( using docopt )
 * many bug fixes
 * and surely more ....

The configuration file format changes from version to version effort are made to make sure the previous configuration format should still work, however users are encouraged to check their configuration files after upgrade.

##Related Projects

 * [GIXLG](https://code.google.com/p/gixlg/) a looking glass with visualisation using ExaBGP
 * [BGPAPI](https://github.com/abh/bgpapi) an HTTP API to ExaBGP
 * [ExaBGP Chef Cookbook](https://github.com/hw-cookbooks/exabgp) automate ExaBGP's installation
 * [IOS2ExaBGP](https://github.com/lochiiconnectivity/ios2exa) converts Cisco IOS IPv4 BGP LOC Rib dumps to ExaBGP's format
 * [exabgp-voipbl](https://github.com/GeertHauwaerts/exabgp-voipbl) advertises local or/and voipbl.org blacklist using unicast or flow route.

And some self promotion :

 * [ExaProxy](https://github.com/Exa-Networks/exaproxy) A non-caching HTTP proxy able to perform complex header manipulations

