"""pytest configuration for performance tests.

Provides fixtures and configuration for performance testing.
"""

from typing import Any
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_logger() -> Any:
    """Mock the logger to avoid initialization issues in performance tests."""
    from exabgp.logger.option import option

    # Save original values
    original_logger = option.logger
    original_formater = option.formater

    # Create a mock logger with all required methods
    mock_option_logger = Mock()
    mock_option_logger.debug = Mock()
    mock_option_logger.info = Mock()
    mock_option_logger.warning = Mock()
    mock_option_logger.error = Mock()
    mock_option_logger.critical = Mock()

    # Create a mock formater that accepts all arguments
    mock_formater = Mock(return_value='formatted message')

    option.logger = mock_option_logger
    option.formater = mock_formater

    # Also mock log to avoid other issues
    with patch('exabgp.bgp.message.update.log') as mock_log, patch(
        'exabgp.bgp.message.update.nlri.nlri.log'
    ) as mock_nlri_log, patch('exabgp.bgp.message.update.attribute.attributes.log') as mock_attr_log:
        mock_log.debug = Mock()
        mock_nlri_log.debug = Mock()
        mock_attr_log.debug = Mock()

        yield

    # Restore original values
    option.logger = original_logger
    option.formater = original_formater
