#ExaBGP

Software Defined Networking without marketing

**ExaBGP 3.2 is out !**

##Presentation

Control your network using [BGP](http://www.ietf.org/rfc/rfc4271.txt) from any commodity servers and reap the benefit of software defined networking without [OpenFlow](http://www.wired.com/wiredenterprise/2012/04/going-with-the-flow-google/)

The list of supported RFC is available [here](https://github.com/Thomas-Mangin/exabgp/wiki/RFC-Information)

Receive parsed BGP updates in a friendly form (plain text or JSON) and manipulate them with shell scripts, for example this [looking glass](https://code.google.com/p/gixlg/wiki/sample_maps) use ExaBGP, PHP and MySQL and let you see how a prefix is routed through your network.

This program is packaged for **Debian**, **Ubuntu**, **ArchLinux**, **Mint**, **FreeBSD**, **OSX**, **OmniOS**. Unless you need the latest version, please consider using your distribution's.

If you are using ExaBGP from source (or mercurial), it **does not need to be installed** on your server ( using "python setup.py install" ) and will run from the extracted archive, or your local git repository. It allows to run several versions at the same time without conflict.

These organisations told us they use ExaBGP :
[FACEBOOK](http://velocityconf.com/velocity2013/public/schedule/detail/28410)
[MICROSOFT](http://www.nanog.org/sites/default/files/wed.general.brainslug.lapukhov.20.pdf)
[DAILYMOTION](https://twitter.com/fgabut)
[BBC](http://www.bbc.co.uk/)
[WIKIMEDIA](https://github.com/Thomas-Mangin/exabgp/issues/4)
[AMSIX](https://ripe64.ripe.net/presentations/49-Follow_Up_AMS-IX_route-server_test_Euro-IX_20th_RIPE64.pdf)
[NEO TELECOM](http://media.frnog.org/FRnOG_18/FRnOG_18-6.pdf)
[VIDEOPLATZA](http://www.videoplaza.com/wp-content/uploads/2013/04/Junior-Operations-Engineer-Spring-2013.pdf)
[ALCATEL LUCENT](http://www.nanog.org/sites/default/files/wed.general.trafficdiversion.serodio.10.pdf)
and many researchers
[1](http://typo3.change-project.eu/fileadmin/publications/Deliverables/CHANGE_Deliverable_D4-3_Revised.pdf)
[2](http://www.cs.cornell.edu/projects/quicksilver/public_pdfs/tcpr.pdf)
[3](http://docs.di.fc.ul.pt/jspui/bitstream/10455/6703/1/Disserta%C3%A7%C3%A3o%20de%20mestrado%20do%20S%C3%A9rgio%20Miguel%20Geraldes%20de%20oliveira%20Serrano_Nov-2010.pdf)

Should you need commercial support in order to deploy ExaBGP in your organisation, please feel free to contact Exa Networks using sales AT exa-networks DOT co DOT uk

Want to know how the code is changing ? follow our [Google + Community page](https://plus.google.com/communities/108249711110699351497) where we discuss current developments. You can as well follow us on twitter, or subscribe to our low volume mailing list.

##Features

 * announce BGP route to IPv4 or IPv6 routers with a JunOS looking configuration file
   * **IPv4**/**IPv6** (unicast, multicast, nlri-mpls, *mpls-vpn*) routes with arbitrary next-hops
   * **MPLS** (route-distinguisher), RFC 4659 (vpnv6)
   * **flow routes** (see [RFC 5575](http://tools.ietf.org/html/rfc5575 RFC 5575))
   * support for many recent drafts (multi-session, add-path, IPv6 FlowSpec, ...)
 * generate BGP updates from third party applications
 * parse BGP and generate BGP updates from your own program **simply**
   * track changes in the global routing table or your network.
   * temporary route redirection (adding more specific routes with different next-hop)
   * injection of flow routes to handle DDOS
 * runs on any Unix server (has no dependencies).
 * BSD licence, integrate ExaBGP in your own application stack !

ExaBGP does **not** perform any **FIB manipulation**, however it can call an application which will perform them.
Please look at [BIRD](http://bird.network.cz/) if this is what you are looking for.

##News

### RFC / drafts support

 * complete RFC 5575 by :
   * providing support for **flow-vpn**
    * adding DCSP marking
    * adding traffic-action
 * implemented **draft-raszuk-idr-flow-spec-v6-03**
 * implemented **draft-ietf-idr-flowspec-redirect-ip-00.txt**

### New features include

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

##Usage

 * [Stop DDOS](http://perso.nautile.fr/prez/fgabut-flowspec-frnog-final.pdf) using FlowSpec
 * [AnyCast](http://blog.iweb-hosting.co.uk/blog/2012/01/27/using-bgp-to-serve-high-availability-dns/) servers
 * [High-Availability across Datacenters](http://thomas.mangin.com/data/pdf/RIPE%2063%20-%20Mangin%20-%20BGP.pdf) without any global L2 domains
 * [Looking-Glass](https://code.google.com/p/gixlg/)  using MySQL backend
 * Many more ...

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
> wget https://github.com/Thomas-Mangin/exabgp/archive/3.2.5.tar.gz
> tar zxvf 3.2.5.tar.gz
> cd exabgp-3.2.5
> ./sbin/exabgp --help
```

##Related Projects

 * [GIXLG](https://code.google.com/p/gixlg/) a looking glass with visualisation using ExaBGP
 * [BGPAPI](https://github.com/abh/bgpapi) an HTTP API to ExaBGP
 * [ExaBGP Chef Cookbook](https://github.com/hw-cookbooks/exabgp) automate ExaBGP's installation
 * [IOS2ExaBGP](https://github.com/lochiiconnectivity/ios2exa) converts Cisco IOS IPv4 BGP LOC Rib dumps to ExaBGP's format

And some self promotion :

 * [ExaProxy](http://code.google.com/p/exaproxy) A non-caching HTTP proxy able to perform complex headers and answers manipulations

My [blog](http://thomas.mangin.com/categories/networking.html) may contain some BGP related information, but I tend to post more on [G+](https://plus.google.com/u/0/communities/108249711110699351497) than I blog.
