# encoding: utf-8
"""
fsm.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations
from enum import IntEnum

# https://en.wikipedia.org/wiki/Border_Gateway_Protocol#Finite-state_machines

# ======================================================== Finite State Machine
#


class STATE(IntEnum):
    """BGP Finite State Machine states"""
    IDLE = 0x01
    ACTIVE = 0x02
    CONNECT = 0x04
    OPENSENT = 0x08
    OPENCONFIRM = 0x10
    ESTABLISHED = 0x20

    def __repr__(self):
        """Return just the state name for backward compatibility"""
        return self.name

    def __str__(self):
        """Return just the state name for backward compatibility"""
        return self.name


# Add backward compatibility attributes for tests and legacy code
STATE.names = {state.value: state.name for state in STATE}
STATE.codes = {state.name: state.value for state in STATE}
STATE.valid = [state.value for state in STATE]


class FSM(object):
    # Expose STATE enum members at class level for backward compatibility
    IDLE = STATE.IDLE
    ACTIVE = STATE.ACTIVE
    CONNECT = STATE.CONNECT
    OPENSENT = STATE.OPENSENT
    OPENCONFIRM = STATE.OPENCONFIRM
    ESTABLISHED = STATE.ESTABLISHED

    # Keep STATE reference for tests that access FSM.STATE
    STATE = STATE

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
        return f'FSM state {self.state}'

    def name(self):
        """Return the name of the current state"""
        if isinstance(self.state, STATE):
            return self.state.name
        # Fallback for invalid states
        try:
            return STATE(self.state).name
        except ValueError:
            return 'INVALID'
