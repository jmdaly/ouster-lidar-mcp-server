#!/usr/bin/env python3
"""
Direct test of MCP server tools.
This script tests the MCP tools by directly calling the functions rather than using the API.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import the tool functions directly
from app_setup import mcp
from sensor_operations import discover_sensors, get_connected_sensors, connect_sensor
from scan_operations import capture_single_scan
from visualization import list_visualizations

class MockContext:
    """Mock MCP context for testing"""
    def __init__(self):
        self.progress_values = []
        self.info_messages = []
        self.error_messages = []
        
    async def info(self, message: str) -> None:
        logger.info(f"[INFO] {message}")
        self.info_messages.append(message)
    
    async def error(self, message: str) -> None:
        logger.error(f"[ERROR] {message}")
        self.error_messages.append(message)
    
    async def report_progress(self, current: int, total: int) -> None:
        logger.info(f"[PROGRESS] {current}/{total}")
        self.progress_values.append((current, total))

async def run_test():
    ctx = MockContext()
    
    # Test discover_sensors
    logger.info("\n=== Testing discover_sensors ===")
    result = await discover_sensors(ctx)
    print(json.dumps(result, indent=2))
    
    # Test get_connected_sensors
    logger.info("\n=== Testing get_connected_sensors ===")
    result = await get_connected_sensors(ctx)
    print(json.dumps(result, indent=2))
    
    # Test connecting to a mock sensor (this will fail as expected)
    logger.info("\n=== Testing connect_sensor with mock hostname ===")
    result = await connect_sensor("mock-sensor.local", ctx)
    print(json.dumps(result, indent=2))
    
    # Test list_visualizations
    logger.info("\n=== Testing list_visualizations ===")
    result = await list_visualizations(ctx)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(run_test())