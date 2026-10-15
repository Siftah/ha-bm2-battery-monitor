"""Home Assistant fixtures for the custom integration."""

import pytest


@pytest.fixture(autouse=True)
def custom_integrations(recorder_mock, enable_custom_integrations, mock_bluetooth):
    """Load the custom component with a real in-memory Recorder and mocked radio."""
