# /Users/jmdaly/jj/ouster-lidar-mcp-server/app_setup.py
from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
import logging
import os
import atexit

# Read port from environment if available, default to 8080
port = int(os.environ.get("MCP_PORT", 8080))
host = os.environ.get("MCP_HOST", "localhost")

# Initialize the FastMCP server with the name "ouster_lidar"
mcp = FastMCP("ouster_lidar", port=port, host=host)

# Dictionary to track connected sensors
# Key: hostname, Value: sensor object
scan_sources: Dict[str, Any] = {}

# Dictionary to track visualization processes
# Key: hostname, Value: process ID (pid)
visualization_processes: Dict[str, int] = {}

# Configure logger
logger = logging.getLogger(__name__)

# Define a cleanup function to be called on exit
def cleanup_resources():
    """Cleanup function to ensure all resources are properly released on exit."""
    logger.info("Cleaning up resources before shutdown...")
    
    # Close all sensor connections
    for hostname, source in list(scan_sources.items()):
        try:
            logger.info(f"Closing connection to sensor: {hostname}")
            source.close()
        except Exception as e:
            logger.error(f"Error closing sensor connection to {hostname}: {e}")
        finally:
            scan_sources.pop(hostname, None)
    
    # Terminate all visualization processes
    for hostname, pid in list(visualization_processes.items()):
        try:
            import os
            import signal
            logger.info(f"Terminating visualization process for {hostname} (PID: {pid})")
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            logger.error(f"Error terminating visualization process for {hostname}: {e}")
        finally:
            visualization_processes.pop(hostname, None)
            
    logger.info("Cleanup completed")
    
    # Try to stop the MCP server if it's running
    try:
        mcp.stop()
        logger.info("MCP server stopped")
    except Exception as e:
        logger.error(f"Error stopping MCP server: {e}")

# Register the cleanup function to be called when the program exits
atexit.register(cleanup_resources)