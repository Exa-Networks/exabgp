# encoding: utf-8
"""
ip.py

Created by Thomas Mangin on 2009-09-12.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import socket


def isipv4(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
        return True
    except socket.error:
        return False


def isipv6(address):
    try:
        socket.inet_pton(socket.AF_INET6, address)
        return True
    except socket.error:
        return False


def isip(address):
    return isipv4(address) or isipv6(address)
