======
ExaBGP
======

.. image:: https://img.shields.io/pypi/v/exabgp.svg
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: Latest Version

.. image:: https://img.shields.io/pypi/dm/exabgp.svg
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: Downloads

.. image:: https://coveralls.io/repos/github/Exa-Networks/exabgp/badge.svg?branch=main
   :target: https://coveralls.io/r/Exa-Networks/exabgp
   :alt: Coverage

.. image:: https://img.shields.io/pypi/l/exabgp.svg
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: License

.. contents:: **Table of Contents**
   :depth: 2

Introduction
============

ExaBGP allows engineers to control their network from commodity servers. Think of it as Software Defined Networking using BGP.

It can be used to announce ipv4, ipv6, vpn or flow routes (for DDOS protection) from its configuration file(s).
ExaBGP can also transform BGP messages into friendly plain text or JSON which can be easily manipulate by scripts and report peer announcements.

It does not manipulate the FIB: it speaks BGP and hands what it hears to your programs.

Twenty three address families are implemented: ipv4 and ipv6 unicast, multicast, mpls-vpn,
nlri-mpls, flow, flow-vpn, mcast-vpn, mup and sr-policy, ipv4 rtc, l2vpn evpn and vpls, and
bgp-ls with its vpn variant.

Installation
============

Prerequisites
-------------

The branch you are reading, ``main``, requires Python 3.12 or later, which is what
``pyproject.toml`` declares. The released ``5.0`` branch runs on Python 3.8 or later.
ExaBGP includes/vendors its dependencies.

Using pip
---------

``pip`` installs the latest tagged release, which comes from the ``5.0`` branch:

::

    pip install -U exabgp
    exabgp --help

Without installation
--------------------

Nothing on ``main`` is tagged, so there is no tarball for it. Clone the branch and run it
from the checkout:

::

    git clone https://github.com/Exa-Networks/exabgp.git
    ./exabgp/sbin/exabgp --help

For a released version, a tarball of the tag works without installing anything:

::

    curl -L https://github.com/Exa-Networks/exabgp/archive/5.0.13.tar.gz | tar zx
    ./exabgp-5.0.13/sbin/exabgp --help

Feedback and getting involved
=============================

- Slack: https://join.slack.com/t/exabgp/shared_invite/enQtNTM3MTU5NTg5NTcyLTZjNmZhOWY5MWU3NTlkMTc5MmZlZmI4ZDliY2RhMGIwMDNkMmIzMDE3NTgwNjkwYzNmMDMzM2QwZjdlZDkzYTg
- #exabgp: irc://irc.freenode.net:6667/exabgp (unmonitored)
- Twitter: https://twitter.com/#!/search/exabgp
- Mailing list: http://groups.google.com/group/exabgp-users
- Issue tracker: https://github.com/Exa-Networks/exabgp/issues
- Code Repository: https://github.com/Exa-Networks/exabgp

Versions
========

``README.md`` in the root of the repository carries the version notice: which branch is
released, which is in development, and what each requires. It is the maintained one, and
this file is the short form of it.
