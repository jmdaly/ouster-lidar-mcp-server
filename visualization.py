# /Users/jmdaly/jj/ouster-lidar-mcp-server/visualization.py
import asyncio
import logging
import subprocess
import time
import os
import signal
from typing import Any, Dict

from mcp.server.fastmcp import Context

from app_setup import mcp, scan_sources, visualization_processes

logger = logging.getLogger(__name__)

@mcp.tool()
async def start_visualization(hostname: str, ctx: Context) -> Dict[str, Any]:
    """
    Start a point cloud visualization for a connected sensor.
    
    This tool launches the Ouster visualizer as a separate process,
    allowing for real-time visualization of the sensor data.
    
    Args:
        hostname: Hostname or IP address of the Ouster sensor
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with visualization status
    """
    try:
        logger.info(f"Starting visualization for sensor {hostname}")
        await ctx.info(f"Starting visualization for sensor {hostname}")
        await ctx.report_progress(10, 100)
        if hostname not in scan_sources:
            await ctx.info(f"Sensor {hostname} is not connected")
            return {
                "status": "not_connected",
                "hostname": hostname,
                "message": "Cannot start visualization for a sensor that is not connected"
            }
        if hostname in visualization_processes:
            pid = visualization_processes[hostname]
            try:
                import psutil
                if psutil.pid_exists(pid):
                    await ctx.info(f"Visualization is already running for sensor {hostname} (PID: {pid})")
                    return {
                        "status": "already_running",
                        "hostname": hostname,
                        "pid": pid,
                        "message": f"Visualization is already running (PID: {pid})"
                    }
                else:
                    del visualization_processes[hostname]
            except ImportError:
                logger.warning("psutil not available, cannot check if visualization process is still running")
                await ctx.info("Note: Cannot verify if previous visualization is still running")
        await ctx.report_progress(30, 100)
        try:
            process = subprocess.Popen(
                ["ouster-cli", "source", hostname, "viz"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            await ctx.report_progress(60, 100)
            await asyncio.sleep(1.0)
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                error_msg = stderr.decode('utf-8', errors='replace') if stderr else "Unknown error"
                await ctx.error(f"Visualization process exited immediately: {error_msg}")
                return {
                    "status": "error",
                    "hostname": hostname,
                    "error": f"Visualization process exited immediately: {error_msg}"
                }
            pid = process.pid
            visualization_processes[hostname] = pid
            await ctx.report_progress(100, 100)
            await ctx.info(f"Visualization started successfully for sensor {hostname} (PID: {pid})")
            return {
                "status": "success",
                "hostname": hostname,
                "pid": pid,
                "message": f"Visualization started successfully (PID: {pid})"
            }
        except Exception as e:
            await ctx.error(f"Error starting visualization: {str(e)}")
            return {
                "status": "error",
                "hostname": hostname,
                "error": f"Error starting visualization: {str(e)}"
            }
    except Exception as e:
        logger.error(f"Error in start_visualization for {hostname}: {e}")
        await ctx.error(f"Error starting visualization: {str(e)}")
        return {
            "status": "error",
            "hostname": hostname,
            "error": str(e)
        }

@mcp.tool()
async def stop_visualization(hostname: str, ctx: Context) -> Dict[str, Any]:
    """
    Stop a running point cloud visualization for a sensor.
    
    Args:
        hostname: Hostname or IP address of the Ouster sensor
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with stop operation status
    """
    try:
        logger.info(f"Stopping visualization for sensor {hostname}")
        await ctx.info(f"Stopping visualization for sensor {hostname}")
        await ctx.report_progress(10, 100)
        if hostname not in visualization_processes:
            await ctx.info(f"No visualization running for sensor {hostname}")
            return {
                "status": "not_running",
                "hostname": hostname,
                "message": "No visualization is currently running for this sensor"
            }
        pid = visualization_processes[hostname]
        await ctx.report_progress(40, 100)
        try:
            import os
            import signal
            import psutil
            if not psutil.pid_exists(pid):
                logger.info(f"Process {pid} for {hostname} no longer exists")
                await ctx.info(f"Visualization process (PID: {pid}) is no longer running")
                del visualization_processes[hostname]
                return {
                    "status": "not_running",
                    "hostname": hostname,
                    "message": f"Visualization process (PID: {pid}) is no longer running"
                }
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            parent.terminate()
            _, alive = psutil.wait_procs([parent] + children, timeout=3)
            for process in alive:
                process.kill()
            del visualization_processes[hostname]
            await ctx.report_progress(100, 100)
            await ctx.info(f"Visualization stopped successfully for sensor {hostname}")
            return {
                "status": "success",
                "hostname": hostname,
                "message": "Visualization stopped successfully"
            }
        except ImportError:
            try:
                import os
                import signal
                os.kill(pid, signal.SIGTERM)
                await asyncio.sleep(1.0)
                try:
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                    await ctx.info(f"Had to force kill visualization process (PID: {pid})")
                except OSError:
                    pass
                del visualization_processes[hostname]
                await ctx.report_progress(100, 100)
                await ctx.info(f"Visualization stopped for sensor {hostname}")
                return {
                    "status": "success",
                    "hostname": hostname,
                    "message": "Visualization stopped successfully"
                }
            except Exception as e:
                await ctx.error(f"Error stopping visualization process: {str(e)}")
                return {
                    "status": "error",
                    "hostname": hostname,
                    "error": f"Error stopping visualization process: {str(e)}"
                }
    except Exception as e:
        logger.error(f"Error in stop_visualization for {hostname}: {e}")
        await ctx.error(f"Error stopping visualization: {str(e)}")
        return {
            "status": "error",
            "hostname": hostname,
            "error": str(e)
        }

@mcp.tool()
async def list_visualizations(ctx: Context) -> Dict[str, Any]:
    """
    List all currently running sensor visualizations.
    
    Args:
        ctx: MCP context object for progress reporting
        
    Returns:
        Dictionary with list of running visualizations
    """
    try:
        logger.info("Listing running visualizations")
        await ctx.info("Retrieving list of running visualizations")
        await ctx.report_progress(20, 100)
        running_viz = []
        to_remove = []
        try:
            import psutil
            for hostname, pid in visualization_processes.items():
                if psutil.pid_exists(pid):
                    try:
                        process = psutil.Process(pid)
                        process_info = {
                            "hostname": hostname,
                            "pid": pid,
                            "cpu_percent": process.cpu_percent(interval=0.1),
                            "memory_percent": process.memory_percent(),
                            "status": process.status(),
                            "running_time": time.time() - process.create_time()
                        }
                        running_viz.append(process_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        to_remove.append(hostname)
                else:
                    to_remove.append(hostname)
        except ImportError:
            for hostname, pid in visualization_processes.items():
                running_viz.append({
                    "hostname": hostname,
                    "pid": pid,
                    "status": "unknown"
                })
        for hostname in to_remove:
            del visualization_processes[hostname]
        await ctx.report_progress(100, 100)
        await ctx.info(f"Found {len(running_viz)} running visualizations")
        return {
            "status": "success",
            "visualizations": running_viz,
            "total_count": len(running_viz)
        }
    except Exception as e:
        logger.error(f"Error listing visualizations: {e}")
        await ctx.error(f"Error listing visualizations: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }
