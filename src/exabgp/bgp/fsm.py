"""fsm.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from exabgp.reactor.peer import Peer

# https://en.wikipedia.org/wiki/Border_Gateway_Protocol#Finite-state_machines

# ======================================================== Finite State Machine
#


class FSMState(IntEnum):
    """BGP Finite State Machine states per RFC 4271 Section 8.2.2."""

    IDLE = 0x01
    ACTIVE = 0x02
    CONNECT = 0x04
    OPENSENT = 0x08
    OPENCONFIRM = 0x10
    ESTABLISHED = 0x20


class FSM:
    # mypyc compiles neither a class nested in a class body nor a bare class constant:
    # the states live at module level and FSM keeps the names every caller uses
    STATE: ClassVar[type[FSMState]] = FSMState

    IDLE: ClassVar[FSMState] = FSMState.IDLE
    ACTIVE: ClassVar[FSMState] = FSMState.ACTIVE
    CONNECT: ClassVar[FSMState] = FSMState.CONNECT
    OPENSENT: ClassVar[FSMState] = FSMState.OPENSENT
    OPENCONFIRM: ClassVar[FSMState] = FSMState.OPENCONFIRM
    ESTABLISHED: ClassVar[FSMState] = FSMState.ESTABLISHED

    # to: from - transition table mapping destination state to valid source states
    transition: ClassVar[dict[FSMState, list[FSMState]]] = {
        FSMState.IDLE: [
            FSMState.IDLE,
            FSMState.ACTIVE,
            FSMState.CONNECT,
            FSMState.OPENSENT,
            FSMState.OPENCONFIRM,
            FSMState.ESTABLISHED,
        ],
        FSMState.ACTIVE: [FSMState.IDLE, FSMState.ACTIVE, FSMState.OPENSENT],
        FSMState.CONNECT: [FSMState.IDLE, FSMState.CONNECT, FSMState.ACTIVE],
        FSMState.OPENSENT: [FSMState.CONNECT],
        FSMState.OPENCONFIRM: [FSMState.OPENSENT, FSMState.OPENCONFIRM],
        FSMState.ESTABLISHED: [FSMState.OPENCONFIRM, FSMState.ESTABLISHED],
    }

    peer: Peer
    state: FSMState

    def __init__(self, peer: Peer, state: FSMState) -> None:
        self.peer = peer
        self.state = state

    def change(self, state: FSMState) -> FSM:
        # if self.state not in self.transition.get(state,[]):
        # 	raise RuntimeError ('invalid state machine transition (from %s to %s)' % (str(self.state),str(state)))
        self.state = state
        if self.peer.neighbor.api and self.peer.neighbor.api['fsm']:
            self.peer.reactor.processes.fsm(self.peer.neighbor, self)
        return self

    def __eq__(self, other: object) -> bool:
        return self.state == other

    def __ne__(self, other: object) -> bool:
        return self.state != other

    def __repr__(self) -> str:
        return f'FSM state {self.state}'

    def name(self) -> str:
        return self.state.name
