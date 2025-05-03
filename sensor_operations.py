# /Users/jmdaly/jj/ouster-lidar-mcp-server/sensor_operations.py
import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

import ouster.sdk.client as client
from ouster.sdk.client import ChanField # type: ignore # noqa
from ouster.sdk import open_source # type: ignore # noqa

import numpy as np

from app_setup import mcp, scan_sources

logger = logging.getLogger(__name__)

@mcp.tool()
async def connect_sensor(hostname: str, ctx: Context) -> Dict[str, Any]:
    """
    Connect to an Ouster sensor using the modern SDK and return its information.
    
    Args:
        hostname: Hostname or IP address of the Ouster sensor
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with connection status and sensor information
    """
    try:
        logger.info(f"Connecting to sensor at {hostname}")
        await ctx.info(f"Attempting to connect to sensor at {hostname}")
        await ctx.report_progress(10, 100)
        
        if hostname in scan_sources:
            logger.info(f"Already connected to sensor {hostname}")
            await ctx.info(f"Already connected to sensor {hostname}")
            await ctx.report_progress(100, 100)
            source = scan_sources[hostname]
            info = source.metadata
            return {
                "status": "already_connected",
                "sensor_info": {
                    "hostname": hostname,
                    "serial": info.sn,
                    "model": info.prod_line,
                    "firmware_version": info.fw_rev,
                }
            }
        
        await ctx.info("Establishing connection using modern SDK")
        await ctx.report_progress(30, 100)
        source = open_source(hostname)
        
        await ctx.info("Connection established, retrieving sensor metadata")
        await ctx.report_progress(60, 100)
        info = source.metadata
        
        await ctx.info("Storing connection information")
        await ctx.report_progress(90, 100)
        scan_sources[hostname] = source
        
        await ctx.report_progress(100, 100)
        await ctx.info("Connection complete")
        
        return {
            "status": "connected",
            "sensor_info": {
                "hostname": hostname,
                "serial": info.sn,
                "model": info.prod_line,
                "firmware_version": info.fw_rev,
            }
        }
    except Exception as e:
        logger.error(f"Error connecting to sensor {hostname}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@mcp.tool()
async def disconnect_sensor(hostname: str, ctx: Context) -> Dict[str, Any]:
    """
    Disconnect from an Ouster sensor.
    
    Args:
        hostname: Hostname or IP address of the Ouster sensor
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with disconnection status
    """
    try:
        await ctx.info(f"Processing disconnect request for sensor {hostname}")
        await ctx.report_progress(10, 100)
        
        if hostname in scan_sources:
            source = scan_sources[hostname]
            await ctx.info("Removing sensor from connected devices")
            await ctx.report_progress(50, 100)
            
            try:
                source.close()
            except AttributeError:
                pass
            
            del scan_sources[hostname]
            
            await ctx.report_progress(100, 100)
            await ctx.info("Sensor disconnected successfully")
            
            return {"status": "disconnected", "hostname": hostname}
        else:
            await ctx.info(f"Sensor {hostname} is not currently connected")
            await ctx.report_progress(100, 100)
            return {"status": "not_connected", "hostname": hostname}
    except Exception as e:
        logger.error(f"Error disconnecting from sensor {hostname}: {e}")
        await ctx.info(f"Error disconnecting from sensor: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@mcp.tool()
async def get_sensor_info(hostname: str, ctx: Context) -> Dict[str, Any]:
    """
    Get detailed information about a connected sensor.
    
    Args:
        hostname: Hostname or IP address of the Ouster sensor
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with detailed sensor information
    """
    try:
        await ctx.info(f"Retrieving information for sensor {hostname}")
        await ctx.report_progress(10, 100)
        
        if hostname in scan_sources:
            source = scan_sources[hostname]
            info = source.metadata
            
            await ctx.info("Extracting sensor metadata")
            await ctx.report_progress(50, 100)
            
            sensor_info = {
                "hostname": hostname,
                "serial": info.sn,
                "model": info.prod_line,
                "firmware_version": info.fw_rev,
                "mode": info.mode,
                "azimuth_window": [info.azimuth_window[0], info.azimuth_window[1]],
                "beam_altitude_angles": info.beam_altitude_angles.tolist(),
                "beam_azimuth_angles": info.beam_azimuth_angles.tolist(),
                "lidar_origin_to_beam_origin_mm": info.lidar_origin_to_beam_origin_mm,
                "lidar_pixels_per_column": info.format.pixels_per_column,
                "lidar_columns_per_frame": info.format.columns_per_frame,
                "udp_port_lidar": info.udp_port_lidar,
                "udp_port_imu": info.udp_port_imu,
            }
            
            await ctx.report_progress(100, 100)
            await ctx.info("Sensor information retrieved successfully")
            
            return {
                "status": "success",
                "sensor_info": sensor_info
            }
        else:
            await ctx.info(f"Sensor {hostname} is not connected")
            await ctx.report_progress(100, 100)
            return {
                "status": "not_connected",
                "hostname": hostname
            }
    except Exception as e:
        logger.error(f"Error getting sensor info for {hostname}: {e}")
        await ctx.info(f"Error retrieving sensor information: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@mcp.tool()
async def get_connected_sensors(ctx: Context) -> Dict[str, Any]:
    """
    Get a list of all connected sensors.
    
    Args:
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with list of connected sensors
    """
    try:
        await ctx.info("Retrieving list of connected sensors")
        await ctx.report_progress(30, 100)
        
        connected_sensors = []
        for hostname, source in scan_sources.items():
            info = source.metadata
            connected_sensors.append({
                "hostname": hostname,
                "serial": info.sn,
                "model": info.prod_line,
            })
        
        await ctx.report_progress(100, 100)
        await ctx.info(f"Found {len(connected_sensors)} connected sensors")
        
        return {
            "status": "success",
            "connected_sensors": connected_sensors
        }
    except Exception as e:
        logger.error(f"Error getting connected sensors: {e}")
        await ctx.info(f"Error retrieving connected sensors: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@mcp.tool()
async def discover_sensors(ctx: Context) -> Dict[str, Any]:
    """
    Discover Ouster lidar sensors on the local network using mDNS.
    
    This tool uses the 'ouster-cli discover' command to find all available
    Ouster sensors on the network and returns their information.
    
    Returns:
        Dictionary with discovered sensors information
    """
    try:
        logger.info("Searching for Ouster sensors on the network")
        await ctx.info("Searching for Ouster sensors on the network using mDNS")
        await ctx.report_progress(10, 100)
        
        cmd = ["ouster-cli", "discover"]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        await ctx.report_progress(30, 100)
        stdout, stderr = process.communicate(timeout=10)
        
        if process.returncode != 0:
            logger.error(f"Error running ouster-cli discover: {stderr}")
            await ctx.info(f"Error running discovery command: {stderr}")
            return {
                "status": "error",
                "error": f"Failed to discover sensors: {stderr}"
            }
        
        await ctx.report_progress(60, 100)
        
        if not stdout.strip():
            logger.info("No sensors found on the network")
            await ctx.info("No sensors found on the network")
            return {
                "status": "success",
                "sensors": []
            }
        
        try:
            discovered_sensors = json.loads(stdout)
            sensors_info = []
            for sensor in discovered_sensors:
                sensor_info = {
                    "hostname": sensor.get("hostname", "unknown"),
                    "ip": sensor.get("ip", "unknown"),
                    "serial": sensor.get("sn", "unknown"),
                    "product_line": sensor.get("prod_line", "unknown"),
                    "firmware_version": sensor.get("fw_rev", "unknown"),
                    "connection_status": "discovered"
                }
                if sensor_info["hostname"] in scan_sources:
                    sensor_info["connection_status"] = "connected"
                sensors_info.append(sensor_info)
            
            await ctx.report_progress(100, 100)
            await ctx.info(f"Found {len(sensors_info)} sensors on the network")
            
            return {
                "status": "success",
                "sensors": sensors_info
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output: {e}")
            logger.debug(f"Raw output: {stdout}")
            sensors_info = []
            lines = stdout.strip().split('\n')
            current_sensor = {}
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("S:") or line.startswith("Sensor:"):
                    if current_sensor:
                        sensors_info.append(current_sensor)
                    hostname = line.replace("Sensor:", "").replace("S:", "").strip()
                    current_sensor = {"hostname": hostname}
                elif ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key, value = parts
                        key = key.strip().lower().replace(" ", "_")
                        if key == "i":  # Special case for IP
                            key = "ip"
                        value = value.strip()
                        current_sensor[key] = value
            if current_sensor:
                sensors_info.append(current_sensor)
            standardized_sensors = []
            for sensor in sensors_info:
                standardized = {
                    "hostname": sensor.get("hostname", "unknown"),
                    "ip": sensor.get("ip", "unknown"),
                    "serial": sensor.get("serial", sensor.get("sn", "unknown")),
                    "product_line": sensor.get("product_line", sensor.get("model", "unknown")),
                    "firmware_version": sensor.get("firmware_version", sensor.get("fw_rev", "unknown")),
                    "connection_status": "discovered"
                }
                if standardized["hostname"] in scan_sources:
                    standardized["connection_status"] = "connected"
                standardized_sensors.append(standardized)
            await ctx.report_progress(100, 100)
            await ctx.info(f"Found {len(standardized_sensors)} sensors on the network")
            return {
                "status": "success",
                "sensors": standardized_sensors
            }
    except subprocess.TimeoutExpired:
        logger.error("Timeout expired while discovering sensors")
        await ctx.info("Timeout occurred while searching for sensors")
        return {
            "status": "error",
            "error": "Discovery command timed out after 10 seconds"
        }
    except Exception as e:
        logger.error(f"Error discovering sensors: {e}")
        await ctx.info(f"Error discovering sensors: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }
