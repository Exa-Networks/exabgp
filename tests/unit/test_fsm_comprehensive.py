#!/usr/bin/env python3
# encoding: utf-8
"""
test_fsm_comprehensive.py

Comprehensive tests for BGP Finite State Machine (FSM) implementation.
Tests state definitions, transitions, validation, API callbacks, and edge cases.

Created: 2025-11-08
"""

import pytest
import os
from unittest.mock import Mock, MagicMock, patch

# Set up environment before importing ExaBGP modules
os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'

from exabgp.bgp.fsm import FSM


class TestFSMStateConstants:
    """Test FSM state constant definitions"""

    def test_state_values(self):
        """Test that state constants have correct values"""
        assert FSM.IDLE == 0x01
        assert FSM.ACTIVE == 0x02
        assert FSM.CONNECT == 0x04
        assert FSM.OPENSENT == 0x08
        assert FSM.OPENCONFIRM == 0x10
        assert FSM.ESTABLISHED == 0x20

    def test_state_uniqueness(self):
        """Test that all states have unique values"""
        states = [
            FSM.IDLE,
            FSM.ACTIVE,
            FSM.CONNECT,
            FSM.OPENSENT,
            FSM.OPENCONFIRM,
            FSM.ESTABLISHED,
        ]
        assert len(states) == len(set(states))

    def test_state_names(self):
        """Test that state names are correctly mapped"""
        assert FSM.STATE.names[FSM.IDLE] == 'IDLE'
        assert FSM.STATE.names[FSM.ACTIVE] == 'ACTIVE'
        assert FSM.STATE.names[FSM.CONNECT] == 'CONNECT'
        assert FSM.STATE.names[FSM.OPENSENT] == 'OPENSENT'
        assert FSM.STATE.names[FSM.OPENCONFIRM] == 'OPENCONFIRM'
        assert FSM.STATE.names[FSM.ESTABLISHED] == 'ESTABLISHED'

    def test_state_codes_reverse_mapping(self):
        """Test that state codes dictionary provides reverse mapping"""
        assert FSM.STATE.codes['IDLE'] == FSM.IDLE
        assert FSM.STATE.codes['ACTIVE'] == FSM.ACTIVE
        assert FSM.STATE.codes['CONNECT'] == FSM.CONNECT
        assert FSM.STATE.codes['OPENSENT'] == FSM.OPENSENT
        assert FSM.STATE.codes['OPENCONFIRM'] == FSM.OPENCONFIRM
        assert FSM.STATE.codes['ESTABLISHED'] == FSM.ESTABLISHED

    def test_state_valid_list(self):
        """Test that valid states list contains all state codes"""
        assert FSM.IDLE in FSM.STATE.valid
        assert FSM.ACTIVE in FSM.STATE.valid
        assert FSM.CONNECT in FSM.STATE.valid
        assert FSM.OPENSENT in FSM.STATE.valid
        assert FSM.OPENCONFIRM in FSM.STATE.valid
        assert FSM.ESTABLISHED in FSM.STATE.valid
        assert len(FSM.STATE.valid) == 6


class TestFSMStateRepresentation:
    """Test FSM state string representations"""

    def test_state_repr(self):
        """Test STATE __repr__ returns proper state names"""
        assert repr(FSM.IDLE) == 'IDLE'
        assert repr(FSM.ACTIVE) == 'ACTIVE'
        assert repr(FSM.CONNECT) == 'CONNECT'
        assert repr(FSM.OPENSENT) == 'OPENSENT'
        assert repr(FSM.OPENCONFIRM) == 'OPENCONFIRM'
        assert repr(FSM.ESTABLISHED) == 'ESTABLISHED'

    def test_state_str(self):
        """Test STATE __str__ returns proper state names"""
        assert str(FSM.IDLE) == 'IDLE'
        assert str(FSM.ACTIVE) == 'ACTIVE'
        assert str(FSM.CONNECT) == 'CONNECT'
        assert str(FSM.OPENSENT) == 'OPENSENT'
        assert str(FSM.OPENCONFIRM) == 'OPENCONFIRM'
        assert str(FSM.ESTABLISHED) == 'ESTABLISHED'


class TestFSMInitialization:
    """Test FSM object initialization"""

    def test_init_with_idle_state(self):
        """Test FSM initialization with IDLE state"""
        peer = Mock()
        fsm = FSM(peer, FSM.IDLE)
        assert fsm.peer is peer
        assert fsm.state == FSM.IDLE

    def test_init_with_different_states(self):
        """Test FSM initialization with various states"""
        peer = Mock()

        states = [
            FSM.IDLE,
            FSM.ACTIVE,
            FSM.CONNECT,
            FSM.OPENSENT,
            FSM.OPENCONFIRM,
            FSM.ESTABLISHED,
        ]

        for state in states:
            fsm = FSM(peer, state)
            assert fsm.state == state
            assert fsm.peer is peer

    def test_init_preserves_peer_reference(self):
        """Test that FSM maintains reference to peer object"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.reactor = Mock()

        fsm = FSM(peer, FSM.IDLE)
        assert fsm.peer is peer
        assert fsm.peer.neighbor is peer.neighbor


class TestFSMStateComparison:
    """Test FSM state comparison operators"""

    def test_equality_with_same_state(self):
        """Test FSM equality operator with matching state"""
        peer = Mock()
        fsm = FSM(peer, FSM.IDLE)
        assert fsm == FSM.IDLE

    def test_equality_with_different_state(self):
        """Test FSM equality operator with different state"""
        peer = Mock()
        fsm = FSM(peer, FSM.IDLE)
        assert not (fsm == FSM.ACTIVE)

    def test_inequality_with_different_state(self):
        """Test FSM inequality operator with different state"""
        peer = Mock()
        fsm = FSM(peer, FSM.IDLE)
        assert fsm != FSM.ACTIVE

    def test_inequality_with_same_state(self):
        """Test FSM inequality operator with matching state"""
        peer = Mock()
        fsm = FSM(peer, FSM.ESTABLISHED)
        assert not (fsm != FSM.ESTABLISHED)

    def test_multiple_state_comparisons(self):
        """Test FSM comparison across multiple states"""
        peer = Mock()
        fsm = FSM(peer, FSM.CONNECT)

        assert fsm == FSM.CONNECT
        assert fsm != FSM.IDLE
        assert fsm != FSM.ACTIVE
        assert fsm != FSM.OPENSENT
        assert fsm != FSM.OPENCONFIRM
        assert fsm != FSM.ESTABLISHED


class TestFSMStateTransitions:
    """Test FSM state transition logic"""

    def test_change_updates_state(self):
        """Test that change() method updates FSM state"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.ACTIVE)
        assert fsm.state == FSM.ACTIVE

    def test_change_returns_self(self):
        """Test that change() returns FSM object for chaining"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.IDLE)
        result = fsm.change(FSM.ACTIVE)
        assert result is fsm

    def test_transition_idle_to_active(self):
        """Test IDLE -> ACTIVE transition"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.ACTIVE)
        assert fsm == FSM.ACTIVE

    def test_transition_active_to_connect(self):
        """Test ACTIVE -> CONNECT is allowed (via IDLE)"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        # Note: transition table shows CONNECT can come from IDLE
        # ACTIVE can transition to IDLE, then to CONNECT
        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.CONNECT)
        assert fsm == FSM.CONNECT

    def test_transition_connect_to_opensent(self):
        """Test CONNECT -> OPENSENT transition"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.CONNECT)
        fsm.change(FSM.OPENSENT)
        assert fsm == FSM.OPENSENT

    def test_transition_opensent_to_openconfirm(self):
        """Test OPENSENT -> OPENCONFIRM transition"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.OPENSENT)
        fsm.change(FSM.OPENCONFIRM)
        assert fsm == FSM.OPENCONFIRM

    def test_transition_openconfirm_to_established(self):
        """Test OPENCONFIRM -> ESTABLISHED transition"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.OPENCONFIRM)
        fsm.change(FSM.ESTABLISHED)
        assert fsm == FSM.ESTABLISHED

    def test_transition_established_to_idle(self):
        """Test ESTABLISHED -> IDLE transition (session reset)"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.ESTABLISHED)
        fsm.change(FSM.IDLE)
        assert fsm == FSM.IDLE

    def test_multiple_consecutive_transitions(self):
        """Test multiple state changes in sequence"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.ACTIVE)
        assert fsm == FSM.ACTIVE

        fsm.change(FSM.IDLE)
        assert fsm == FSM.IDLE

        fsm.change(FSM.CONNECT)
        assert fsm == FSM.CONNECT

        fsm.change(FSM.OPENSENT)
        assert fsm == FSM.OPENSENT

        fsm.change(FSM.OPENCONFIRM)
        assert fsm == FSM.OPENCONFIRM

        fsm.change(FSM.ESTABLISHED)
        assert fsm == FSM.ESTABLISHED

    def test_transition_staying_in_same_state(self):
        """Test transition to the same state (no change)"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.IDLE)
        assert fsm == FSM.IDLE


class TestFSMTransitionTable:
    """Test FSM transition table validation"""

    def test_transition_table_structure(self):
        """Test that transition table has entries for all states"""
        assert FSM.IDLE in FSM.transition
        assert FSM.ACTIVE in FSM.transition
        assert FSM.CONNECT in FSM.transition
        assert FSM.OPENSENT in FSM.transition
        assert FSM.OPENCONFIRM in FSM.transition
        assert FSM.ESTABLISHED in FSM.transition

    def test_idle_can_transition_from_all_states(self):
        """Test IDLE accepts transitions from all states (reset)"""
        allowed_from = FSM.transition[FSM.IDLE]
        assert FSM.IDLE in allowed_from
        assert FSM.ACTIVE in allowed_from
        assert FSM.CONNECT in allowed_from
        assert FSM.OPENSENT in allowed_from
        assert FSM.OPENCONFIRM in allowed_from
        assert FSM.ESTABLISHED in allowed_from

    def test_active_transition_sources(self):
        """Test ACTIVE state allowed transitions"""
        allowed_from = FSM.transition[FSM.ACTIVE]
        assert FSM.IDLE in allowed_from
        assert FSM.ACTIVE in allowed_from
        assert FSM.OPENSENT in allowed_from

    def test_connect_transition_sources(self):
        """Test CONNECT state allowed transitions"""
        allowed_from = FSM.transition[FSM.CONNECT]
        assert FSM.IDLE in allowed_from
        assert FSM.CONNECT in allowed_from
        assert FSM.ACTIVE in allowed_from

    def test_opensent_transition_sources(self):
        """Test OPENSENT state allowed transitions"""
        allowed_from = FSM.transition[FSM.OPENSENT]
        assert FSM.CONNECT in allowed_from
        # OPENSENT can only come from CONNECT

    def test_openconfirm_transition_sources(self):
        """Test OPENCONFIRM state allowed transitions"""
        allowed_from = FSM.transition[FSM.OPENCONFIRM]
        assert FSM.OPENSENT in allowed_from
        assert FSM.OPENCONFIRM in allowed_from

    def test_established_transition_sources(self):
        """Test ESTABLISHED state allowed transitions"""
        allowed_from = FSM.transition[FSM.ESTABLISHED]
        assert FSM.OPENCONFIRM in allowed_from
        assert FSM.ESTABLISHED in allowed_from


class TestFSMAPICallbacks:
    """Test FSM API notification callbacks"""

    def test_change_triggers_api_callback_when_enabled(self):
        """Test that state change triggers API callback when enabled"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': True}
        peer.reactor = Mock()
        peer.reactor.processes = Mock()
        peer.reactor.processes.fsm = Mock()

        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.ACTIVE)

        peer.reactor.processes.fsm.assert_called_once_with(peer.neighbor, fsm)

    def test_change_skips_api_callback_when_disabled(self):
        """Test that state change skips API callback when disabled"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}
        peer.reactor = Mock()
        peer.reactor.processes = Mock()
        peer.reactor.processes.fsm = Mock()

        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.ACTIVE)

        peer.reactor.processes.fsm.assert_not_called()

    def test_multiple_transitions_trigger_multiple_callbacks(self):
        """Test that multiple state changes trigger multiple callbacks"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': True}
        peer.reactor = Mock()
        peer.reactor.processes = Mock()
        peer.reactor.processes.fsm = Mock()

        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.ACTIVE)
        fsm.change(FSM.IDLE)
        fsm.change(FSM.CONNECT)

        assert peer.reactor.processes.fsm.call_count == 3

    def test_api_callback_receives_correct_parameters(self):
        """Test that API callback receives neighbor and FSM instance"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': True}
        peer.reactor = Mock()
        peer.reactor.processes = Mock()
        peer.reactor.processes.fsm = Mock()

        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.ESTABLISHED)

        call_args = peer.reactor.processes.fsm.call_args
        assert call_args[0][0] is peer.neighbor
        assert call_args[0][1] is fsm


class TestFSMRepr:
    """Test FSM object representation"""

    def test_fsm_repr_format(self):
        """Test FSM __repr__ includes state name"""
        peer = Mock()
        fsm = FSM(peer, FSM.IDLE)
        assert 'FSM state' in repr(fsm)

    def test_fsm_repr_different_states(self):
        """Test FSM __repr__ for different states"""
        peer = Mock()

        states = [
            FSM.IDLE,
            FSM.ACTIVE,
            FSM.CONNECT,
            FSM.OPENSENT,
            FSM.OPENCONFIRM,
            FSM.ESTABLISHED,
        ]

        for state in states:
            fsm = FSM(peer, state)
            assert 'FSM state' in repr(fsm)
            assert str(state) in repr(fsm)


class TestFSMName:
    """Test FSM name() method"""

    def test_name_returns_idle(self):
        """Test name() returns 'IDLE' for IDLE state"""
        peer = Mock()
        fsm = FSM(peer, FSM.IDLE)
        assert fsm.name() == 'IDLE'

    def test_name_returns_active(self):
        """Test name() returns 'ACTIVE' for ACTIVE state"""
        peer = Mock()
        fsm = FSM(peer, FSM.ACTIVE)
        assert fsm.name() == 'ACTIVE'

    def test_name_returns_connect(self):
        """Test name() returns 'CONNECT' for CONNECT state"""
        peer = Mock()
        fsm = FSM(peer, FSM.CONNECT)
        assert fsm.name() == 'CONNECT'

    def test_name_returns_opensent(self):
        """Test name() returns 'OPENSENT' for OPENSENT state"""
        peer = Mock()
        fsm = FSM(peer, FSM.OPENSENT)
        assert fsm.name() == 'OPENSENT'

    def test_name_returns_openconfirm(self):
        """Test name() returns 'OPENCONFIRM' for OPENCONFIRM state"""
        peer = Mock()
        fsm = FSM(peer, FSM.OPENCONFIRM)
        assert fsm.name() == 'OPENCONFIRM'

    def test_name_returns_established(self):
        """Test name() returns 'ESTABLISHED' for ESTABLISHED state"""
        peer = Mock()
        fsm = FSM(peer, FSM.ESTABLISHED)
        assert fsm.name() == 'ESTABLISHED'

    def test_name_after_transition(self):
        """Test name() reflects current state after transition"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.IDLE)
        assert fsm.name() == 'IDLE'

        fsm.change(FSM.CONNECT)
        assert fsm.name() == 'CONNECT'

        fsm.change(FSM.ESTABLISHED)
        assert fsm.name() == 'ESTABLISHED'


class TestFSMTypicalSessionFlow:
    """Test FSM behavior in typical BGP session scenarios"""

    def test_successful_session_establishment(self):
        """Test typical successful BGP session establishment flow"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        # Start in IDLE
        fsm = FSM(peer, FSM.IDLE)
        assert fsm == FSM.IDLE

        # Attempt connection -> ACTIVE
        fsm.change(FSM.ACTIVE)
        assert fsm == FSM.ACTIVE

        # TCP connected -> CONNECT (via IDLE)
        fsm.change(FSM.IDLE)
        fsm.change(FSM.CONNECT)
        assert fsm == FSM.CONNECT

        # OPEN sent -> OPENSENT
        fsm.change(FSM.OPENSENT)
        assert fsm == FSM.OPENSENT

        # OPEN received and validated -> OPENCONFIRM
        fsm.change(FSM.OPENCONFIRM)
        assert fsm == FSM.OPENCONFIRM

        # KEEPALIVE exchanged -> ESTABLISHED
        fsm.change(FSM.ESTABLISHED)
        assert fsm == FSM.ESTABLISHED

    def test_session_reset_from_established(self):
        """Test session reset from ESTABLISHED to IDLE"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.ESTABLISHED)
        fsm.change(FSM.IDLE)
        assert fsm == FSM.IDLE

    def test_connection_failure_recovery(self):
        """Test connection failure and recovery"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        # Try to connect
        fsm = FSM(peer, FSM.IDLE)
        fsm.change(FSM.ACTIVE)
        assert fsm == FSM.ACTIVE

        # Connection fails, back to IDLE
        fsm.change(FSM.IDLE)
        assert fsm == FSM.IDLE

        # Retry connection
        fsm.change(FSM.ACTIVE)
        assert fsm == FSM.ACTIVE

    def test_open_message_collision(self):
        """Test handling of simultaneous OPEN messages (collision)"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        # Both sides send OPEN -> OPENCONFIRM
        fsm = FSM(peer, FSM.OPENCONFIRM)

        # Stay in OPENCONFIRM while resolving collision
        fsm.change(FSM.OPENCONFIRM)
        assert fsm == FSM.OPENCONFIRM

        # Eventually resolve and establish
        fsm.change(FSM.ESTABLISHED)
        assert fsm == FSM.ESTABLISHED


class TestFSMEdgeCases:
    """Test FSM edge cases and boundary conditions"""

    def test_fsm_with_none_peer(self):
        """Test FSM initialization with None peer (edge case)"""
        fsm = FSM(None, FSM.IDLE)
        assert fsm.peer is None
        assert fsm.state == FSM.IDLE

    def test_rapid_state_changes(self):
        """Test rapid consecutive state changes"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.IDLE)

        # Rapidly change states
        for _ in range(10):
            fsm.change(FSM.ACTIVE)
            fsm.change(FSM.IDLE)

        assert fsm == FSM.IDLE

    def test_state_persistence_across_comparisons(self):
        """Test that state comparisons don't modify state"""
        peer = Mock()
        fsm = FSM(peer, FSM.CONNECT)

        # Multiple comparisons shouldn't change state
        _ = fsm == FSM.IDLE
        _ = fsm != FSM.ACTIVE
        _ = fsm == FSM.CONNECT

        assert fsm == FSM.CONNECT

    def test_fsm_state_is_integer(self):
        """Test that FSM states are integer values"""
        peer = Mock()
        fsm = FSM(peer, FSM.IDLE)

        assert isinstance(fsm.state, int)
        assert fsm.state == 0x01


class TestFSMSessionLifecycle:
    """Test complete FSM session lifecycle scenarios"""

    def test_full_lifecycle_with_api_tracking(self):
        """Test full session lifecycle with API callbacks"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': True}
        peer.reactor = Mock()
        peer.reactor.processes = Mock()
        peer.reactor.processes.fsm = Mock()

        fsm = FSM(peer, FSM.IDLE)

        # Track all state changes
        states = []

        def record_state(neighbor, fsm_obj):
            states.append(fsm_obj.state)

        peer.reactor.processes.fsm.side_effect = record_state

        # Go through full lifecycle
        fsm.change(FSM.ACTIVE)
        fsm.change(FSM.IDLE)
        fsm.change(FSM.CONNECT)
        fsm.change(FSM.OPENSENT)
        fsm.change(FSM.OPENCONFIRM)
        fsm.change(FSM.ESTABLISHED)

        # Verify all transitions were recorded
        assert states == [
            FSM.ACTIVE,
            FSM.IDLE,
            FSM.CONNECT,
            FSM.OPENSENT,
            FSM.OPENCONFIRM,
            FSM.ESTABLISHED,
        ]

    def test_session_termination_and_restart(self):
        """Test session termination and restart"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.ESTABLISHED)

        # Terminate session
        fsm.change(FSM.IDLE)
        assert fsm == FSM.IDLE

        # Restart session
        fsm.change(FSM.CONNECT)
        fsm.change(FSM.OPENSENT)
        fsm.change(FSM.OPENCONFIRM)
        fsm.change(FSM.ESTABLISHED)
        assert fsm == FSM.ESTABLISHED

    def test_multiple_failed_connection_attempts(self):
        """Test multiple connection failures before success"""
        peer = Mock()
        peer.neighbor = Mock()
        peer.neighbor.api = {'fsm': False}

        fsm = FSM(peer, FSM.IDLE)

        # Multiple failed attempts
        for _ in range(5):
            fsm.change(FSM.ACTIVE)
            fsm.change(FSM.IDLE)

        # Finally succeed
        fsm.change(FSM.CONNECT)
        fsm.change(FSM.OPENSENT)
        fsm.change(FSM.OPENCONFIRM)
        fsm.change(FSM.ESTABLISHED)

        assert fsm == FSM.ESTABLISHED
