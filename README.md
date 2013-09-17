#ExaBGP 

##Summary

Unlike [BIRD](http://bird.network.cz/) or [QUAGGA](www.quagga.net/), [ExaBGP](http://github.com/thomas-mangin/exabgp) was not designed to transform a general purpose server into a router, but to allow engineers to control their [BGP](http://tools.ietf.org/html/rfc4271) network easily.
I like to think of it as [Software Defined Networking](http://www.wired.com/wiredenterprise/2012/04/going-with-the-flow-google/) using commodity routers.

[ExaBGP](http://github.com/thomas-mangin/exabgp) transform [BGP](http://www.ietf.org/rfc/rfc4271.txt) messages into friendly plain text or JSON which can be easily manipulate by scripts.

It allows the creation of tools such as :
 * this [advanced looking glass](https://code.google.com/p/gixlg/wiki/sample_maps) graphically display the routing of prefix
 * this [high availability tool](http://vincent.bernat.im/en/blog/2013-exabgp-highavailability.html) which automatically isolate dead server / broken services
 * [DDOS mitigation](http://perso.nautile.fr/prez/fgabut-flowspec-frnog-final.pdf)
 * or for [anycasting](http://blog.iweb-hosting.co.uk/blog/2012/01/27/using-bgp-to-serve-high-availability-dns/)

So have a look and take control your network using [BGP](http://www.ietf.org/rfc/rfc4271.txt) from any commodity servers.

##More information

This program is packaged for **Debian**, **Ubuntu**, **ArchLinux**, **Mint**, **FreeBSD**, **OSX**, **OmniOS**. Unless you need the latest version, please consider using your distribution's.

If you are using [ExaBGP](http://github.com/thomas-mangin/exabgp) from source (or git), it **does not need to be installed** on your server ( using "python setup.py install" ). Simply run [ExaBGP](http://github.com/thomas-mangin/exabgp) from the extracted archive, or your local git repository. It allows to run several versions at the same time without conflict.

The list of supported RFC is available [here](https://github.com/Thomas-Mangin/exabgp/wiki/RFC-Information)

##Who is using it ?

These organisations are speaking of, or using ExaBGP:
[FACEBOOK](http://velocityconf.com/velocity2013/public/schedule/detail/28410),
[MICROSOFT](http://www.nanog.org/sites/default/files/wed.general.brainslug.lapukhov.20.pdf),
[DAILYMOTION](https://twitter.com/fgabut),
[BBC](http://www.bbc.co.uk/),
[WIKIMEDIA](https://github.com/Thomas-Mangin/exabgp/issues/4),
[AMSIX](https://ripe64.ripe.net/presentations/49-Follow_Up_AMS-IX_route-server_test_Euro-IX_20th_RIPE64.pdf),
[NEO TELECOM](http://media.frnog.org/FRnOG_18/FRnOG_18-6.pdf),
[VIDEOPLATZA](http://www.videoplaza.com/wp-content/uploads/2013/04/Junior-Operations-Engineer-Spring-2013.pdf),
[ALCATEL LUCENT](http://www.nanog.org/sites/default/files/wed.general.trafficdiversion.serodio.10.pdf),
[CLOUDFLARE](http://www.slideshare.net/TomPaseka/flowspec-apf-2013)
many researchers
[1](http://typo3.change-project.eu/fileadmin/publications/Deliverables/CHANGE_Deliverable_D4-3_Revised.pdf)
[2](http://www.cs.cornell.edu/projects/quicksilver/public_pdfs/tcpr.pdf)
[3](http://docs.di.fc.ul.pt/jspui/bitstream/10455/6703/1/Disserta%C3%A7%C3%A3o%20de%20mestrado%20do%20S%C3%A9rgio%20Miguel%20Geraldes%20de%20oliveira%20Serrano_Nov-2010.pdf)
and many are simply quietly using it ...

Want to know how the code is changing ? follow our [Google + Community page](https://plus.google.com/communities/108249711110699351497) where we discuss current developments. You can as well follow us on twitter, or subscribe to our low volume mailing list.

##Features

 * runs on any Unix server (has no dependencies).
 * receive / send routes using your own scripts or a JunOS looking configuration file
   * **IPv4**/**IPv6** (unicast, multicast, nlri-mpls, *mpls-vpn*) routes with arbitrary next-hops
   * **MPLS** (route-distinguisher), [RFC 4659](http://tools.ietf.org/html/rfc4659 RFC 4659) (vpnv6)
   * **flow routes** (complete [RFC 5575](http://tools.ietf.org/html/rfc5575 RFC 5575) support)
 * support for many recent drafts
   * **[draft-raszuk-idr-flow-spec-v6-03](http://tools.ietf.org/html/draft-ietf-idr-flow-spec-v6-03)**
   * **[draft-ietf-idr-flowspec-redirect-ip-00](http://tools.ietf.org/html/draft-ietf-idr-flowspec-redirect-ip-00)**
   * **[draft-ietf-idr-add-paths-08](http://tools.ietf.org/html/draft-ietf-idr-add-paths-08)**
   * **[draft-ietf-idr-bgp-multisession-07](http://tools.ietf.org/html/draft-ietf-idr-bgp-multisession-07)**
   * **[draft-keyur-bgp-enhanced-route-refresh-00](http://tools.ietf.org/html/draft-keyur-bgp-enhanced-route-refresh-00)**
   * **[draft-scudder-bmp-01](http://tools.ietf.org/html/draft-scudder-bmp-01)**
 * BSD licence, integrate [ExaBGP](http://github.com/thomas-mangin/exabgp) in your own application stack - no strings attached !

[ExaBGP](http://github.com/thomas-mangin/exabgp) does **not** perform any **FIB manipulation**, you will need to write your own LocalRIB and FIB code if this what you need the feature, or simpler, use another open source BGP daemon.

### New features coming of 3.2 include

 * enhance route refresh support (still in development)
 * Fully RFC 5575 support
 * **An external program to announce a service** ( Thank you Vincent ! )
 * ExaBGP can **accept incoming connections** ( not production ready ! )
 * ExaBGP can decode incoming Flow routes
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

The configuration file format changed slightly from 3.1.x to 3.2.x, effort were made to make sure the previous configuration format would still work, however users are encouraged to check their configuration files.

##More information

Should you need any help or have any question, please post on our [mailing-list](http://groups.google.com/group/exabgp-users) or ask on our [G+ community](https://plus.google.com/u/0/communities/108249711110699351497)

Follow our [**google community**](https://plus.google.com/u/0/communities/108249711110699351497) or [**twitter**](https://twitter.com/#!/search/exabgp).

Please consult any of :

 * the [changelog](https://raw.github.com/Thomas-Mangin/exabgp/master/CHANGELOG)
 * or [RFC compliance](https://github.com/Thomas-Mangin/exabgp/wiki/RFC-Information) pages
 * the [wiki](https://github.com/Thomas-Mangin/exabgp/wiki) with some some talks and presentations, ...
 * and [the FAQ](https://github.com/Thomas-Mangin/exabgp/wiki/FAQ)

Development is done on python 2.7, the code is kept compatible with python 2.4 in ExaBGP 2.x.x and python 2.5 in ExaBGP 3.1.x.
ExaBGP 3.2.x will rely on python 2.7, and we are likely to required python 3.4+ for ExaBGP 4.x.x

This programs does not have any dependences on any third party libraries and will run out of the box on any Unix system.

## Get it
```sh
> wget https://github.com/Thomas-Mangin/exabgp/archive/3.2.10.tar.gz
> tar zxvf 3.2.10.tar.gz
> cd exabgp-3.2.10
> ./sbin/exabgp --help
```

##Commercial support

Should you feel a need for commercial support in order to deploy ExaBGP in your organisation, please feel free to contact Exa Networks using sales AT exa-networks DOT co DOT uk

##Related Projects

 * [GIXLG](https://code.google.com/p/gixlg/) a looking glass with visualisation using ExaBGP
 * [BGPAPI](https://github.com/abh/bgpapi) an HTTP API to ExaBGP
 * [ExaBGP Chef Cookbook](https://github.com/hw-cookbooks/exabgp) automate ExaBGP's installation
 * [IOS2ExaBGP](https://github.com/lochiiconnectivity/ios2exa) converts Cisco IOS IPv4 BGP LOC Rib dumps to ExaBGP's format

And some self promotion :

 * [ExaProxy](http://code.google.com/p/exaproxy) A non-caching HTTP proxy able to perform complex header manipulations

My [blog](http://thomas.mangin.com/categories/networking.html) may contain some BGP related information, but I tend to post more on [G+](https://plus.google.com/u/0/communities/108249711110699351497) than I blog.
