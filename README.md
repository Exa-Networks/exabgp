##Summary

Unlike [BIRD](http://bird.network.cz/) or [Quagga](http://www.quagga.net/), [ExaBGP](http://github.com/Exa-Networks/exabgp) was not designed to transform a general purpose server into a router, but to allow engineers to control their [BGP](http://tools.ietf.org/html/rfc4271) network easily.
Think of it as [Software Defined Networking](http://www.wired.com/wiredenterprise/2012/04/going-with-the-flow-google/) for people with "commodity" routers.

[ExaBGP](http://github.com/Exa-Networks/exabgp) transform [BGP](http://www.ietf.org/rfc/rfc4271.txt) messages into friendly plain text or JSON which can be easily manipulate by scripts.

It allows the creation of tools such as :
 * this [advanced looking glass](https://code.google.com/p/gixlg/wiki/sample_maps) graphically display the routing of prefix
 * this [high availability tool](http://vincent.bernat.im/en/blog/2013-exabgp-highavailability.html) which automatically isolate dead server / broken services
 * [DDOS mitigation](http://perso.nautile.fr/prez/fgabut-flowspec-frnog-final.pdf)
 * an [anycasted](http://blog.iweb-hosting.co.uk/blog/2012/01/27/using-bgp-to-serve-high-availability-dns/) server

So have a look and take control your network from any commodity servers.

##More information

This program is packaged for **Debian**, **Ubuntu**, **ArchLinux**, **Gentoo**, **Mint**, **FreeBSD**, **OSX**, **OmniOS**. Unless you need the latest version, please consider using your distribution's.

If you are using [ExaBGP](http://github.com/Exa-Networks/exabgp) from source (or git), it **does not need to be installed** on your server ( using "python setup.py install" ). Simply run [ExaBGP](http://github.com/Exa-Networks/exabgp) from the extracted archive, or your local git repository. It allows to run several versions at the same time without conflict.

```sh
> wget https://github.com/Exa-Networks/exabgp/archive/3.2.18.tar.gz
> tar zxvf 3.2.18.tar.gz
> cd exabgp-3.2.18
> ./sbin/exabgp --help
```

##Who is using it ?

These organisations are speaking of, or using, [ExaBGP](http://github.com/Exa-Networks/exabgp):
[FACEBOOK](http://velocityconf.com/velocity2013/public/schedule/detail/28410),
[MICROSOFT](http://www.nanog.org/sites/default/files/wed.general.brainslug.lapukhov.20.pdf),
[DAILYMOTION](https://twitter.com/fgabut),
[BBC](http://www.bbc.co.uk/),
[AMSIX](https://ripe64.ripe.net/presentations/49-Follow_Up_AMS-IX_route-server_test_Euro-IX_20th_RIPE64.pdf),
[NEO TELECOM](http://media.frnog.org/FRnOG_18/FRnOG_18-6.pdf),
[VIDEOPLAZA](http://www.videoplaza.com),
[ALCATEL LUCENT](http://www.nanog.org/sites/default/files/wed.general.trafficdiversion.serodio.10.pdf),
[CLOUDFLARE](http://www.slideshare.net/TomPaseka/flowspec-apf-2013),
[INTERNAP](http://www.internap.com/),
researchers
[[1]](http://typo3.change-project.eu/fileadmin/publications/Deliverables/CHANGE_Deliverable_D4-3_Revised.pdf)
[[2]](http://www.cs.cornell.edu/projects/quicksilver/public_pdfs/tcpr.pdf)
[[3]](http://docs.di.fc.ul.pt/jspui/bitstream/10455/6703/1/Disserta%C3%A7%C3%A3o%20de%20mestrado%20do%20S%C3%A9rgio%20Miguel%20Geraldes%20de%20oliveira%20Serrano_Nov-2010.pdf),
and please let us know if you use it too and can list you here ...

##BUG

No software is perfect, so should you encounter a bug please [report it](https://github.com/Exa-Networks/exabgp/issues?labels=bug&page=1&state=open) so we can resolve it.

##Curious

Want to know how the code is changing ? Have a question ?

follow our [Google + Community page](https://plus.google.com/communities/108249711110699351497) where we discuss current developments. You can as well follow us on twitter, or subscribe to our low volume [mailing list](http://groups.google.com/group/exabgp-users).
You can as well keep an eye on what we are doing on [twitter](https://twitter.com/#!/search/exabgp).

Please consult any of :

 * the [changelog](https://raw.github.com/Exa-Networks/exabgp/master/CHANGELOG)
 * or [RFC compliance](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information) pages
 * the [wiki](https://github.com/Exa-Networks/exabgp/wiki) with some some talks and presentations, ...
 * and [the FAQ](https://github.com/Exa-Networks/exabgp/wiki/FAQ)

This programs **does not have any dependences on any third party libraries** and will run out of the box on any Unix system with a recent version of python installed.

Development is done on python 2.7, the code is kept compatible with python 2.4 in ExaBGP 2.x.x and python 2.5 in ExaBGP 3.1.x.
ExaBGP 3.2.x does rely on python 2.7 (but installing argparse with 2.6 works too), and we are likely to required python 3.4+ for ExaBGP 4.x.x

```sh
> »› python --version
Python 2.6.7
> pip install argparse
```


##Features

### known ...

 * runs on any Unix server (has no dependencies).
 * receive / send routes using your own scripts or a JunOS looking configuration file
   * **IPv4**/**IPv6** (unicast, multicast, nlri-mpls, *mpls-vpn*) routes with arbitrary next-hops
   * **MPLS** (route-distinguisher), [RFC 4659](http://tools.ietf.org/html/rfc4659 RFC 4659) (vpnv6)
   * **flow routes** (complete [RFC 5575](http://tools.ietf.org/html/rfc5575 RFC 5575) support)
 * support for many recent drafts
   * [draft-raszuk-idr-flow-spec-v6-03](http://tools.ietf.org/html/draft-ietf-idr-flow-spec-v6-03)
   * [draft-ietf-idr-flowspec-redirect-ip-00](http://tools.ietf.org/html/draft-ietf-idr-flowspec-redirect-ip-00)
   * [draft-ietf-idr-add-paths-08](http://tools.ietf.org/html/draft-ietf-idr-add-paths-08)
   * [draft-ietf-idr-bgp-multisession-07](http://tools.ietf.org/html/draft-ietf-idr-bgp-multisession-07)
   * [draft-ietf-idr-bgp-enhanced-route-refresh-04](http://tools.ietf.org/html/draft-ietf-idr-bgp-enhanced-route-refresh-04)
   * [draft-scudder-bmp-01](http://tools.ietf.org/html/draft-scudder-bmp-01)
   * [draft-ietf-idr-aigp-10.txt](http://tools.ietf.org/html/draft-ietf-idr-aigp-10)
 * BSD licence, integrate [ExaBGP](http://github.com/Exa-Networks/exabgp) in your own application stack - no strings attached !

[ExaBGP](http://github.com/Exa-Networks/exabgp) does **not** perform any **FIB manipulation**, you will need to write your own LocalRIB and FIB code if this what you need the feature, or simpler, use another open source BGP daemon.

### new on 3.2 stable ...

 * enhance route refresh support (still in development)
 * Ful RFC 5575 support, can decode incoming Flow routes
 * **An external program to announce a service** ( Thank you Vincent ! )
 * **accept incoming connections**
 * using "next-hop self" is supported via the API
 * new update code generation can *group multiple NLRI*, from different families, in one update packet
 * **NOTIFICATION** message generation using the API
 * API message control (limit diffusion to a subset of peers)
 * better --decode option to find out what a hex dump of a route mean
 * new internals ... many, including
    * large rewrite of non-optimal code
    * new non-blocking reactor
    * new Adj-RIB-In and Adj-RIB-Out with scalable watchdog feature
 * many small fixes, see the full CHANGELOG
 * and more ....

The list of supported RFC is available [here](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information)

The configuration file format changed slightly from 3.1.x to 3.2.x, effort were made to make sure the previous configuration format would still work, however users are encouraged to check their configuration files.

##Commercial support

Should you feel a need for commercial support in order to deploy ExaBGP in your organisation, please feel free to contact Exa Networks using sales AT exa-networks DOT co DOT uk

##Related Projects

 * [GIXLG](https://code.google.com/p/gixlg/) a looking glass with visualisation using ExaBGP
 * [BGPAPI](https://github.com/abh/bgpapi) an HTTP API to ExaBGP
 * [ExaBGP Chef Cookbook](https://github.com/hw-cookbooks/exabgp) automate ExaBGP's installation
 * [IOS2ExaBGP](https://github.com/lochiiconnectivity/ios2exa) converts Cisco IOS IPv4 BGP LOC Rib dumps to ExaBGP's format

And some self promotion :

 * [ExaProxy](http://code.google.com/p/exaproxy) A non-caching HTTP proxy able to perform complex header manipulations

My [blog](http://thomas.mangin.com/categories/networking.html) may contain some BGP related information, but I tend to post more on [G+](https://plus.google.com/u/0/communities/108249711110699351497) about ExaBGP than I blog.
