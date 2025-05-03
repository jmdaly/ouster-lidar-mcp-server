# /Users/jmdaly/jj/ouster-lidar-mcp-server/scan_operations.py
import asyncio
import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

import ouster.sdk.client as client
from ouster.sdk.client import ChanField # type: ignore # noqa

import numpy as np

from app_setup import mcp, scan_sources

logger = logging.getLogger(__name__)

@mcp.tool()
async def capture_single_scan(hostname: str, ctx: Context) -> Dict[str, Any]:
    """
    Capture a single LiDAR scan from the sensor using modern SDK.
    
    Args:
        hostname: Hostname or IP address of the Ouster sensor
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with scan information
    """
    try:
        if hostname in scan_sources:
            source = scan_sources[hostname]
            logger.info(f"Capturing scan from {hostname}")
            await ctx.info("Starting scan capture using modern SDK")
            await ctx.report_progress(20, 100)
            try:
                scan_iterator = iter(source)
                scan = next(scan_iterator)
                await ctx.info("Scan capture complete")
                await ctx.report_progress(80, 100)
                try:
                    range_field = scan.field(ChanField.RANGE)
                    signal_field = scan.field(ChanField.SIGNAL)
                    reflectivity_field = scan.field(ChanField.REFLECTIVITY)
                except Exception:
                    range_field = scan.field("RANGE")
                    signal_field = scan.field("SIGNAL")
                    reflectivity_field = scan.field("REFLECTIVITY")
                await ctx.report_progress(100, 100)
                scan_info = {
                    "status": "success",
                    "scan_summary": {
                        "frame_id": scan.frame_id,
                        "scan_shape": {
                            "h": range_field.shape[0],
                            "w": range_field.shape[1],
                        },
                        "range_stats": {
                            "min": float(range_field.min()),
                            "max": float(range_field.max()),
                            "mean": float(range_field.mean()),
                        },
                        "signal_stats": {
                            "min": float(signal_field.min()),
                            "max": float(signal_field.max()),
                            "mean": float(signal_field.mean()),
                        },
                        "reflectivity_stats": {
                            "min": float(reflectivity_field.min()),
                            "max": float(reflectivity_field.max()),
                            "mean": float(reflectivity_field.mean()),
                        },
                        "num_valid_returns": int((range_field > 0).sum()),
                    }
                }
                return scan_info
            except StopIteration:
                return {
                    "status": "error",
                    "error": "No scan data available from sensor"
                }
        else:
            return {
                "status": "not_connected",
                "hostname": hostname
            }
    except Exception as e:
        logger.error(f"Error capturing scan from {hostname}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@mcp.tool()
async def get_scan(hostname: str, ctx: Context) -> Dict[str, Any]:
    """
    Get a single LiDAR scan using the modern SDK approach.
    
    This is the preferred method for getting scan data as it leverages
    the modern Ouster SDK's ScanSource functionality.
    
    Args:
        hostname: Hostname or IP address of the Ouster sensor
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with complete scan data
    """
    try:
        if hostname not in scan_sources:
            return {
                "status": "not_connected",
                "hostname": hostname,
                "message": "Sensor is not connected. Use connect_sensor first."
            }
        source = scan_sources[hostname]
        logger.info(f"Getting scan from {hostname} using modern SDK")
        await ctx.info("Retrieving scan using modern SDK")
        await ctx.report_progress(20, 100)
        try:
            scan_iterator = iter(source)
            scan = next(scan_iterator)
            await ctx.info("Scan retrieved successfully")
            await ctx.report_progress(80, 100)
            scan_data = {
                "frame_id": scan.frame_id,
                "timestamp": scan.timestamp.tolist(),
                "measurement_id": scan.measurement_id.tolist(),
                "status": scan.status.tolist(),
                "fields": {}
            }
            for field_name in ['RANGE', 'SIGNAL', 'REFLECTIVITY', 'NEAR_IR']:
                try:
                    if hasattr(ChanField, field_name):
                        field_data = scan.field(getattr(ChanField, field_name))
                    else:
                        field_data = scan.field(field_name)
                    scan_data["fields"][field_name] = {
                        "shape": field_data.shape,
                        "dtype": str(field_data.dtype),
                        "min": float(field_data.min()),
                        "max": float(field_data.max()),
                        "mean": float(field_data.mean()),
                        "non_zero_count": int((field_data > 0).sum())
                    }
                except Exception:
                    continue
            await ctx.report_progress(100, 100)
            return {
                "status": "success",
                "scan_data": scan_data
            }
        except StopIteration:
            return {
                "status": "error",
                "error": "No scan data available from sensor"
            }
    except Exception as e:
        logger.error(f"Error getting scan from {hostname}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@mcp.tool()
async def stream_scans(hostname: str, num_scans: int, ctx: Context) -> Dict[str, Any]:
    """
    Stream multiple LiDAR scans from the sensor.
    
    Args:
        hostname: Hostname or IP address of the Ouster sensor
        num_scans: Number of scans to capture
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with stream statistics
    """
    try:
        if hostname not in scan_sources:
            return {
                "status": "not_connected",
                "hostname": hostname,
                "message": "Sensor is not connected. Use connect_sensor first."
            }
        source = scan_sources[hostname]
        logger.info(f"Streaming {num_scans} scans from {hostname}")
        await ctx.info(f"Starting to stream {num_scans} scans")
        scans_captured = 0
        scan_stats = []
        try:
            for i, scan in enumerate(source):
                if i >= num_scans:
                    break
                range_field = scan.field(ChanField.RANGE)
                scan_stat = {
                    "frame_id": scan.frame_id,
                    "valid_returns": int((range_field > 0).sum()),
                    "range_mean": float(range_field[range_field > 0].mean()) if (range_field > 0).any() else 0.0
                }
                scan_stats.append(scan_stat)
                scans_captured += 1
                progress = int((scans_captured / num_scans) * 100)
                await ctx.report_progress(progress, 100)
                await ctx.info(f"Captured scan {scans_captured}/{num_scans}")
        except Exception as stream_error:
            logger.error(f"Error during streaming: {stream_error}")
            return {
                "status": "error",
                "error": f"Streaming failed after {scans_captured} scans: {str(stream_error)}"
            }
        await ctx.info(f"Successfully streamed {scans_captured} scans")
        return {
            "status": "success",
            "scans_captured": scans_captured,
            "scan_statistics": scan_stats
        }
    except Exception as e:
        logger.error(f"Error streaming scans from {hostname}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@mcp.tool()
async def process_point_cloud(hostname: str, ctx: Context, max_distance: Optional[float] = None) -> Dict[str, Any]:
    """
    Process a LiDAR scan and extract 3D point cloud information using modern SDK.
    
    Args:
        hostname: Hostname or IP address of the Ouster sensor
        ctx: MCP context object for progress reporting
        max_distance: Maximum distance in meters to consider points valid (optional)
        
    Returns:
        Dictionary with detailed point cloud information
    """
    try:
        if hostname in scan_sources:
            source = scan_sources[hostname]
            info = source.metadata
            await ctx.info("Capturing scan for point cloud processing using modern SDK")
            await ctx.report_progress(10, 100)
            try:
                scan_iterator = iter(source)
                scan = next(scan_iterator)
                await ctx.info("Scan capture complete, processing point cloud")
                await ctx.report_progress(30, 100)
            except StopIteration:
                return {
                    "status": "error",
                    "error": "No scan data available from sensor"
                }
            try:
                range_field = scan.field(ChanField.RANGE)
            except Exception:
                range_field = scan.field("RANGE")
            await ctx.info("Converting range data to 3D point cloud")
            xyz_lut = client.XYZLut(info) # type: ignore # noqa
            xyz_points = xyz_lut(range_field)
            valid_points = np.ones(xyz_points.shape[0:2], dtype=bool)
            if max_distance is not None:
                distances = np.sqrt(np.sum(xyz_points**2, axis=2))
                valid_points = np.logical_and(valid_points, distances <= max_distance)
                valid_points = np.logical_and(valid_points, range_field > 0)
            else:
                valid_points = np.logical_and(valid_points, range_field > 0)
            valid_points_count = np.sum(valid_points)
            valid_x = xyz_points[:, :, 0][valid_points]
            valid_y = xyz_points[:, :, 1][valid_points]
            valid_z = xyz_points[:, :, 2][valid_points]
            signal = None
            try:
                try:
                    signal_field = scan.field(ChanField.SIGNAL)
                except Exception:
                    signal_field = scan.field("SIGNAL")
                signal = signal_field[valid_points]
            except Exception:
                pass
            reflectivity = None
            try:
                try:
                    reflectivity_field = scan.field(ChanField.REFLECTIVITY)
                except Exception:
                    reflectivity_field = scan.field("REFLECTIVITY")
                reflectivity = reflectivity_field[valid_points]
            except Exception:
                pass
            if ctx:
                await ctx.info("Calculating point cloud statistics")
            if valid_points_count > 0:
                min_x, max_x = float(np.min(valid_x)), float(np.max(valid_x))
                min_y, max_y = float(np.min(valid_y)), float(np.max(valid_y))
                min_z, max_z = float(np.min(valid_z)), float(np.max(valid_z))
                grid_resolution = 1.0
                x_grid_size = int(np.ceil((max_x - min_x) / grid_resolution)) + 1
                y_grid_size = int(np.ceil((max_y - min_y) / grid_resolution)) + 1
                x_grid = np.floor((valid_x - min_x) / grid_resolution).astype(int)
                y_grid = np.floor((valid_y - min_y) / grid_resolution).astype(int)
                grid_counts = np.zeros((x_grid_size, y_grid_size), dtype=int)
                for i in range(len(x_grid)):
                    if 0 <= x_grid[i] < x_grid_size and 0 <= y_grid[i] < y_grid_size:
                        grid_counts[x_grid[i], y_grid[i]] += 1
                occupied_cells = np.sum(grid_counts > 0)
                occupancy_percentage = float(occupied_cells / (x_grid_size * y_grid_size) * 100)
                height_mean = float(np.mean(valid_z))
                height_std = float(np.std(valid_z))
                highest_density_cells = []
                if np.any(grid_counts > 0):
                    flat_indices = np.argsort(grid_counts.flatten())[-5:]
                    for idx in reversed(flat_indices):
                        if grid_counts.flatten()[idx] > 0:
                            cell_x, cell_y = np.unravel_index(idx, grid_counts.shape)
                            real_x = min_x + (cell_x + 0.5) * grid_resolution
                            real_y = min_y + (cell_y + 0.5) * grid_resolution
                            highest_density_cells.append({
                                "x": float(real_x),
                                "y": float(real_y),
                                "point_count": int(grid_counts[cell_x, cell_y]),
                                "density": float(grid_counts[cell_x, cell_y] / grid_resolution**2)
                            })
                result = {
                    "status": "success",
                    "frame_id": int(scan.frame_id),
                    "point_cloud": {
                        "total_points": int(range_field.shape[0] * range_field.shape[1]),
                        "valid_points": int(valid_points_count),
                        "bounding_box": {
                            "min_x": min_x,
                            "min_y": min_y,
                            "min_z": min_z,
                            "max_x": max_x,
                            "max_y": max_y,
                            "max_z": max_z,
                            "width": max_x - min_x, 
                            "length": max_y - min_y,
                            "height": max_z - min_z
                        },
                        "grid_analysis": {
                            "resolution": grid_resolution,
                            "grid_size": {
                                "x": x_grid_size,
                                "y": y_grid_size
                            },
                            "occupied_cells": int(occupied_cells),
                            "occupancy_percentage": occupancy_percentage,
                            "highest_density_regions": highest_density_cells
                        },
                        "height_statistics": {
                            "mean": height_mean,
                            "std_dev": height_std
                        }
                    }
                }
                if signal is not None:
                    result["point_cloud"]["signal_statistics"] = {
                        "min": float(np.min(signal)),
                        "max": float(np.max(signal)),
                        "mean": float(np.mean(signal)),
                        "std_dev": float(np.std(signal))
                    }
                if reflectivity is not None:
                    result["point_cloud"]["reflectivity_statistics"] = {
                        "min": float(np.min(reflectivity)),
                        "max": float(np.max(reflectivity)),
                        "mean": float(np.mean(reflectivity)),
                        "std_dev": float(np.std(reflectivity))
                    }
                return result
            else:
                return {
                    "status": "warning",
                    "message": "No valid points found in scan",
                    "frame_id": int(scan.frame_id),
                    "point_cloud": {
                        "total_points": int(range_field.shape[0] * range_field.shape[1]),
                        "valid_points": 0
                    }
                }
        else:
            return {
                "status": "not_connected",
                "hostname": hostname
            }
    except Exception as e:
        logger.error(f"Error processing point cloud from {hostname}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
