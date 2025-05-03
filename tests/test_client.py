"""
Unit tests for the Ouster Lidar MCP client.

These tests verify the client's ability to communicate with the MCP server
and handle various responses from the server correctly.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# We need to test the functionality in test_client.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from test_client import run_test

# Create fixtures for the test_functionality function
@pytest.fixture
def mock_read():
    return AsyncMock()

@pytest.fixture
def mock_write():
    return AsyncMock()

@pytest.fixture
def sensor_hostname():
    return "test-sensor"

# Import test_functionality after defining fixtures
from test_client import test_functionality


# Helper for creating mock MCP ClientSession
class MockClientSession:
    def __init__(self, responses=None):
        """
        Initialize with predefined responses for specific tool calls.
        
        Args:
            responses: Dictionary mapping tool+function name to response
        """
        self.responses = responses or {}
        self.initialize = AsyncMock()
        self.list_tools = AsyncMock()
        self.call_tool = AsyncMock()
        
        # Configure default responses with proper name attribute on each tool
        mock_tool = MagicMock()
        mock_tool.name = "ouster_lidar"
        mock_tool.tool_functions = [
            MagicMock(name="connect_sensor"),
            MagicMock(name="disconnect_sensor"),
            MagicMock(name="get_sensor_info"),
            MagicMock(name="get_connected_sensors"),
            MagicMock(name="capture_single_scan"),
            MagicMock(name="set_sensor_config"),
        ]
        self.list_tools.return_value = MagicMock(tools=[mock_tool])
        
        # Set up the call_tool method to return predefined responses
        async def mock_call_tool(tool_name, function_name, params):
            # Store the call
            self.call_tool(tool_name=tool_name, function_name=function_name, params=params)
            
            key = f"{tool_name}.{function_name}"
            if key in self.responses:
                return self.responses[key]
            # Default responses for common functions
            if key == "ouster_lidar.connect_sensor":
                return {
                    "status": "connected",
                    "sensor_info": {
                        "hostname": params.get("hostname", "unknown"),
                        "serial": "TEST_SERIAL",
                        "model": "TEST_MODEL",
                        "firmware_version": "TEST_FW"
                    }
                }
            elif key == "ouster_lidar.disconnect_sensor":
                return {"status": "disconnected", "hostname": params.get("hostname", "unknown")}
            elif key == "ouster_lidar.get_sensor_info":
                return {
                    "status": "success",
                    "sensor_info": {
                        "hostname": params.get("hostname", "unknown"),
                        "serial": "TEST_SERIAL",
                        "model": "TEST_MODEL",
                        "firmware_version": "TEST_FW",
                        "mode": "1024x10",
                        "azimuth_window": [0, 360],
                        "beam_altitude_angles": [0.1, 0.2, 0.3],
                        "beam_azimuth_angles": [0.1, 0.2, 0.3],
                        "lidar_origin_to_beam_origin_mm": 10.5,
                        "lidar_pixels_per_column": 64,
                        "lidar_columns_per_frame": 1024,
                        "udp_port_lidar": 7502,
                        "udp_port_imu": 7503
                    }
                }
            elif key == "ouster_lidar.get_connected_sensors":
                return {
                    "status": "success",
                    "connected_sensors": [
                        {
                            "hostname": "test-sensor-1",
                            "serial": "TEST_SERIAL_1",
                            "model": "TEST_MODEL_1"
                        }
                    ]
                }
            elif key == "ouster_lidar.capture_single_scan":
                return {
                    "status": "success",
                    "scan_summary": {
                        "frame_id": 42,
                        "scan_shape": {"h": 64, "w": 1024},
                        "range_stats": {"min": 0.0, "max": 85.0, "mean": 12.5},
                        "signal_stats": {"min": 0.0, "max": 255.0, "mean": 45.0},
                        "reflectivity_stats": {"min": 0.0, "max": 255.0, "mean": 35.0},
                        "num_valid_returns": 45000
                    }
                }
            elif key == "ouster_lidar.set_sensor_config":
                return {
                    "status": "success",
                    "config_applied": True,
                    "message": "Configuration updated successfully"
                }
            else:
                return {"status": "error", "error": f"Unknown tool/function: {key}"}
            
        self.call_tool.side_effect = mock_call_tool
    
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# Tests for stdio transport client functionality
class TestStdioClient:
    @pytest.fixture
    def mock_stdio_client(self):
        """Create a mock of the stdio_client context manager."""
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = (mock_read, mock_write)
        return mock_cm
    
    @pytest.mark.asyncio
    async def test_run_test_stdio(self, mock_stdio_client, monkeypatch):
        """Test the run_test function with stdio transport."""
        # Mock the stdio_client
        monkeypatch.setattr("test_client.stdio_client", lambda params: mock_stdio_client)
        
        # Mock the test_functionality
        mock_test_func = AsyncMock()
        monkeypatch.setattr("test_client.test_functionality", mock_test_func)
        
        # Run the test
        server_params = {
            "command": "python",
            "args": ["main.py"]
        }
        await run_test(server_params, "test-sensor")
        
        # Verify test_functionality was called correctly
        mock_test_func.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_stdio_client, monkeypatch):
        """Test client initialization with stdio transport."""
        # Mock the ClientSession
        mock_session = MockClientSession()
        mock_session_cls = AsyncMock(return_value=mock_session)
        mock_session_cls.__aenter__.return_value = mock_session
        monkeypatch.setattr("test_client.ClientSession", lambda *args: mock_session)
        
        # Run the test
        await test_functionality(AsyncMock(), AsyncMock(), "test-sensor")
        
        # Verify the session was initialized
        mock_session.initialize.assert_called_once()
        mock_session.list_tools.assert_called_once()


# Tests for SSE transport client functionality
class TestSseClient:
    @pytest.fixture
    def mock_sse_client(self):
        """Create a mock of the sse_client context manager."""
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = (mock_read, mock_write)
        return mock_cm
    
    @pytest.mark.asyncio
    async def test_run_test_sse(self, mock_sse_client, monkeypatch):
        """Test the run_test function with SSE transport."""
        # Mock the sse_client
        monkeypatch.setattr("test_client.sse_client", lambda url: mock_sse_client)
        
        # Mock the test_functionality
        mock_test_func = AsyncMock()
        monkeypatch.setattr("test_client.test_functionality", mock_test_func)
        
        # Run the test
        server_params = {
            "url": "http://localhost:8080"
        }
        await run_test(server_params, "test-sensor")
        
        # Verify test_functionality was called correctly
        mock_test_func.assert_called_once()


# Tests for all tool interactions
class TestToolInteractions:
    @pytest.fixture
    def mock_session(self):
        """Create a mock ClientSession."""
        return MockClientSession()
        
    @pytest.mark.asyncio
    async def test_connect_sensor(self, mock_session, monkeypatch, capsys):
        """Test the connect_sensor tool function."""
        monkeypatch.setattr("test_client.ClientSession", lambda *args: mock_session)
        
        # Define custom response
        mock_session.responses["ouster_lidar.connect_sensor"] = {
            "status": "connected",
            "sensor_info": {
                "hostname": "test-sensor",
                "serial": "SERIAL123",
                "model": "OS-1-64",
                "firmware_version": "v2.4.0"
            }
        }
        
        # Run the test
        await test_functionality(AsyncMock(), AsyncMock(), "test-sensor")
        
        # Check that the tool was called correctly
        mock_session.call_tool.assert_any_call(
            tool_name="ouster_lidar",
            function_name="connect_sensor",
            params={"hostname": "test-sensor"}
        )
        
        # Verify output contains the expected information
        captured = capsys.readouterr()
        assert "SERIAL123" in captured.out
        assert "OS-1-64" in captured.out
    
    @pytest.mark.asyncio
    async def test_get_sensor_info(self, mock_session, monkeypatch, capsys):
        """Test the get_sensor_info tool function."""
        monkeypatch.setattr("test_client.ClientSession", lambda *args: mock_session)
        
        # Define custom response
        mock_session.responses["ouster_lidar.get_sensor_info"] = {
            "status": "success",
            "sensor_info": {
                "hostname": "test-sensor",
                "serial": "SERIAL123",
                "model": "OS-1-64",
                "firmware_version": "v2.4.0",
                "mode": "1024x10",
                "azimuth_window": [0, 360],
                "beam_altitude_angles": [0.1, 0.2, 0.3],
                "beam_azimuth_angles": [0.1, 0.2, 0.3],
                "lidar_origin_to_beam_origin_mm": 10.5,
                "lidar_pixels_per_column": 64,
                "lidar_columns_per_frame": 1024,
                "udp_port_lidar": 7502,
                "udp_port_imu": 7503
            }
        }
        
        # Run the test
        await test_functionality(AsyncMock(), AsyncMock(), "test-sensor")
        
        # Check that the tool was called correctly
        mock_session.call_tool.assert_any_call(
            tool_name="ouster_lidar",
            function_name="get_sensor_info",
            params={"hostname": "test-sensor"}
        )
        
        # Verify output contains the expected information
        captured = capsys.readouterr()
        assert "sensor_info" in captured.out
        assert "1024x10" in captured.out
    
    @pytest.mark.asyncio
    async def test_capture_single_scan(self, mock_session, monkeypatch, capsys):
        """Test the capture_single_scan tool function."""
        monkeypatch.setattr("test_client.ClientSession", lambda *args: mock_session)
        
        # Define custom response
        mock_session.responses["ouster_lidar.capture_single_scan"] = {
            "status": "success",
            "scan_summary": {
                "frame_id": 42,
                "scan_shape": {"h": 64, "w": 1024},
                "range_stats": {"min": 0.0, "max": 85.0, "mean": 12.5},
                "signal_stats": {"min": 0.0, "max": 255.0, "mean": 45.0},
                "reflectivity_stats": {"min": 0.0, "max": 255.0, "mean": 35.0},
                "num_valid_returns": 45000
            }
        }
        
        # Run the test
        await test_functionality(AsyncMock(), AsyncMock(), "test-sensor")
        
        # Check that the tool was called correctly
        mock_session.call_tool.assert_any_call(
            tool_name="ouster_lidar",
            function_name="capture_single_scan",
            params={"hostname": "test-sensor"}
        )
        
        # Verify output contains the expected information
        captured = capsys.readouterr()
        assert "scan_summary" in captured.out
        assert "frame_id" in captured.out
    
    @pytest.mark.asyncio
    async def test_set_sensor_config(self, mock_session, monkeypatch, capsys):
        """Test the set_sensor_config tool function."""
        monkeypatch.setattr("test_client.ClientSession", lambda *args: mock_session)
        
        # Define custom response
        mock_session.responses["ouster_lidar.set_sensor_config"] = {
            "status": "success",
            "config_applied": True,
            "message": "Configuration updated successfully"
        }
        
        # Run the test
        await test_functionality(AsyncMock(), AsyncMock(), "test-sensor")
        
        # Check that the tool was called correctly
        mock_session.call_tool.assert_any_call(
            tool_name="ouster_lidar",
            function_name="set_sensor_config",
            params={
                "hostname": "test-sensor",
                "config_params": {
                    "timestamp_mode": "TIME_FROM_INTERNAL_OSC",
                    "operating_mode": "NORMAL"
                }
            }
        )
        
        # Verify output contains the expected information
        captured = capsys.readouterr()
        assert "config_applied" in captured.out
    
    @pytest.mark.asyncio
    async def test_disconnect_sensor(self, mock_session, monkeypatch, capsys):
        """Test the disconnect_sensor tool function."""
        monkeypatch.setattr("test_client.ClientSession", lambda *args: mock_session)
        
        # Define custom response
        mock_session.responses["ouster_lidar.disconnect_sensor"] = {
            "status": "disconnected",
            "hostname": "test-sensor"
        }
        
        # Run the test
        await test_functionality(AsyncMock(), AsyncMock(), "test-sensor")
        
        # Check that the tool was called correctly
        mock_session.call_tool.assert_any_call(
            tool_name="ouster_lidar",
            function_name="disconnect_sensor",
            params={"hostname": "test-sensor"}
        )
        
        # Verify output contains the expected information
        captured = capsys.readouterr()
        assert "disconnected" in captured.out
    
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_session, monkeypatch, capsys):
        """Test error handling in the client."""
        monkeypatch.setattr("test_client.ClientSession", lambda *args: mock_session)
        
        # Define error response
        mock_session.responses["ouster_lidar.connect_sensor"] = {
            "status": "error",
            "error": "Connection failed: Device not found"
        }
        
        # Run the test
        await test_functionality(AsyncMock(), AsyncMock(), "test-sensor")
        
        # Verify output contains the error information
        captured = capsys.readouterr()
        assert "error" in captured.out



