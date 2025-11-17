# ExaBGP

**BGP Swiss Army Knife of Networking**

ExaBGP is a BGP implementation designed to enable network engineers and developers to interact with BGP networks using simple Python scripts or external programs via a simple API.

**Key Differentiator**: Unlike traditional BGP daemons (BIRD, FRRouting), ExaBGP does **not** manipulate the FIB (Forwarding Information Base). Instead, it focuses on BGP protocol implementation and provides an API for external process.

## Table of Contents

<table width="100%">
<tr valign="top">
<td>

**Getting Started**
- [Use Cases](#use-cases)
- [Features](#features)
- [Quick Start](#quick-start)

</td>
<td>

**Installation**
- [Docker](#docker)
- [Zipapp](#zipapp)
- [pip releases](#pip-releases)
- [GitHub releases](#github-releases)
- [git main](#git-main)
- [OS packages](#os-packages)

</td>
<td>

**Usage**
- [Upgrade](#upgrade)
- [Documentation](#documentation)
- [Support](#support)
- [Contributing](#contributing)

</td>
<td>

**Development**
- [Requirements](#requirements)
- [Version Information](#version-information)
- [Testing](#testing)
- [Debug Options](#debug-options)
- [Message Decoding](#message-decoding)

</td>
</tr>
</table>

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
- **Event-Driven**: Custom reactor pattern (pre-dates asyncio)
- **Extensible**: Registry-based plugin architecture

**Note**: If you need FIB manipulation, consider other open source BGP daemons such as [BIRD](http://bird.network.cz/) or [FRRouting](https://frrouting.org/).

## Quick Start

The fastest way to get started:

```sh
# Using Docker
docker pull ghcr.io/exa-networks/exabgp:latest
docker run -it --rm ghcr.io/exa-networks/exabgp:latest --help

# Using zipapp (self-contained executable)
git clone https://github.com/Exa-Networks/exabgp
cd exabgp
./release binary /usr/local/sbin/exabgp
/usr/local/sbin/exabgp --version

# Using pip
pip install exabgp
exabgp --help

# From source
git clone https://github.com/Exa-Networks/exabgp
cd exabgp
./sbin/exabgp --help
```

See [Installation](#installation) for detailed options and [Documentation](#documentation) for configuration examples.

## Installation

Should you encounter any issues, we will ask you to install the latest version from git.
The simplest way to install ExaBGP is as a zipapp.

### Docker

Official container images are built and published on [GitHub](https://github.com/Exa-Networks/exabgp/pkgs/container/exabgp). To install from the command line use:

```sh
docker pull ghcr.io/exa-networks/exabgp:latest
docker run -it --rm ghcr.io/exa-networks/exabgp:latest version
```

You can also build your own container image from the repository:

```sh
git clone https://github.com/Exa-Networks/exabgp exabgp-git
cd exabgp-git
docker build -t exabgp ./
docker run -p 179:1790 --mount type=bind,source=`pwd`/etc/exabgp,target=/etc/exabgp -it exabgp -v /etc/exabgp/parse-simple-v4.conf
```

It is possible to add your configuration file within the docker image and/or use the container like the exabgp binary. You can also use the `Docker.remote` file to build it using pip (does not require any other file).

### Zipapp

From the source folder, it is possible to create a self-contained executable which only requires an installed python3 interpreter:

```sh
git clone https://github.com/Exa-Networks/exabgp exabgp-git
cd exabgp-git
./release binary /usr/local/sbin/exabgp
/usr/local/sbin/exabgp --version
```

which is a helper function and creates a python3 zipapp:

```sh
git clone https://github.com/Exa-Networks/exabgp exabgp-git
cd exabgp-git
python3 -m zipapp -o /usr/local/sbin/exabgp -m exabgp.application:main -p "/usr/bin/env python3" src
/usr/local/sbin/exabgp --version
```

### pip releases

The latest version is available on [`pypi`](https://pypi.python.org/pypi), the Python Package Index:

```sh
pip install exabgp

exabgp --version
exabgp --help

exabgp --run healthcheck --help
python3 -m exabgp healthcheck --help
```

### GitHub releases

It is also possible to download releases from GitHub:

```sh
curl -L https://github.com/Exa-Networks/exabgp/archive/5.0.0.tar.gz | tar zx
cd exabgp-5.0.0
./sbin/exabgp --version
./sbin/exabgp --help

./sbin/exabgp --run healthcheck --help
env PYTHONPATH=./src python3 -m exabgp healthcheck --help
./bin/healthcheck --help
```

### git main

In case of issues, we are asking users to run the latest code directly from a local `git clone`:

```sh
git clone https://github.com/Exa-Networks/exabgp exabgp-git
cd exabgp-git
./sbin/exabgp --version
./sbin/exabgp --help

./sbin/exabgp --run healthcheck --help
env PYTHONPATH=./src python3 -m exabgp healthcheck --help
./bin/healthcheck --help
```

It is then possible to change git to use any release (here 5.0.0):

```sh
git checkout 5.0.0
./sbin/exabgp --version
```

### OS packages

The program is packaged for many systems such as [Debian](https://packages.debian.org/search?keywords=exabgp), [Ubuntu](https://packages.ubuntu.com/search?keywords=exabgp), [ArchLinux](https://aur.archlinux.org/packages/exabgp), [Gentoo](https://packages.gentoo.org/packages/net-misc/exabgp), [FreeBSD](https://www.freshports.org/net/exabgp/), [OSX](https://ports.macports.org/port/exabgp/).

RHEL users can find help [here](https://github.com/Exa-Networks/exabgp/wiki/RedHat).

Many OS distributions provide older releases, but on the plus side, the packaged version will be integrated with systemd.

Feel free to use your preferred installation option, but should you encounter any issues, we will ask you to install the latest code (the main branch) using git.

### Pick and Choose

Multiple versions can be used simultaneously without conflict when ExaBGP is run from extracted archives, docker, and/or local git repositories. If you are using `main`, you can use `exabgp version` to identify the location of your installation.

## Upgrade

ExaBGP is self-contained and easy to upgrade/downgrade by:

- replacing the downloaded release folder for releases downloaded from GitHub
- running `git pull` in the repository folder for installation using git main
- running `pip install -U exabgp`, for pip installations
- running `apt update; apt upgrade exabgp` for Debian/Ubuntu

**If you are migrating your application from ExaBGP 3.4 to 4.x please read this [wiki](https://github.com/Exa-Networks/exabgp/wiki/Migration-from-3.4-to-4.0) entry**.

**ExaBGP 5.0.0 introduces new features** including the `silence-ack` API command. The acknowledgment feature caused issues with simple programs that did not expect ACK messages. The `silence-ack` command resolves this problem by allowing external processes to disable acknowledgment messages.

The configuration file and API format may change occasionally, but every effort is made to ensure backward compatibility is kept. However, users are encouraged to read the [release note/CHANGELOG](https://raw.githubusercontent.com/Exa-Networks/exabgp/main/CHANGELOG) and check their setup after any upgrade.

## Documentation

### 📚 Official Wiki Documentation

Comprehensive documentation is available in the [**ExaBGP Wiki**](https://github.com/Exa-Networks/exabgp/wiki):

**🚀 Getting Started:**
- [**Home**](https://github.com/Exa-Networks/exabgp/wiki/Home) - Main documentation hub
- [**Quick Start**](https://github.com/Exa-Networks/exabgp/wiki/Getting-Started/Quick-Start) - 5-minute tutorial
- [**Installation Guide**](https://github.com/Exa-Networks/exabgp/wiki/Getting-Started/Installation-Guide) - Detailed installation for all platforms
- [**First BGP Session**](https://github.com/Exa-Networks/exabgp/wiki/Getting-Started/First-BGP-Session) - Step-by-step BGP setup

**🔧 API Documentation:**
- [**API Overview**](https://github.com/Exa-Networks/exabgp/wiki/API/API-Overview) - Architecture and patterns
- [**Text API Reference**](https://github.com/Exa-Networks/exabgp/wiki/API/Text-API-Reference) - Complete text command reference
- [**JSON API Reference**](https://github.com/Exa-Networks/exabgp/wiki/API/JSON-API-Reference) - JSON message format
- [**API Commands**](https://github.com/Exa-Networks/exabgp/wiki/API/API-Commands) - A-Z command reference

**🛡️ FlowSpec & DDoS Mitigation:**
- [**FlowSpec Overview**](https://github.com/Exa-Networks/exabgp/wiki/Address-Families/FlowSpec/FlowSpec-Overview) - DDoS mitigation guide
- [**Match Conditions**](https://github.com/Exa-Networks/exabgp/wiki/Address-Families/FlowSpec/Match-Conditions) - All match types
- [**Actions Reference**](https://github.com/Exa-Networks/exabgp/wiki/Address-Families/FlowSpec/Actions-Reference) - All actions (discard, rate-limit, redirect)

**⚙️ Configuration:**
- [**Configuration Syntax**](https://github.com/Exa-Networks/exabgp/wiki/Configuration/Configuration-Syntax) - Complete syntax guide
- [**Directives Reference**](https://github.com/Exa-Networks/exabgp/wiki/Configuration/Directives-Reference) - A-Z configuration directives

**📖 Additional Resources:**
- [**RFC Compliance**](https://github.com/Exa-Networks/exabgp/wiki/RFC-Information) - 55+ RFCs implemented
- [**Migration Guide**](https://github.com/Exa-Networks/exabgp/wiki/Migration-from-3.4-to-4.x) - Upgrading from 3.4 to 4.x
- [**Related Projects**](https://github.com/Exa-Networks/exabgp/wiki/related) - Community tools and integrations
- [**User Articles**](https://github.com/Exa-Networks/exabgp/wiki/Related-articles) - Tutorials and blog posts

### 💡 Examples

To understand ExaBGP configuration in practice, explore the **98 configuration examples** in the [`etc/exabgp`](https://github.com/Exa-Networks/exabgp/tree/main/etc/exabgp) folder covering:
- Basic BGP peering
- FlowSpec rules
- IPv4/IPv6 unicast and multicast
- L3VPN, EVPN, BGP-LS
- API integration patterns
- Health checks and failover

Run `exabgp --help` for command-line options and built-in documentation.

### 🤝 Contributing to Documentation

Documentation contributions are genuinely welcomed! Even small improvements help the community. See the [Contributing](#contributing) section below.

## Development

### Requirements

- **Python 3.8+** required for ExaBGP 5.0 (supports versions 3.8 through 3.12+)
- **No asyncio**: Uses custom reactor pattern predating asyncio adoption
- **Compatibility**: Focus on reliability over adopting latest Python features

**Version 3.x** supported Python 2 only. **Version 4.x** introduced Python 3 support while maintaining Python 2 compatibility (minimum: Python 3.6). **Version 5.0** requires Python 3.8 or later, dropping Python 2 and older Python 3 versions. The minimum was increased to Python 3.8 for better tooling support (ruff, type checking) and to leverage modern Python features.

ExaBGP is nearly as old as Python 3. A lot has changed since 2009; the application does not use Python 3's async-io (as we run a homemade async core engine). It may never do as development slowed, and our primary goal is ensuring reliability for current and new users.

### Version Information

- **Current stable**: 5.0.0 (recommended for production)
- **Development**: main branch
  - **Breaking changes**: Command-line arguments changed from 4.x
  - **Note**: Due to recent async and mypy work, main may not be as stable as it used to be

The main branch (previously the master branch) is ExaBGP 5.0.x. The program command line arguments have been changed and are no longer fully backwards compatible with versions 3 and 4. Version 5.0.0 is now the stable release recommended for production use. **We recommend using the 5.0.0 release for production deployments** rather than running from main.

### Testing

**File descriptor limit**: Ensure `ulimit -n` ≥ 64000 before running tests:

```sh
ulimit -n 64000
```

**Functional tests** - BGP message encoding/decoding validation:

ExaBGP comes with a set of functional tests. Each test starts an IBGP daemon expecting a number of pre-recorded UPDATEs for the matching configuration file.

```sh
# List all available tests
./qa/bin/functional encoding --list

# Run all tests
./qa/bin/functional encoding

# Run specific test (using letter from --list, e.g., A, B)
./qa/bin/functional encoding A
```

You can also manually run both the server and client for any given test:

```sh
# In shell 1
./qa/bin/functional encoding --server A

# In shell 2
./qa/bin/functional encoding --client A
```

**Unit tests** - with coverage reporting:

A test suite is present to complement the functional testing (requires `pip3 install pytest pytest-cov`):

```sh
env exabgp_log_enable=false pytest --cov --cov-reset ./tests/*_test.py
```

**Configuration parsing tests**:

```sh
./qa/bin/parsing
```

### Debug Options

The following "unsupported" options are available to help with development:

```sh
exabgp.debug.configuration  # Trace configuration parsing errors with pdb
exabgp.debug.pdb           # Enable python debugger on runtime errors
                           # (be ready to use `killall python` for orphaned processes)
exabgp.debug.route         # Similar to using decode but using the environment
```

### Message Decoding

You can decode UPDATE messages using ExaBGP's `decode` option:

```sh
env exabgp_tcp_bind='' ./sbin/exabgp decode -c ./etc/exabgp/api-open.conf \
  FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:003C:02:0000001C4001010040020040030465016501800404000000C840050400000064000000002001010101
```

Output (JSON format):
```json
{
  "exabgp": "4.0.1",
  "time": 1560371099.404008,
  "host": "ptr-41.212.219.82.rev.exa.net.uk",
  "pid": 37750,
  "ppid": 10834,
  "counter": 1,
  "type": "update",
  "neighbor": {
    "address": {
      "local": "127.0.0.1",
      "peer": "127.0.0.1"
    },
    "asn": {
      "local": 1,
      "peer": 1
    }
  },
  "direction": "in",
  "message": {
    "update": {
      "attribute": {
        "origin": "igp",
        "med": 200,
        "local-preference": 100
      },
      "announce": {
        "ipv4 unicast": {
          "101.1.101.1": [
            {
              "nlri": "1.1.1.1/32",
              "path-information": "0.0.0.0"
            }
          ]
        }
      }
    }
  }
}
```

## Support

**The most common issue reported (ExaBGP hangs after some time) is caused by using code written for ExaBGP 3.4 with current versions (5.0+) without having read [this wiki entry](https://github.com/Exa-Networks/exabgp/wiki/Migration-from-3.4-to-4.x)**

ExaBGP is supported through GitHub's [issue tracker](https://github.com/Exa-Networks/exabgp/issues). So should you encounter any problems, please do not hesitate to [report it](https://github.com/Exa-Networks/exabgp/issues?labels=bug&page=1&state=open) so we can help you.

During "day time" (GMT/BST) feel free to contact us on [Slack](https://join.slack.com/t/exabgp/shared_invite/enQtNTM3MTU5NTg5NTcyLTMwNmZlMGMyNTQyNWY3Y2RjYmQxODgyYzY2MGFkZmYwODMxNDZkZjc4YmMyM2QzNzA1YWM0MmZjODhlYThjNTQ). We will try to respond if available.

The best way to be informed about our progress/releases is to follow us on [Twitter](https://twitter.com/search?q=exabgp).

If there are any bugs, we'd like to ask you to help us fix the issue using the main branch. We will backport critical fixes to stable releases.

Please remove any non `git main` installations if you are trying the latest release to prevent running the wrong code by accident; it happens more than you think. Verify the binary by running `exabgp version`.

We will nearly systematically ask for the **FULL** output of exabgp with the option `-d`.

## Contributing

Contributions are welcome! Here's how you can help:

1. **Report Issues**: Use our [issue tracker](https://github.com/Exa-Networks/exabgp/issues)
2. **Improve Documentation**: Even small improvements are genuinely appreciated
3. **Submit Pull Requests**:
   - Target the `main` branch for new features
   - Target `4.2` branch for bug fixes (we may backport)
   - Include tests for new functionality
   - Run `ruff format` before committing

### Development Setup

```sh
git clone https://github.com/Exa-Networks/exabgp
cd exabgp
pip install -e .
pip install pytest pytest-cov ruff
```

See [CLAUDE.md](./CLAUDE.md) for detailed AI development guidelines and architecture overview.
