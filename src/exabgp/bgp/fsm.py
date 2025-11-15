"""fsm.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Dict, List

if TYPE_CHECKING:
    from exabgp.reactor.peer import Peer

# https://en.wikipedia.org/wiki/Border_Gateway_Protocol#Finite-state_machines

# ======================================================== Finite State Machine
#


class FSM:
    class STATE(int):
        IDLE: ClassVar[int] = 0x01
        ACTIVE: ClassVar[int] = 0x02
        CONNECT: ClassVar[int] = 0x04
        OPENSENT: ClassVar[int] = 0x08
        OPENCONFIRM: ClassVar[int] = 0x10
        ESTABLISHED: ClassVar[int] = 0x20

        names: ClassVar[Dict[int, str]] = {
            IDLE: 'IDLE',
            ACTIVE: 'ACTIVE',
            CONNECT: 'CONNECT',
            OPENSENT: 'OPENSENT',
            OPENCONFIRM: 'OPENCONFIRM',
            ESTABLISHED: 'ESTABLISHED',
        }

        codes: ClassVar[Dict[str, int]] = dict((name, code) for (code, name) in names.items())

        valid: ClassVar[List[int]] = list(names)

        def __init__(self, code: int) -> None:
            if code not in self.valid:
                raise RuntimeError(f'invalid FSM code {code}')
            int.__init__(code)

        def __repr__(self) -> str:
            return self.names.get(self, f'INVALID 0x{hex(self)}')

        def __str__(self) -> str:
            return repr(self)

    IDLE: STATE = STATE(0x01)
    ACTIVE: STATE = STATE(0x02)
    CONNECT: STATE = STATE(0x04)
    OPENSENT: STATE = STATE(0x08)
    OPENCONFIRM: STATE = STATE(0x10)
    ESTABLISHED: STATE = STATE(0x20)

    # to: from - transition table mapping destination state to valid source states
    transition: ClassVar[Dict[STATE, List[STATE]]] = {
        IDLE: [IDLE, ACTIVE, CONNECT, OPENSENT, OPENCONFIRM, ESTABLISHED],
        ACTIVE: [IDLE, ACTIVE, OPENSENT],
        CONNECT: [IDLE, CONNECT, ACTIVE],
        OPENSENT: [CONNECT],
        OPENCONFIRM: [OPENSENT, OPENCONFIRM],
        ESTABLISHED: [OPENCONFIRM, ESTABLISHED],
    }

    peer: Peer
    state: STATE

    def __init__(self, peer: Peer, state: STATE) -> None:
        self.peer = peer
        self.state = state

    def change(self, state: STATE) -> FSM:
        # if self.state not in self.transition.get(state,[]):
        # 	raise RuntimeError ('invalid state machine transition (from %s to %s)' % (str(self.state),str(state)))
        self.state = state
        if self.peer.neighbor.api['fsm']:  # type: ignore[index]
            self.peer.reactor.processes.fsm(self.peer.neighbor, self)
        return self

    def __eq__(self, other: object) -> bool:
        return self.state == other

    def __neq__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        return f'FSM state {self.state}'

    def name(self) -> str:
        return self.STATE.names.get(self.state, 'INVALID')
