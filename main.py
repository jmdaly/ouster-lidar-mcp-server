#!/usr/bin/env python3
"""
Ouster Lidar MCP Server

This server implements the Model Context Protocol (MCP) to expose Ouster Lidar 
functionality to AI models and other clients.
"""

import argparse
import logging
import os
import signal
import sys
import asyncio
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global flag to indicate shutdown is requested
shutdown_requested = False

def signal_handler(sig, frame):
    """Handle signals by setting the shutdown flag and displaying a message."""
    global shutdown_requested
    sig_name = signal.Signals(sig).name
    logger.info(f"Received {sig_name} signal")
    logger.info("Initiating graceful shutdown...")
    
    # Set the shutdown flag for potential use by other parts of the application
    shutdown_requested = True
    
    # Import cleanup function here to avoid circular imports
    try:
        # Give the application a short time to clean up
        from app_setup import cleanup_resources
        cleanup_resources()
        logger.info("Resources cleaned up, exiting...")
        
        # Exit immediately without waiting for other handlers
        os._exit(0)
    except ImportError:
        logger.warning("Could not import cleanup_resources, exiting directly")
        os._exit(0)
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        os._exit(1)

def main():
    """
    Main entry point for the Ouster LiDAR MCP Server.
    Parses command line arguments and starts the MCP server.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Ouster LiDAR MCP Server")
    parser.add_argument("--host", type=str, default="localhost", 
                       help="Host to bind the server to (for SSE transport)")
    parser.add_argument("--port", type=int, default=8080, 
                       help="Port to bind the server to (for SSE transport)")
    parser.add_argument("--debug", action="store_true", 
                       help="Enable debug logging")
    parser.add_argument("--sse", action="store_true",
                       help="Use SSE transport instead of stdio")
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set environment variables for port and host before importing app_setup
    os.environ["MCP_PORT"] = str(args.port) if args.port is not None else "8080"
    
    # Handle None values for host
    if args.host is not None:
        os.environ["MCP_HOST"] = args.host
        
    # Set SSE-specific environment variables if using SSE transport
    if args.sse:
        os.environ["MCP_SSE_HOST"] = args.host if args.host is not None else "localhost" 
        os.environ["MCP_SSE_PORT"] = str(args.port) if args.port is not None else "8080"
    
    # Now it's safe to import the modules
    from app_setup import mcp, cleanup_resources
    import sensor_operations # noqa
    import scan_operations # noqa
    import visualization # noqa
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info(f"Starting Ouster LiDAR MCP Server in {'SSE' if args.sse else 'stdio'} mode")
        if args.sse:
            logger.info(f"Server will listen on {args.host}:{args.port}")
            try:
                # Run MCP server with SSE transport
                mcp.run(transport="sse")
            except KeyboardInterrupt:
                logger.info("Server shutdown requested via keyboard interrupt")
                cleanup_resources()
                sys.exit(0)
            except asyncio.CancelledError:
                logger.info("Async tasks cancelled during shutdown")
                cleanup_resources()
                sys.exit(0)
            except Exception as e:
                logger.error(f"Server error: {str(e)}")
                cleanup_resources()
                sys.exit(1)
        else:
            logger.info("Server is using stdio transport")
            try:
                # Run MCP server with stdio transport
                mcp.run()
            except KeyboardInterrupt:
                logger.info("Server shutdown requested via keyboard interrupt")
                cleanup_resources()
                sys.exit(0)
            except Exception as e:
                logger.error(f"Server error: {str(e)}")
                cleanup_resources()
                sys.exit(1)
    finally:
        # This should only execute if mcp.run() returns normally,
        # which is unlikely in normal operation
        logger.info("MCP server is shutting down")
        cleanup_resources()
        logger.info("Server shutdown complete")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Program interrupted, cleaning up...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        sys.exit(1)