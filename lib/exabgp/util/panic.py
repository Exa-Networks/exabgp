# encoding: utf-8
"""
panic.py

Created by Thomas Mangin on 2014-12-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.version import version

import sys
import platform

if sys.version_info[0] < 3:
    _max = sys.maxint
else:
    _max = sys.maxsize

PANIC = """
********************************************************************************
EXABGP HAD AN INTERNAL ISSUE / HELP US FIX IT
********************************************************************************

Sorry, you encountered a problem with ExaBGP and we could not keep the program
running.

There are a few things you can do to help us (and yourself):
- make sure you are running the latest version of the code available at
  https://github.com/Exa-Networks/exabgp/releases/latest
- if so report the issue on https://github.com/Exa-Networks/exabgp/issues
  so it can be fixed (github can be searched for similar reports)

PLEASE, when reporting, do include as much information as you can:
- do not obfuscate any data (feel free to send us a private  email with the
  extra information if your business policy is strict on information sharing)
  https://github.com/Exa-Networks/exabgp/wiki/FAQ
- if you can reproduce the issue, run ExaBGP with the command line option -d
  it provides us with much needed information to fix problems quickly
- include the information presented below

Should you not receive an acknowledgment of your issue on github (assignement,
comment, or similar) within a few hours, feel free to email us to make sure
it was not overlooked. (please keep in mind the authors are based in GMT/Europe)

********************************************************************************
-- Please provide ALL the information below on :
-- https://github.com/Exa-Networks/exabgp/issues
********************************************************************************

ExaBGP version : %s
Python version : %s
System Uname   : %s
System MaxInt  : %s

""" % (
    version,
    sys.version.replace('\n', ' '),
    platform.version(),
    str(_max),
)


NO_PANIC = """
********************************************************************************
EXABGP MISBEHAVED / HELP US FIX IT
********************************************************************************

Sorry, you encountered a problem with ExaBGP, as the problem only affects one
peer, we are trying to keep the program running.

There are a few things you can do to help us (and yourself):
- make sure you are running the latest version of the code available at
  https://github.com/Exa-Networks/exabgp/releases/latest
- if so report the issue on https://github.com/Exa-Networks/exabgp/issues
  so it can be fixed (github can be searched for similar reports)

PLEASE, when reporting, do include as much information as you can:
- do not obfuscate any data (feel free to send us a private  email with the
  extra information if your business policy is strict on information sharing)
  https://github.com/Exa-Networks/exabgp/wiki/FAQ
- if you can reproduce the issue, run ExaBGP with the command line option -d
  it provides us with much needed information to fix problems quickly
- include the information presented below

Should you not receive an acknowledgment of your issue on github (assignement,
comment, or similar) within a few hours, feel free to email us to make sure
it was not overlooked. (please keep in mind the authors are based in GMT/Europe)

********************************************************************************
-- Please provide ALL the information below on :
-- https://github.com/Exa-Networks/exabgp/issues
********************************************************************************

ExaBGP version : %s
Python version : %s
System Uname   : %s
System MaxInt  : %s

""" % (
    version,
    sys.version.replace('\n', ' '),
    platform.version(),
    str(_max),
)

FOOTER = """\
********************************************************************************
-- Please provide _ALL_ the information above on :
-- https://github.com/Exa-Networks/exabgp/issues
********************************************************************************
"""
