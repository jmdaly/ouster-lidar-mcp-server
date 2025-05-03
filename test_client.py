#!/usr/bin/env python3
"""
Test client for the Ouster Lidar MCP Server.

This script demonstrates how to use the MCP client to interact with the server.
"""

import argparse
import asyncio
import json
import os
import pytest
import sys
from typing import Optional, Dict, Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client


async def run_test(server_params: dict, sensor_hostname: str):
    """Run a test of the Ouster Lidar MCP Server."""
    print(f"Connecting to MCP server at {server_params.get('url', 'stdio')}")
    
    # Create client based on transport type
    if "url" in server_params:
        # SSE transport
        async with sse_client(server_params["url"]) as (read, write):
            await test_functionality(read, write, sensor_hostname)
    else:
        # Stdio transport
        server_params_obj = StdioServerParameters(
            command=server_params["command"],
            args=server_params.get("args", []),
            env=server_params.get("env", None)
        )
        async with stdio_client(server_params_obj) as (read, write):
            await test_functionality(read, write, sensor_hostname)


@pytest.mark.skip(reason="Requires manual setup with real server and sensor")
async def test_functionality(read, write, sensor_hostname: str):
    """
    Test the MCP server functionality with the provided transport.
    
    This function is intended to be called from other tests with proper mock objects 
    or from integration tests with real connections. It should not be run directly
    as an automated test without the required parameters.
    
    Args:
        read: Async readable stream for MCP communication
        write: Async writable stream for MCP communication
        sensor_hostname: Hostname or IP of the sensor to connect to
    """
    try:
        # Create client session
        async with ClientSession(read, write) as session:
            print("Connected to MCP server")
            
            # Initialize the session
            await session.initialize()
            
            # Get available tools
            tools_response = await session.list_tools()
            tools = tools_response.tools
            tool_names = [str(tool.name) for tool in tools]
            print(f"Available tools: {', '.join(tool_names)}")             
            # Check if ouster_lidar tool is available
            if not any(tool.name == "ouster_lidar" for tool in tools):
                print("Error: ouster_lidar tool not found")
                return
            
            # Connect to the sensor
            print(f"\nConnecting to sensor at {sensor_hostname}...")
            result = await session.call_tool(
                tool_name="ouster_lidar",
                function_name="connect_sensor",
                params={"hostname": sensor_hostname}
            )
            print(f"Connection result: {json.dumps(result, indent=2)}")
            
            if result.get("status") in ["connected", "already_connected"]:
                # Get sensor info
                print("\nGetting sensor info...")
                result = await session.call_tool(
                    tool_name="ouster_lidar",
                    function_name="get_sensor_info",
                    params={"hostname": sensor_hostname}
                )
                print(f"Sensor info: {json.dumps(result, indent=2)}")
                
                # Get list of all connected sensors
                print("\nGetting list of connected sensors...")
                result = await session.call_tool(
                    tool_name="ouster_lidar",
                    function_name="get_connected_sensors",
                    params={}
                )
                print(f"Connected sensors: {json.dumps(result, indent=2)}")
                
                # Capture a single scan
                print("\nCapturing a single scan...")
                result = await session.call_tool(
                    tool_name="ouster_lidar",
                    function_name="capture_single_scan",
                    params={"hostname": sensor_hostname}
                )
                print(f"Scan result: {json.dumps(result, indent=2)}")
                
                # Set some configuration parameters (as an example)
                print("\nSetting configuration parameters...")
                config_params = {
                    "timestamp_mode": "TIME_FROM_INTERNAL_OSC",
                    "operating_mode": "NORMAL"
                }
                result = await session.call_tool(
                    tool_name="ouster_lidar",
                    function_name="set_sensor_config", 
                    params={
                        "hostname": sensor_hostname,
                        "config_params": config_params
                    }
                )
                print(f"Config result: {json.dumps(result, indent=2)}")
                
                # Disconnect from the sensor
                print("\nDisconnecting from sensor...")
                result = await session.call_tool(
                    tool_name="ouster_lidar",
                    function_name="disconnect_sensor",
                    params={"hostname": sensor_hostname}
                )
                print(f"Disconnection result: {json.dumps(result, indent=2)}")
    
    except Exception as e:
        print(f"Error during test: {e}")


def main():
    """Main entry point for the test client."""
    parser = argparse.ArgumentParser(description="Test client for Ouster Lidar MCP Server")
    parser.add_argument("--sensor", type=str, required=True,
                      help="Hostname or IP address of the Ouster sensor")
    
    # Transport options
    transport_group = parser.add_mutually_exclusive_group(required=True)
    transport_group.add_argument("--server-script", type=str,
                       help="Path to the server script for stdio transport")
    transport_group.add_argument("--server-url", type=str,
                       help="URL of the server for SSE transport (e.g., http://localhost:8080)")
    
    args = parser.parse_args()
    
    try:
        # Determine transport parameters
        if args.server_script:
            # Use stdio transport with script path
            server_params = {
                "command": "python",
                "args": [args.server_script]
            }
        else:
            # Use SSE transport with URL
            server_params = {
                "url": args.server_url
            }
        
        asyncio.run(run_test(server_params, args.sensor))
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()



