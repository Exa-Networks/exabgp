# encoding: utf-8
"""
report.py

Created by Thomas Mangin on 2014-12-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import sys
import platform
import traceback
from io import StringIO

from exabgp.version import version
from exabgp.environment import Env
from exabgp.environment import ROOT

from exabgp.logger import history


def string_exception(exception):
    buff = StringIO()
    traceback.print_exc(file=buff)
    trace = buff.getvalue()
    buff.close()
    return trace


def format_exception(exception):
    return '\n'.join(
        [_NO_PANIC + _INFO, '', '', str(type(exception)), str(exception), string_exception(exception), _FOOTER]
    )


def format_panic(dtype, value, trace):
    result = _PANIC + _INFO

    result += '-- Traceback\n\n'
    result += ''.join(traceback.format_exception(dtype, value, trace))

    result += '\n\n-- Logging History\n\n'
    result += history()
    result += '\n\n\n'

    result += _FOOTER

    return result


_INFO = """
ExaBGP version : %s
Python version : %s
System Uname   : %s
System MaxInt  : %s
Root           : %s

Environment:
%s
""" % (
    version,
    sys.version.replace('\n', ' '),
    platform.version(),
    str(sys.maxsize),
    ROOT,
    '\n'.join(Env.iter_env(diff=True)),
)


_PANIC = """
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
"""


_NO_PANIC = """
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
"""


_FOOTER = """\
********************************************************************************
-- Please provide _ALL_ the information above on :
-- https://github.com/Exa-Networks/exabgp/issues
********************************************************************************
"""
