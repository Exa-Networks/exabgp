======
ExaBGP
======

.. image:: https://img.shields.io/badge/chat-gitter-blue.svg
   :target: https://gitter.im/Exa-Networks/exabgp
   :alt: Gitter

.. image:: https://img.shields.io/pypi/v/exabgp.svg
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: Latest Version

.. image:: https://img.shields.io/pypi/dm/exabgp.svg
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: Downloads

.. image:: https://img.shields.io/scrutinizer/coverage/g/exa-networks/exabgp.svg
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

Use cases include
-----------------

- sql backed `looking glass <https://code.google.com/p/gixlg/wiki/sample_maps>`_ with prefix routing visualisation
- service `high availability <http://vincent.bernat.im/en/blog/2013-exabgp-highavailability.html>`_ automatically isolating dead servers / broken services
- `DDOS mitigation <http://perso.nautile.fr/prez/fgabut-flowspec-frnog-final.pdf>`_ solutions
- `anycasted <http://blog.iweb-hosting.co.uk/blog/2012/01/27/using-bgp-to-serve-high-availability-dns/>`_ services

Installation
============

Prerequisites
-------------

ExaBGP requires python 2.6 or 2.7. It has no external dependencies.

Using pip
---------

#. Use pip to install the packages:

::

    pip install -U exabgp
    exabgp --help


Without installation
--------------------

::

    curl -L https://github.com/Exa-Networks/exabgp/archive/%(version)s.tar.gz | tar zx
    ./exabgp-%(version)s/sbin/exabgp --help

Feedback and getting involved
=============================

- Gitter: https://gitter.im/Exa-Networks/exabgp
- #exabgp: irc://irc.freenode.net:6667/exabgp
- Google +: https://plus.google.com/u/0/communities/108249711110699351497
- Twitter: https://twitter.com/#!/search/exabgp
- Mailing list: http://groups.google.com/group/exabgp-users
- Issue tracker: https://github.com/Exa-Networks/exabgp/issues
- Code Repository: https://github.com/Exa-Networks/exabgp
