"""Tests for multi-error collection in configuration parsing.

Tests the Error class's ability to collect multiple validation errors
instead of failing on the first error encountered.
"""

import pytest

from exabgp.configuration.core.error import Error


class TestErrorCollection:
    """Test multi-error collection functionality."""

    def test_default_fail_fast_behavior(self):
        """Test that errors fail fast by default (original behavior)."""
        error = Error()
        assert not error.has_errors()
        assert error.get_all_errors() == []

        # set() should not raise, just return False
        result = error.set('first error')
        assert result is False
        assert error.message == 'first error'
        assert not error.has_errors()  # Not in collection mode

    def test_enable_collection_mode(self):
        """Test enabling collection mode."""
        error = Error()
        error.enable_collection(max_errors=5)

        assert error._collect_mode is True
        assert error._max_errors == 5
        assert error._errors == []

    def test_collect_multiple_errors(self):
        """Test collecting multiple errors."""
        error = Error()
        error.enable_collection(max_errors=10)

        # Add multiple errors
        error.set('error 1')
        error.set('error 2')
        error.set('error 3')

        assert error.has_errors()
        errors = error.get_all_errors()
        assert len(errors) == 3
        assert errors == ['error 1', 'error 2', 'error 3']

    def test_max_errors_limit(self):
        """Test that collection stops at max_errors."""
        error = Error()
        error.enable_collection(max_errors=3)

        # Add errors up to limit
        error.set('error 1')
        error.set('error 2')

        # Third error should trigger exception
        with pytest.raises(Error) as exc_info:
            error.set('error 3')

        # Should have collected all 3 errors
        assert error.has_errors()
        assert len(error.get_all_errors()) == 3
        # The exception message shows the collected errors
        assert 'error 1' in str(exc_info.value)
        assert 'error 3' in str(exc_info.value)

    def test_disable_collection_mode(self):
        """Test disabling collection mode."""
        error = Error()
        error.enable_collection()
        error.set('error 1')
        error.set('error 2')

        assert error.has_errors()

        error.disable_collection()
        assert not error._collect_mode
        assert error._errors == []
        assert not error.has_errors()

    def test_throw_in_collection_mode(self):
        """Test that throw() collects error then raises."""
        error = Error()
        error.enable_collection()

        with pytest.raises(Error) as exc_info:
            error.throw('fatal error')

        # Error should be in collected errors
        assert 'fatal error' in error.get_all_errors()
        assert str(exc_info.value) == 'fatal error'

    def test_str_repr_in_collection_mode(self):
        """Test that __str__ and __repr__ show all collected errors."""
        error = Error()
        error.enable_collection()

        error.set('error 1')
        error.set('error 2')
        error.set('error 3')

        error_str = str(error)
        assert 'error 1' in error_str
        assert 'error 2' in error_str
        assert 'error 3' in error_str

        error_repr = repr(error)
        assert 'error 1' in error_repr
        assert 'error 2' in error_repr
        assert 'error 3' in error_repr

    def test_str_repr_fail_fast_mode(self):
        """Test that __str__ and __repr__ show single message in fail-fast mode."""
        error = Error()
        error.set('single error')

        assert str(error) == 'single error'
        assert repr(error) == 'single error'

    def test_clear_in_fail_fast_mode(self):
        """Test that clear() clears both message and collected errors."""
        error = Error()
        error.set('error message')
        assert error.message == 'error message'

        error.clear()
        assert error.message == ''
        assert error._errors == []

    def test_clear_in_collection_mode(self):
        """Test that clear() only clears message in collection mode."""
        error = Error()
        error.enable_collection()
        error.set('error 1')
        error.set('error 2')

        error.clear()
        assert error.message == ''
        # Errors should still be collected
        assert len(error._errors) == 2

    def test_get_all_errors_returns_copy(self):
        """Test that get_all_errors() returns a copy, not the internal list."""
        error = Error()
        error.enable_collection()
        error.set('error 1')

        errors = error.get_all_errors()
        errors.append('should not affect internal state')

        # Internal state should not be modified
        assert len(error.get_all_errors()) == 1
        assert error.get_all_errors() == ['error 1']
