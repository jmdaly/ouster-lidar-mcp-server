"""
Pytest configuration file for the Ouster Lidar MCP server tests.
"""

import pytest
import sys
from unittest.mock import MagicMock


# Mock the ouster module and its submodules
class MockOuster:
    def __init__(self):
        self.client = MagicMock()
        
        # Define mock ChanField enum
        class MockChanField:
            RANGE = MagicMock(name="RANGE")
            SIGNAL = MagicMock(name="SIGNAL")
            REFLECTIVITY = MagicMock(name="REFLECTIVITY")
        
        self.client.ChanField = MockChanField
        self.client.Sensor = MagicMock()
        self.client.ScanBatcher = MagicMock()
        self.client.SensorConfig = MagicMock()


@pytest.fixture(autouse=True)
def mock_ouster():
    """Mock the ouster module for all tests."""
    mock_ouster_module = MockOuster()
    sys.modules['ouster'] = mock_ouster_module
    sys.modules['ouster.client'] = mock_ouster_module.client
    yield mock_ouster_module
    # Clean up
    if 'ouster' in sys.modules:
        del sys.modules['ouster']
    if 'ouster.client' in sys.modules:
        del sys.modules['ouster.client']
