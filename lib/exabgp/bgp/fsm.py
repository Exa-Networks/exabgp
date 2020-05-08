# encoding: utf-8
"""
fsm.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import sys


# https://en.wikipedia.org/wiki/Border_Gateway_Protocol#Finite-state_machines

# ======================================================== Finite State Machine
#


class FSM(object):
    class STATE(int):
        if sys.version_info[0] < 3:
            __slots__ = ['code']

        IDLE = 0x01
        ACTIVE = 0x02
        CONNECT = 0x04
        OPENSENT = 0x08
        OPENCONFIRM = 0x10
        ESTABLISHED = 0x20

        names = {
            IDLE: 'IDLE',
            ACTIVE: 'ACTIVE',
            CONNECT: 'CONNECT',
            OPENSENT: 'OPENSENT',
            OPENCONFIRM: 'OPENCONFIRM',
            ESTABLISHED: 'ESTABLISHED',
        }

        codes = dict((name, code) for (code, name) in names.items())

        valid = list(names)

        def __init__(self, code):
            if code not in self.valid:
                raise RuntimeError('invalid FSM code %s' % code)
            int.__init__(code)

        def __repr__(self):
            return self.names.get(self, 'INVALID 0x%s' % hex(self))

        def __str__(self):
            return repr(self)

    IDLE = STATE(0x01)
    ACTIVE = STATE(0x02)
    CONNECT = STATE(0x04)
    OPENSENT = STATE(0x08)
    OPENCONFIRM = STATE(0x10)
    ESTABLISHED = STATE(0x20)

    # to: from
    transition = {
        IDLE: [IDLE, ACTIVE, CONNECT, OPENSENT, OPENCONFIRM, ESTABLISHED],
        ACTIVE: [IDLE, ACTIVE, OPENSENT],
        CONNECT: [IDLE, CONNECT, ACTIVE],
        OPENSENT: [CONNECT],
        OPENCONFIRM: [OPENSENT, OPENCONFIRM],
        ESTABLISHED: [OPENCONFIRM, ESTABLISHED],
    }

    def __init__(self, peer, state):
        self.peer = peer
        self.state = state

    def change(self, state):
        # if self.state not in self.transition.get(state,[]):
        # 	raise RuntimeError ('invalid state machine transition (from %s to %s)' % (str(self.state),str(state)))
        self.state = state
        if self.peer.neighbor.api['fsm']:
            self.peer.reactor.processes.fsm(self.peer.neighbor, self)
        return self

    def __eq__(self, other):
        return self.state == other

    def __neq__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'FSM state %s' % self.state

    def name(self):
        return self.STATE.names.get(self.state, 'INVALID')
