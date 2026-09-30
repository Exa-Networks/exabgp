# ExaBGP

**BGP Swiss Army Knife of Networking**

ExaBGP is a BGP implementation designed to enable network engineers and developers to interact with BGP networks using simple Python scripts or external programs via a simple API.

**Key Differentiator**: Unlike traditional BGP daemons (BIRD, FRRouting), ExaBGP does **not** manipulate the FIB (Forwarding Information Base). Instead, it focuses on BGP protocol implementation and provides an API for external process.

ExaBGP has a fully backward-compatible successor written in Go, called Ze (**[ze-software.net](https://ze-software.net)**). If you need more performance than a Python program can deliver, take a look.

## Table of Contents

- [Use Cases](#use-cases)
- [Features](#features)
- [Quick Start](#quick-start)
- [Version Notice](#version-notice)
- [Related Project: Ze](#related-project-ze)
- [Installation](#installation)
- [Upgrade](#upgrade)
- [Compiled build (experimental)](#compiled-build-experimental)
- [Documentation](#documentation)
- [Support](#support)
- [Contributing](#contributing)

## Use Cases

ExaBGP is used for:

- **Service Resilience**: Cross-datacenter failover solutions, migrating /32 service IPs
- **DDoS Mitigation**: Centrally deploying network-level filters (blackhole and/or FlowSpec)
- **Network Monitoring**: Gathering network information via BGP-LS or BGP with Add-Path
- **Traffic Engineering**: Dynamic route injection and manipulation via API
- **Anycast Management**: Automated anycast network control

Learn more on the [wiki](https://github.com/Exa-Networks/exabgp/wiki).

## Features

### Protocol Support
- **RFC Compliance**: ASN4, IPv6, MPLS, VPLS, Flow, Graceful Restart, Enhanced Route Refresh, Extended Next-Hop, BGP-LS, AIGP, and more
- **Address Families**: IPv4/IPv6 Unicast/Multicast, VPNv4/VPNv6, EVPN, FlowSpec, BGP-LS, MUP, SRv6
- **Capabilities**: Add-Path, Route Refresh, Graceful Restart, 4-byte ASN

See [RFC compliance details](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information) for the latest developments.

### Architecture
- **JSON API**: Control BGP via external programs (Python, shell scripts, etc.)
- **No FIB Manipulation**: Pure BGP protocol implementation
- **Event-Driven**: asyncio on `main`, a homemade reactor (which pre-dates asyncio) on 5.0
- **Extensible**: Registry-based plugin architecture

**Note**: If you need FIB manipulation, consider other open source BGP daemons such as [BIRD](http://bird.network.cz/) or [FRRouting](https://frrouting.org/).

## Quick Start

```sh
pip install exabgp
exabgp --help
```

The [Quick Start](https://github.com/Exa-Networks/exabgp/wiki/Quick-Start) tutorial on the wiki takes you from there to a running BGP session, and the [`etc/exabgp`](https://github.com/Exa-Networks/exabgp/tree/main/etc/exabgp) folder holds over 100 configuration examples.

## Version Notice

Two branches are maintained and both are supported:

- **`5.0` is the stable branch.** It is the released version (currently 5.0.13), it is what `pip`/`pipx` and most OS packages install, and it runs on Python 3.8 or later. Pick it if you want a tagged release, or if you are not on Python 3.12 yet.
- **`main` is the development branch**, and the default branch of the repository. It will become 6.0, but it is not 6.0 yet and nothing is tagged: expect the odd rough edge, even though the full unit and functional test suites run on every commit. It requires Python 3.12 or later. Pick it if you want the features being built for 6.0: asyncio engine, the interactive CLI with shell completion, and health monitoring API commands.

If you have no preference, use the stable branch. Beware that `git clone` without a checkout, and `docker pull ghcr.io/exa-networks/exabgp:latest`, both give you `main`, while `pip install exabgp` gives you the latest 5.0 release.

## Related Project: Ze

**[Ze](https://github.com/ze-software/ze)** is a new project by the ExaBGP author, a ground-up rewrite in Go aiming to be a fully programmable network stack. Beyond BGP, it manages network interfaces, programs the FIB, and serves a config editor over SSH and a web UI.

Ze is **pre-alpha**: the core BGP engine works, but APIs and config syntax will change without notice. Existing ExaBGP plugins work unchanged, and `ze config migrate` converts ExaBGP configs. If you use ExaBGP, try it with your configs and tell us what works and what does not.

Official repo: [github.com/ze-software/ze](https://github.com/ze-software/ze), development: [codeberg.org/thomas-mangin/ze](https://codeberg.org/thomas-mangin/ze), Discord: [discord.gg/ykJb8meS4](https://discord.gg/ykJb8meS4).

## Installation

```sh
# pip or pipx, the latest 5.0 release
pipx install exabgp

# the container, from ghcr.io
docker pull ghcr.io/exa-networks/exabgp:5.0.13
docker run -it --rm ghcr.io/exa-networks/exabgp:5.0.13 version

# git, running from the checkout (main by default, `git checkout 5.0` for stable)
git clone https://github.com/Exa-Networks/exabgp
cd exabgp
./sbin/exabgp version
```

Should you encounter any issues, we will ask you to install the latest version from git. The wiki [Installation Guide](https://github.com/Exa-Networks/exabgp/wiki/Installation-Guide) covers the other ways: a self-contained zipapp, GitHub release archives, OS packages, building your own container image, and running several versions side by side.

## Upgrade

Moving from 5.0 to `main` (the future 6.0) needs Python 3.12, and some configurations will not load and some API output changes shape. The [5.x to 6.0.0 migration guide](https://github.com/Exa-Networks/exabgp/wiki/From-5.x-to-6.x) lists every change and what to do about it. Run `exabgp configuration validate <file>` against your configuration before switching over.

Every effort is made to keep backward compatibility, but read the [CHANGELOG](https://github.com/Exa-Networks/exabgp/blob/main/doc/CHANGELOG.rst) and check your setup after any upgrade. Coming from 3.4, read [From 3.4 to 4.x](https://github.com/Exa-Networks/exabgp/wiki/From-3.4-to-4.x).

## Compiled build (experimental)

On `main`, the whole implementation can be compiled with [mypyc](https://mypyc.readthedocs.io/) into C extensions from the same Python source, including configuration, the reactor, API and CLI. Only package initializers and the import-time `util/mypyc.py` fallback remain Python. Build a compiled tree, wheel, or one-file executable with bundled Python; no compiled wheel is published to PyPI yet. The pure-Python build remains the default and is required for reliable `server --memory` GC inspection. See [doc/user/compiled-build.md](doc/user/compiled-build.md) for measurements, build commands and limitations, and the wiki page [Compiled Build](https://github.com/Exa-Networks/exabgp/wiki/Compiled-Build).

The whole-package build measured 1.4–2.4x faster on the documented message/RIB workloads (Apple M4 Max, Python 3.12.14). That excludes startup: the one-file macOS binary took 8.16s for `version`, so prefer the wheel for frequent short-lived commands.

## Documentation

The [**ExaBGP Wiki**](https://github.com/Exa-Networks/exabgp/wiki) is the documentation. The most useful pages:

- [**Quick Start**](https://github.com/Exa-Networks/exabgp/wiki/Quick-Start) - 5-minute tutorial
- [**Installation Guide**](https://github.com/Exa-Networks/exabgp/wiki/Installation-Guide) - Detailed installation for all platforms
- [**First BGP Session**](https://github.com/Exa-Networks/exabgp/wiki/First-BGP-Session) - Step-by-step BGP setup
- [**Configuration Syntax**](https://github.com/Exa-Networks/exabgp/wiki/Configuration-Syntax) - Complete syntax guide
- [**API Overview**](https://github.com/Exa-Networks/exabgp/wiki/API-Overview) - Architecture and patterns
- [**JSON API Reference**](https://github.com/Exa-Networks/exabgp/wiki/JSON-API-Reference) - JSON message format
- [**FlowSpec Overview**](https://github.com/Exa-Networks/exabgp/wiki/FlowSpec-Overview) - DDoS mitigation guide
- [**Debugging**](https://github.com/Exa-Networks/exabgp/wiki/Debugging) - Finding out what went wrong
- [**RFC compliance ledger**](doc/RFC_COMPLIANCE.md) - generated, in this repository: 24 RFCs requirement by requirement, with the tests which prove each one and the gaps we have not closed. Every quote in it is checked against the published RFC on every test run. The concept comes from [Ze](https://github.com/ze-software/ze), ExaBGP's successor, and was backported here in a simpler form

Run `exabgp --help` for command-line options and built-in documentation.

## Support

**The most common issue reported (ExaBGP hangs after some time) is caused by using code written for ExaBGP 3.4 with current versions (5.0+) without having read [this wiki entry](https://github.com/Exa-Networks/exabgp/wiki/From-3.4-to-4.x)**

ExaBGP is supported through GitHub's [issue tracker](https://github.com/Exa-Networks/exabgp/issues). So should you encounter any problems, please do not hesitate to [report it](https://github.com/Exa-Networks/exabgp/issues?labels=bug&page=1&state=open) so we can help you.

During "day time" (GMT/BST) feel free to contact us on [Slack](https://join.slack.com/t/exabgp/shared_invite/enQtNTM3MTU5NTg5NTcyLTMwNmZlMGMyNTQyNWY3Y2RjYmQxODgyYzY2MGFkZmYwODMxNDZkZjc4YmMyM2QzNzA1YWM0MmZjODhlYThjNTQ). We will try to respond if available. The best way to be informed about our progress/releases is to follow us on [Twitter](https://twitter.com/search?q=exabgp).

If there are any bugs, we'd like to ask you to help us fix the issue using the main branch. We will backport critical fixes to stable releases. Please remove any non `git main` installations if you are trying the latest release to prevent running the wrong code by accident; it happens more than you think. Verify the binary by running `exabgp version`.

We will nearly systematically ask for the **FULL** output of exabgp with the option `-d`.

## Contributing

Contributions are welcome, from bug reports on the [issue tracker](https://github.com/Exa-Networks/exabgp/issues) to pull requests, and documentation improvements, even small ones, are genuinely appreciated. Target `main` for new features and `5.0` for bug fixes, and include tests.

[CONTRIBUTING.md](CONTRIBUTING.md) explains the development setup, how to run the tests, and the debugging options. See [CLAUDE.md](./CLAUDE.md) for the AI development guidelines and the architecture overview.
