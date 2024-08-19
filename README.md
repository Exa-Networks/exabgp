ExaBGP has been used to:

- provide cross-datacenters failover solutions migrating /32 service IP.
- mitigate network attacks, centrally deploying network-level filters (blackhole and/or flowspec)
- gather network information ( using BGP-LS, or BGP with Add-Path)

More information is available on the [wiki](https://github.com/Exa-Networks/exabgp/wiki).

## Installation

### zipapp

From the source folder, it is possible to create a self-contained executable which only requires an installed python3 interpreter

```sh
> git clone https://github.com/Exa-Networks/exabgp exabgp-git

> cd exabgp-git
> release binary /usr/local/sbin/exabgp
> /usr/local/sbin/exabgp --version
```

which is a helper function and creates a python3 zipapp

```sh
> git clone https://github.com/Exa-Networks/exabgp exabgp-git

> cd exabgp-git
> python3 -m zipapp -o /usr/local/sbin/exabgp -m exabgp.application:main  -p "/usr/bin/env python3" src
> /usr/local/sbin/exabgp --version
```

### git main

In case of issues, we are asking users to run the latest code directly for a local `git clone`.

```sh
> git clone https://github.com/Exa-Networks/exabgp exabgp-git

> cd exabgp-git
> ./sbin/exabgp --version
> ./sbin/exabgp --help

> ./sbin/exabgp --run healthcheck --help
> env PYTHONPATH=./src python3 -m exabgp healthcheck --help
> ./bin/healthcheck --help
```

It is then possible to change git to use any release (here 4.2.18)

```sh
> git checkout 4.2.18
> ./sbin/exabgp --version
```

### docker

You can also use the repository to create a docker image

```sh
> git clone https://github.com/Exa-Networks/exabgp exabgp-git

> cd exabgp-git
> docker build -t exabgp ./
> docker run -p 179:1790 --mount type=bind,source=`pwd`/etc/exabgp,target=/etc/exabgp -it exabgp -v /etc/exabgp/parse-simple-v4.conf
```

It is possible to add your configuration file within the docker image and/or use the container like the exabgp binary. You can also use the `Docker.remote` file to build it using pip (does not require any other file)

### pip releases

The latest version is available on [`pypi`](https://pypi.python.org/pypi), the Python Package Index

```sh
> pip install exabgp

> exabgp --version
> exabgp --help

> exabgp --run healthcheck --help
> python3 -m exabgp healthcheck --help
 ```

### GitHub releases

It is also possible to download releases from GitHub

```sh
> curl -L https://github.com/Exa-Networks/exabgp/archive/4.2.18.tar.gz | tar zx

> cd exabgp-4.2.18
> ./sbin/exabgp --version
> ./sbin/exabgp --help

> ./sbin/exabgp --run healthcheck --help
> env PYTHONPATH=./src python3 -m exabgp healthcheck --help
> ./bin/healthcheck --help
```

### OS packages

The program is packaged for many systems such as [Debian](https://packages.debian.org/search?keywords=exabgp), [Ubuntu](https://packages.ubuntu.com/search?keywords=exabgp), [ArchLinux](https://aur.archlinux.org/packages/exabgp), [Gentoo](https://packages.gentoo.org/packages/net-misc/exabgp), [FreeBSD](https://www.freshports.org/net/exabgp/), [OSX](https://ports.macports.org/port/exabgp/).

RHEL users can find help [here](https://github.com/Exa-Networks/exabgp/wiki/RedHat).

Many OS provide old, not to say ancient, releases but on the plus side, the packaged version will be integrated with systemd.

Feel free to use your prefered installation option but should you encounter any issues, we will ask you to install the latest code (the main branch) using git.

### pick and choose

Multiple versions can be used simultaneously without conflict when ExaBGP is run from extracted archives, docker, and/or local git repositories. if you are using `master`, you can use `exabgp version` to identify the location of your installation.

## Upgrade

ExaBGP is self-contained and easy to upgrade/downgrade by:

* replacing the downloaded release folder for releases download
* running `git pull` in the repository folder for installation using git main
* running `pip install -U exabgp`, for pip installations
* running `apt update; apt upgrade exabgp` for Debian/Ubuntu

*If you are migrating your application from ExaBGP 3.4 to 4.x please read this [wiki](https://github.com/Exa-Networks/exabgp/wiki/Migration-from-3.4-to-4.0) entry*.

The configuration file and API format may change occasionally, but every effort is made to ensure backward compatibility is kept. However, users are encouraged to read the [release note/CHANGELOG](https://raw.github.com/Exa-Networks/exabgp/main/CHANGELOG) and check their setup after any upgrade.

## Support

**The most common issue reported (ExaBGP hangs after some time) is caused by using code written for ExaBGP 3.4 with 4.2 or master without having read [this wiki entry](https://github.com/Exa-Networks/exabgp/wiki/Migration-from-3.4-to-4.x)**

ExaBGP is supported through Github's [issue tracker](https://github.com/Exa-Networks/exabgp/issues). So should you encounter any problems, please do not hesitate to [report it](https://github.com/Exa-Networks/exabgp/issues?labels=bug&page=1&state=open) so we can help you.

During "day time" (GMT/BST) feel free to contact us on [`Slack`](https://join.slack.com/t/exabgp/shared_invite/enQtNTM3MTU5NTg5NTcyLTMwNmZlMGMyNTQyNWY3Y2RjYmQxODgyYzY2MGFkZmYwODMxNDZkZjc4YmMyM2QzNzA1YWM0MmZjODhlYThjNTQ). We will try to respond if available.

The best way to be informed about our progress/releases is to follow us on [Twitter](https://twitter.com/#!/search/exabgp).

If there are any bugs, we'd like to ask you to help us fix the issue using the main branch. We may then backport the fixes to the 4.2 stable branch.

Please remove any non `git main` installations if you are trying the latest release to prevent running the wrong code by accident; it happens more than you think, and verify the binary by running `exabgp version`.

We will nearly systematically ask for the `FULL` output exabgp with the option `-d`.

## Development

ExaBGP 3.4 and previous versions are Python 2 applications. ExaBGP 4.0 had support for both Python 2 and 3. The current version of ExaBGP (4.2 and main) targets Python 3 only. The code should work with all recent versions (>= 3.6), but the requirement is set to 3.8.1 as some of the tooling now requires it (such as flake8).

ExaBGP is nearly as old as Python3. A lot has changed since 2009; the application does not use Python3 'new' async-io (as we run a homemade async core engine). It may never do as development slowed, and our primary goal is ensuring reliably for current and new users.

The main branch (previously the master branch) will now be ExaBGP 5.0.x. The program command line arguments have already been changed and are no longer fully backwards compatible with versions 3 and 4. We recommend using the 4.2 releases in production, but running master is sometimes required.

## Documentation

You may want to look at these [related projects](https://github.com/Exa-Networks/exabgp/wiki/related).

The documentation is known to be imperfect. One could even say wanting, limited, insufficient and lacking. Therefore, any contribution (however small) toward its improvement is genuinely welcomed.

Other users did however do a fair bit of [`documentation`](https://github.com/Exa-Networks/exabgp/wiki/Related-articles), just not on the [`wiki`](https://github.com/Exa-Networks/exabgp/wiki). 😭

To understand how ExaBGP should be configured, please have a look into the [`etc/exabgp`](https://github.com/Exa-Networks/exabgp/tree/main/etc/exabgp) folder of the repository where a great many examples are available.

`exabgp --help`  is also a treasure trove of information.

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
