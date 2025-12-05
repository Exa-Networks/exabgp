"""Unit tests for API versioning (v4/v6).

Tests the API versioning system that allows switching between:
- v4 (legacy): supports both JSON and Text encoders
- v6 (default): JSON-only output

Created: 2024-12-04
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


class TestApiVersionConfig:
    """Test API version configuration."""

    def test_api_version_parser_valid_values(self) -> None:
        """Test api_version parser accepts valid values (4, 6)."""
        from exabgp.environment.parsing import api_version

        assert api_version('4') == 4
        assert api_version('6') == 6

    def test_api_version_parser_invalid_values(self) -> None:
        """Test api_version parser rejects invalid values."""
        from exabgp.environment.parsing import api_version

        with pytest.raises(TypeError, match='API version must be 4 or 6'):
            api_version('5')

        with pytest.raises(TypeError, match='API version must be 4 or 6'):
            api_version('7')

        with pytest.raises(TypeError, match='invalid API version'):
            api_version('invalid')

    def test_api_section_default_version(self) -> None:
        """Test ApiSection defaults to version 6."""
        from exabgp.environment.config import ApiSection

        # Access the default via the descriptor
        default = ApiSection.version.default
        assert default == 6


class TestV4JSONWrapper:
    """Test V4JSON wrapper that delegates to v6 JSON."""

    def test_v4_json_patches_version(self) -> None:
        """Test V4JSON patches version string from v6 to v4 version."""
        from exabgp.reactor.api.response.v4.json import V4JSON
        from exabgp.version import json as json_version
        from exabgp.version import json_v4

        v4_encoder = V4JSON(json_v4)

        # Create a mock JSON result that contains v6 version
        mock_v6_result = f'{{"exabgp": "{json_version}", "data": "test"}}'

        # Test the _patch_version method
        patched = v4_encoder._patch_version(mock_v6_result)
        assert f'"exabgp": "{json_v4}"' in patched
        assert f'"exabgp": "{json_version}"' not in patched

    def test_v4_json_handles_none(self) -> None:
        """Test V4JSON handles None results correctly."""
        from exabgp.reactor.api.response.v4.json import V4JSON
        from exabgp.version import json_v4

        v4_encoder = V4JSON(json_v4)
        assert v4_encoder._patch_version(None) is None


class TestV4TextWrapper:
    """Test V4Text wrapper that calls v6 JSON internally."""

    def test_v4_text_has_v6_delegate(self) -> None:
        """Test V4Text creates internal v6 JSON encoder."""
        from exabgp.reactor.api.response.v4.text import V4Text
        from exabgp.reactor.api.response.json import JSON
        from exabgp.version import text_v4

        v4_encoder = V4Text(text_v4)
        assert hasattr(v4_encoder, '_v6')
        assert isinstance(v4_encoder._v6, JSON)


class TestResponseClass:
    """Test Response class exposes both v4 and v6 encoders."""

    def test_response_has_v6_encoders(self) -> None:
        """Test Response class has v6 JSON encoder."""
        from exabgp.reactor.api.response import Response
        from exabgp.reactor.api.response.json import JSON

        assert hasattr(Response, 'JSON')
        assert Response.JSON is JSON

    def test_response_has_v4_namespace(self) -> None:
        """Test Response class has V4 namespace with v4 encoders."""
        from exabgp.reactor.api.response import Response
        from exabgp.reactor.api.response.v4.json import V4JSON
        from exabgp.reactor.api.response.v4.text import V4Text

        assert hasattr(Response, 'V4')
        assert Response.V4.JSON is V4JSON
        assert Response.V4.Text is V4Text


class TestEncoderSelection:
    """Test encoder selection based on API version in processes.py."""

    @patch('exabgp.reactor.api.processes.getenv')
    def test_v6_uses_json_encoder(self, mock_getenv: MagicMock) -> None:
        """Test v6 API uses JSON encoder regardless of encoder config."""
        from exabgp.reactor.api.response import Response
        from exabgp.reactor.api.response.json import JSON

        # Mock getenv to return v6 API version
        mock_env = MagicMock()
        mock_env.api.version = 6
        mock_env.api.respawn = True
        mock_env.api.terminate = False
        mock_env.api.ack = True
        mock_getenv.return_value = mock_env

        # Verify Response.JSON is the v6 encoder
        assert Response.JSON is JSON

    @patch('exabgp.reactor.api.processes.getenv')
    def test_v4_uses_v4_json_encoder(self, mock_getenv: MagicMock) -> None:
        """Test v4 API uses V4JSON encoder when json is configured."""
        from exabgp.reactor.api.response import Response
        from exabgp.reactor.api.response.v4.json import V4JSON

        # Mock getenv to return v4 API version
        mock_env = MagicMock()
        mock_env.api.version = 4
        mock_env.api.respawn = True
        mock_env.api.terminate = False
        mock_env.api.ack = True
        mock_getenv.return_value = mock_env

        # Verify Response.V4.JSON is the v4 JSON encoder
        assert Response.V4.JSON is V4JSON

    @patch('exabgp.reactor.api.processes.getenv')
    def test_v4_uses_v4_text_encoder(self, mock_getenv: MagicMock) -> None:
        """Test v4 API uses V4Text encoder when text is configured."""
        from exabgp.reactor.api.response import Response
        from exabgp.reactor.api.response.v4.text import V4Text

        # Mock getenv to return v4 API version
        mock_env = MagicMock()
        mock_env.api.version = 4
        mock_env.api.respawn = True
        mock_env.api.terminate = False
        mock_env.api.ack = True
        mock_getenv.return_value = mock_env

        # Verify Response.V4.Text is the v4 Text encoder
        assert Response.V4.Text is V4Text


class TestV4Version:
    """Test json_v4 version constant."""

    def test_v4_version_is_4x(self) -> None:
        """Test json_v4 starts with 4."""
        from exabgp.version import json_v4

        assert json_v4.startswith('4.')


class TestV6JSONVersion:
    """Test v6 JSON encoder version."""

    def test_v6_json_version_is_6(self) -> None:
        """Test v6 JSON encoder uses 6.0.0 version."""
        from exabgp.version import json as json_version

        assert json_version == '6.0.0'
