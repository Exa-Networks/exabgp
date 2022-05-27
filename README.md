[![License](https://img.shields.io/pypi/l/exabgp.svg)](https://github.com/Exa-Networks/exabgp/blob/master/LICENCE.txt)
[![CI](https://github.com/Exa-Networks/exabgp/actions/workflows/ci.yaml/badge.svg)](https://github.com/Exa-Networks/exabgp/actions/workflows/ci.yaml)
[![PyPI Status](https://img.shields.io/pypi/status/exabgp.svg)](https://pypi.python.org/pypi/exabgp)
[![PyPI](https://img.shields.io/pypi/v/exabgp.svg)](https://pypi.python.org/pypi/exabgp)
[![PyPI Wheel](https://img.shields.io/pypi/wheel/exabgp.svg)](https://pypi.python.org/pypi/exabgp)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Introduction

[ExaBGP](https://github.com/Exa-Networks/exabgp) provides a convenient way to implement [Software Defined Networking](https://en.wikipedia.org/wiki/Software-defined_networking) by transforming [BGP messages](http://thomas.mangin.com/data/pdf/UKNOF%2015%20-%20Mangin%20-%20Naked%20BGP.pdf) into friendly plain [text or JSON](https://github.com/Exa-Networks/exabgp/wiki/Controlling-ExaBGP-:-API-for-received-messages), which can then be easily handled by simple scripts or your BSS/OSS.

It is routinely used to improve service resilience and provide protection against network or service failures. For example, thanks to the `healthcheck` backend included, anycasted DNS service failures can be detected and handled [gracefully](http://blog.iweb-hosting.co.uk/blog/2012/01/27/using-bgp-to-serve-high-availability-dns/). To help you get started, [Vincent Bernat](https://github.com/vincentbernat) put forward a full lab [explaining](https://vincent.bernat.ch/en/blog/2013-exabgp-highavailability)  how to best use this feature.

Also, [alone](http://perso.nautile.fr/prez/fgabut-flowspec-frnog-final.pdf) or in conjunction with [FastNetMon](https://github.com/pavel-odintsov/fastnetmon) or [WanGuard](https://www.andrisoft.com/software/wanguard), it provides network operators a cost effective DDOS protection solution.

Thanks to modern routers' flow balancing, ExaBGP can also be used to save you money on [load balancers](https://tech.shutterstock.com/2014/05/22/stop-buying-load-balancers), some good information can be found [here](https://vincent.bernat.ch/en/blog/2018-multi-tier-loadbalancer) too.

Other uses include keeping an eye on network changes done as was done by [RIPE](https://labs.ripe.net/Members/wouter_miltenburg/researching-next-generation-ris-route-collectors) or by other networks with [GIXLG](https://github.com/dpiekacz/gixlg/wiki/GIXLG-wiki).

## Installation

ExaBGP 3.4 and previous versions are python 2 applications. ExaBGP 4.0 had support for both Python 2 and 3. current version of ExaBGP (4.2 and master) are targeting python 3 only (3.7+).

### OS packages

The program is packaged for [Debian](https://packages.debian.org/search?keywords=exabgp), [Ubuntu](https://packages.ubuntu.com/search?keywords=exabgp), [ArchLinux](https://aur.archlinux.org/packages/exabgp), [Gentoo](https://packages.gentoo.org/packages/net-misc/exabgp), [FreeBSD](https://www.freshports.org/net/exabgp/), [OSX](https://ports.macports.org/port/exabgp/) and probably more.

Many OS have quite ancient releases (sometimes over a year old). On the plus side, the package will most likely come with systemd pre-setup and therefore may be easier to use.

As it is often the recommended way to get software onto server, feel free to use them but should you encounter any issues we would then recommend a pip installation, as it will install the latest stable version.

### pip releases

The latest version is available on [`pypi`](https://pypi.python.org/pypi), the Python Package Index

```sh
> pip install exabgp

> exabgp --version
> exabgp --help

> exabgp --run healthcheck --help
> python3 -m exabgp healthcheck --help
 ```

### github releases

It is also possible to download releases from github

```sh
> curl -L https://github.com/Exa-Networks/exabgp/archive/4.2.18.tar.gz | tar zx

> cd exabgp-4.2.18
> ./sbin/exabgp --version
> ./sbin/exabgp --help

> ./sbin/exabgp --run healthcheck --help
> env PYTHONPATH=./src python3 -m exabgp healthcheck --help
> ./bin/healthcheck --help
```

### git master

In case of issues, we are asking user to run the lastest code directly for a local `git clone`.

```sh
> git clone https://github.com/Exa-Networks/exabgp exabgp-git

> cd exabgp-git
> ./sbin/exabgp --version
> ./sbin/exabgp --help

> ./sbin/exabgp --run healthcheck --help
> env PYTHONPATH=./src python3 -m exabgp healthcheck --help
> ./bin/healthcheck --help
```

Obviously, it is then possible to change git to use any release (here 4.2.18)

```sh
> git checkout 4.2.18
> ./sbin/exabgp --version
```

### zipapp

From the source folder, it is possible to create a self-contained executable which only requires an installed python3 interpreter

```sh
> cd exabgp-git
> release binary /usr/local/sbin/exabgp
> /usr/local/sbin/exabgp --version
```

which is an helper function and create a python3 zipapp

```sh
> cd exabgp-git
> python3 -m zipapp -o /usr/local/sbin/exabgp -m exabgp.application:main  -p "/usr/bin/env python3" src
> /usr/local/sbin/exabgp --version
```

### docker

Alternatively, you can use the repository to create a docker image

```sh
> cd exabgp-git
> docker build -t exabgp ./
> docker run -p 179:1790 --mount type=bind,source=`pwd`/etc/exabgp,target=/etc/exabgp -it exabgp -v /etc/exabgp/parse-simple-v4.conf
```

It is possible add your configuration file within the docker image or use the container like you would use the exabgp binary, or use the `Docker.remote` file to build it using pip (does not require any other file)

### pick and choose

Multiple versions can be used simultaneously without conflict when ExaBGP is ran from extracted archives, docker, and/or local git repositories.

## Upgrade

ExaBGP is self-contained and easy to upgrade/downgrade by:

* replacing the downloaded release folder, for releases download
* running `git pull` in the repository folder, for installation using git master
* running `pip install -U exabgp`, for pip installations
* running `apt update; apt upgrade exabgp` for Debian/Ubuntu

*If you are migrating your application from ExaBGP 3.4 to 4.x please read this [wiki](https://github.com/Exa-Networks/exabgp/wiki/Migration-from-3.4-to-4.0) entry*.

The configuration file and API format may change from time to time, but every effort is made to make sure backward compatibility is kept. However users are encouraged to read the [release note/CHANGELOG](https://raw.github.com/Exa-Networks/exabgp/master/CHANGELOG) and check their setup after upgrade.

## Support

ExaBGP is supported through Github's [issue tracker](https://github.com/Exa-Networks/exabgp/issues). So should you encounter any problems, please do not hesitate to [report it](https://github.com/Exa-Networks/exabgp/issues?labels=bug&page=1&state=open) so we can help you.

During "day time" (GMT/BST) feel free to contact us on [`Slack`](https://join.slack.com/t/exabgp/shared_invite/enQtNTM3MTU5NTg5NTcyLTMwNmZlMGMyNTQyNWY3Y2RjYmQxODgyYzY2MGFkZmYwODMxNDZkZjc4YmMyM2QzNzA1YWM0MmZjODhlYThjNTQ). We will try to respond if available.

The best way to be kept informed about our progress/releases is to follow us on [Twitter](https://twitter.com/#!/search/exabgp).

In case of bugs, we will ask you to help us fix the issue using the master branch. We will then try to backport any fixes to the 4.2 stable branch.

Please make sure to remove any non `git master` installations if you are trying the latest master release, to prevent to run the wrong code by accident, it happens more than you think, and verify the binary by running `exabgp version`.

We will nearly systematically ask for the `FULL` output exabgp with the option `-d`.

## Development

The master branch is now what will be ExaBGP 5.0.x. The program command line arguments has already been changed and are no longer fully backward compatible with version 3 and 4.

ExaBGP is nearly as old as Python3. Lots has changed in 11 years. Support for python2 has already been dropped.

master has already seen a big rewrite but more is still to come. The application need work to take advantage of Python3 'new' async-io (as we run an home-made async core engine) and new features are being investigated (such as configuration edition via a interactive CLI).

For these reasons, we recommend the use of the 4.2 releases in production, but running master is sometimes required for the latest and greatest features.

## Who is using ExaBGP ?

Some users have documented their use cases, such as [DailyMotion](https://medium.com/dailymotion/how-we-built-our-hybrid-kubernetes-platform-d121ea9cb0bc) or [Facebook](https://code.fb.com/data-infrastructure/dhcplb-server/).

These organisations have spoken of, or are using/have used ExaBGP:
[AMS-IX](https://ripe64.ripe.net/presentations/49-Follow_Up_AMS-IX_route-server_test_Euro-IX_20th_RIPE64.pdf),
[Alcatel Lucent](https://www.nanog.org/sites/default/files/wed.general.trafficdiversion.serodio.10.pdf),
[BBC](https://www.bbc.co.uk/blogs/internet/entries/8c6c2414-df7a-4ad7-bd2e-dbe481da3633),
[Blablacar](http://previous.blablatech.com/blog/bgp-routing-to-containers),
[Cisco Systems](https://www.cisco.com/c/dam/en/us/td/docs/wireless/asr_5000/21-24/OpenSource/StarOS-2124-1623227047.pdf),
[Cloudflare](https://www.slideshare.net/TomPaseka/flowspec-apf-2013),
[Dailymotion](https://github.com/pyke369/exabgp-helpers),
[Facebook](https://code.facebook.com/posts/1734.0.826831603/dhcplb-an-open-source-load-balancer/),
[Microsoft](https://www.nanog.org/sites/default/files/wed.general.brainslug.lapukhov.20.pdf),
[OpenDNS](https://blog.opendns.com/2013/01/10/high-availability-with-anycast-routing/),
[Oracle](https://dyn.com/blog/how-oracle-dyn-leveraged-open-standards-and-chatbots-to-better-respond-to-attacks/#close),
[PowerDNS](https://blog.powerdns.com/2016/02/23/an-important-update-on-new-powerdns-products/),
[RIPE NCC](https://labs.ripe.net/author/wouter_miltenburg/building-the-next-generation-ris-route-collectors/stackpath), ...

Therefore so should [`YOU`](https://en.wikipedia.org/wiki/Bandwagon_effect)! 😀

## Documentation

The documentation is known to be imperfect. One could even say wanting, limited, insufficient and lacking, therefore any contribution (however small) toward its improvement is truly welcomed.

Other users did however do a fair bit of [`documentation`](https://github.com/Exa-Networks/exabgp/wiki/Related-articles), just not on the [`wiki`](https://github.com/Exa-Networks/exabgp/wiki). 😭

To understand how ExaBGP should be configured, please have a look into the [`etc/exabgp`](https://github.com/Exa-Networks/exabgp/tree/master/etc/exabgp) folder of the repository where a great many examples are available.

`exabgp --help`  is also a treasure trove of information.

## Related Projects

The following projects are related to ExaBGP

**BGP playgrounds**

* [Large Communities](https://github.com/pierky/bgp-large-communities-playground) A docker-based lab to play with BGP Large Communities
* [High availability](https://vincent.bernat.ch/en/blog/2013-exabgp-highavailability) provide redundant services
* [VXLAN](https://vincent.bernat.ch/en/blog/2017-vxlan-bgp-evpn)
* [L3 routing to the hypervisor](https://vincent.bernat.ch/en/blog/2018-l3-routing-hypervisor)
* [BGP LLGR](https://vincent.bernat.ch/en/blog/2018-bgp-llgr) BGP long lived graceful restart
* [ExaBGP Monitor](https://github.com/slowr/ExaBGP-Monitor) Connect ExaBGP with [socket.io](https://socket.io/)

**Network Protection**

* [WanGuard](https://www.andrisoft.com/software/wanguard) DDOS protection from Andrisoft
* [FastNetMon](https://github.com/pavel-odintsov/fastnetmon) a DDOS protection solution
* [exabgp edgerouter](https://github.com/infowolfe/exabgp-edgerouter) Spamhaus and Emerging Threats blocking with Ubiquiti EdgeRouters
* [exabgp-voipbl](https://github.com/GeertHauwaerts/exabgp-voipbl) advertises local or/and voipbl.org blacklist using unicast or flow route.

**Network Monitoring**

* [ARTEMIS](https://github.com/FORTH-ICS-INSPIRE/artemis) Real-Time Detection and Automatic Mitigation for BGP Prefix Hijacking.
* [GIXLG](https://github.com/dpiekacz/gixlg) a looking glass with visualisation
* [lookify](https://github.com/marc-barry/lookify) another looking glass
* [invalidroutesreporter](https://github.com/pierky/invalidroutesreporter) report/log invalid routes received by route servers

**Route Announcement**

* [BTS](https://github.com/nickrusso42518/bts) BGP Traffic Server, Traffic Engineering Automation
* [ERCO](https://erco.xyz/) web interface
* [ExaBGPmon](https://github.com/thepacketgeek/ExaBGPmon) web interface
* [ExaBGPmon Vagrant](https://github.com/DDecoene/ExaBGPmon) Fork of ExaBGPmon with a vagrantfile and install script.
* [BGPAPI](https://github.com/abh/bgpapi) an HTTP API
* [BGP commander](https://github.com/crazed/bgpcommander) Integration with etcd
* [exabgp-healthcheck](https://github.com/sysadminblog/exabgp-healthcheck) a perl based healthcheck program
* [exabgpctl](https://github.com/ahmet2mir/exabgpctl) control exabgp and get information in json,yaml and flat format

**Installation**

* [Ansible](https://github.com/sfromm/ansible-exabgp) Playbook
* [Chef](https://github.com/hw-cookbooks/exabgp) Cookbook

**Interoperability**

* [IOS2ExaBGP](https://github.com/lochiiconnectivity/ios2exa) converts Cisco IOS IPv4 BGP LOC Rib dumps to ExaBGP's format
* [MRTparse](https://github.com/YoshiyukiYamauchi/mrtparse) convert MRT format to ExaBGP

**High availability**

* [ExaZK](https://github.com/shtouff/exazk) a plugin to interface ExaBGP & ZooKeeper
* [exazk](https://github.com/ton31337/exazk) a ruby solution to interface ExaBGP & ZooKeeper to achieve service HA
* [exabgp-healthcheck](https://github.com/shthead/exabgp-healthcheck) A third party healthcheck program in Perl
* [exa-template](https://github.com/ton31337/exa-template) service discovery by BGP communities. more information on this [blog](http://blog.donatas.net/blog/2017/03/02/exa-template/)

**Performance**

* [bgperf](https://github.com/osrg/bgperf) Stress test solution for Bird and Quagga (can be used with other implementations)
* [super smash brogp](https://github.com/spotify/super-smash-brogp) Stress test BGP
* [kyro](https://github.com/kvogt/kyro) realtime network performance measurement and optimal routes injection - not really ExaBGP related, they have their own stack, but worth mentioning
* [kakapo](https://github.com/hdb3/kakapo) a BGP flooding tool

**FIB**

* [IOS-XR Solenoid](https://github.com/ios-xr/Solenoid) a FIB for ExaBGP
* [FBGP](https://github.com/trungdtbk/fbgp2)a FIB (pushing routes to a Faucet SDN controller)

**Other BGP implementation**

* [RustyBGP](https://github.com/osrg/rustybgp) (Rust) Fantastic BGP implementation 👏!
* [BioRouting](https://github.com/bio-routing) (Golang) BGP, IS-IS, OSPF - very robust implementation
* [Bird](http://bird.network.cz/) (C) trusted around the world, powerful route filtering language
* [FRR](http://frrouting.org/) (C) was Quagga, Zebra. If you do not already know it, you should
* [More](https://github.com/Exa-Networks/exabgp/wiki/Other-OSS-BGP-implementations) of known open source BGP implementation

## Features

RFC support includes ASN4, IPv6, MPLS, VPLS, Flow, Graceful Restart, Enhanced Route Refresh, Extended Next-Hop, "BGP-LS" and AIGP among others.
More information can be found [here](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information)

ExaBGP does **not** perform any FIB manipulation. If this is what you need, you may consider another open source BGP daemon such as [BIRD](http://bird.network.cz/) or [Quagga](http://www.quagga.net/).

[RFC compliance](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information) details the latest developments.

## Development

### Debug environment variable

The following "unsupported" options are available to help with development:
```
  exabgp.debug.configuration  to trace with pdb configuration parsing errors
  exabgp.debug.pdb            enable python debugger on runtime errors (be ready to use `killall python` to handle orphaned child processes)
  exabgp.debug.route          similar to using decode but using the environment
```

### Test suite

If you want to check any code changes, the repository comes with a `qa` folder, which includes many way to check code integrity.

ExaBGP comes with a set of functional tests, each test starts an IBGP daemon expecting a number of per recorded UPDATEs for the matching configuration file.

You can see all the existing tests running `./qa/bin/functional encoding --list`. Each test is numbered and can be run independently (please note that 03 is not the same as 3).

```sh
# ./qa/bin/functional encoding    # (run all the test)
# ./qa/bin/functional encoding A  # (run test 03 as reported by listing)
```

You can also manually run both the server and client for any given test:

```sh
shell1# ./qa/bin/functional encoding --server A
shell2# ./qa/bin/functional encoding --client A
```

A test suite is also present to complement the functional testing.
(`pip3 install pytest pytest-cov`)

```sh
# env exabgp_log_enable=false pytest --cov --cov-reset ./tests/*_test.py
```

You can decode UPDATE messages using ExaBGP `decode` option.

```sh
# env exabgp_tcp_bind='' ./sbin/exabgp decode -c ./etc/exabgp/api-open.conf FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:003C:02:0000001C4001010040020040030465016501800404000000C840050400000064000000002001010101
```
```json
{ "exabgp": "4.0.1", "time": 1560371099.404008, "host" : "ptr-41.212.219.82.rev.exa.net.uk", "pid" : 37750, "ppid" : 10834, "counter": 1, "type": "update", "neighbor": { "address": { "local": "127.0.0.1", "peer": "127.0.0.1" }, "asn": { "local": 1, "peer": 1 } , "direction": "in", "message": { "update": { "attribute": { "origin": "igp", "med": 200, "local-preference": 100 }, "announce": { "ipv4 unicast": { "101.1.101.1": [ { "nlri": "1.1.1.1/32", "path-information": "0.0.0.0" } ] } } } } } }
```
