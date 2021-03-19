======
ExaBGP
======

.. image:: https://img.shields.io/pypi/v/exabgp.svg
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: Latest Version

.. image:: https://img.shields.io/pypi/dm/exabgp.svg
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: Downloads

.. image:: https://coveralls.io/repos/github/Exa-Networks/exabgp/badge.svg?branch=master
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

It supports IPv4, IPv6, mpls, vpls, bgp-ls, flowspec and more.

Installation
============

Prerequisites
-------------

ExaBGP requires a recent python 3 version (3.7 or later recommended). It includes/vendors its dependencies.

Using pip
---------

#. Use pip to install the packages:

::

    pip install -U exabgp
    exabgp --help


Without installation
--------------------

::

    curl -L https://github.com/Exa-Networks/exabgp/archive/4.2.13.tar.gz | tar zx
    ./exabgp-4.2.13/sbin/exabgp --help

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
