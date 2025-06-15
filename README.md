# Ouster Lidar MCP Server

A Model Context Protocol (MCP) server that provides access to Ouster Lidar sensors via a standardized API. This server allows AI models and other clients to interact with Ouster Lidar sensors through a set of well-defined tool functions.

## Features

- Connect to and disconnect from Ouster Lidar sensors
- Get detailed sensor information
- Capture Lidar scans
- Configure sensor parameters
- Support for multiple simultaneous sensor connections
- Run directly from GitHub using `uvx` without local cloning

## Requirements

- Python 3.11 or higher
- Ouster SDK 0.14.0 or higher (installed automatically when using `uvx`)
- MCP library 1.7.1 or higher (installed automatically when using `uvx`)
- uv package manager (which includes `uvx`)

## Installation

1. Clone this repository
2. Create and activate a virtual environment:

```bash
# Create virtual environment
uv venv
# Activate it
source .venv/bin/activate  # On Unix/macOS
.venv\Scripts\activate     # On Windows
```

3. Install dependencies:

```bash
# Basic installation
uv pip install -e .

# With development dependencies (for running tests)
uv pip install -e ".[dev]"
```

## Usage

### Starting the server

The server can be run in several ways:

#### Option 1: Direct run with `uvx` (recommended, no local clone required)

Run directly from GitHub using `uvx`:

```bash
# Start with default settings (stdio transport)
uvx --from git+https://github.com/jmdaly/ouster-lidar-mcp-server.git -m main

# Enable debug logging
uvx --from git+https://github.com/jmdaly/ouster-lidar-mcp-server.git -m main --debug

# Run with SSE transport (localhost:8080)
uvx --from git+https://github.com/jmdaly/ouster-lidar-mcp-server.git -m main --sse

# Specify host and port for SSE
uvx --from git+https://github.com/jmdaly/ouster-lidar-mcp-server.git -m main --sse --host 0.0.0.0 --port 9000
```

#### Option 2: From a local clone

If you have cloned the repository:

##### 1. Standard I/O (stdio) transport:

```bash
# Start with default settings
python main.py

# Enable debug logging
python main.py --debug
```

##### 2. Server-Sent Events (SSE) transport over HTTP:

```bash
# Start with default settings (localhost:8080)
python main.py --sse

# Specify host and port
python main.py --sse --host 0.0.0.0 --port 9000

# Enable debug logging
python main.py --sse --debug
```

#### Option 3: As an installed package

If you've installed the package:

```bash
# Start with default settings
ouster-mcp-server

# Enable debug logging
ouster-mcp-server --debug

# Run with SSE transport
ouster-mcp-server --sse
```

### Testing the server

A test client is provided to verify server functionality:

#### For stdio transport:

```bash
python test_client.py --server-script main.py --sensor your-sensor-hostname
```

#### For SSE transport:

```bash
# Start the server in one terminal
python main.py --sse

# Run the test client in another terminal
python test_client.py --server-url http://localhost:8080 --sensor your-sensor-hostname
```

### Using with MCP clients like Claude

1. Start the server using one of the methods above (direct `uvx`, stdio, or SSE transport)
2. Connect to the server using Claude Desktop or any other MCP-compatible client
3. Use the provided tools to interact with Ouster Lidar sensors

For the fastest setup with Claude Desktop:
```bash
# This runs the server directly from GitHub - no local clone needed
uvx --from git+https://github.com/jmdaly/ouster-lidar-mcp-server.git -m main --sse
```

Then connect Claude Desktop to `http://localhost:8080`

## Available Tools

The server provides the following tool functions:

1. `connect_sensor` - Connect to an Ouster Lidar sensor
2. `disconnect_sensor` - Disconnect from an Ouster Lidar sensor
3. `get_sensor_info` - Get detailed information about a connected sensor
4. `get_connected_sensors` - List all connected sensors
5. `capture_single_scan` - Capture a single scan from a connected sensor
6. `set_sensor_config` - Configure sensor parameters

## Example Usage in Claude

Here's an example of how to use the tools in Claude:

```
> tool ouster_lidar.connect_sensor
{
  "hostname": "os-122200123456.local"
}

Response:
{
  "status": "connected",
  "sensor_info": {
    "hostname": "os-122200123456.local",
    "serial": "122200123456",
    "model": "OS-1-64",
    "firmware_version": "v2.4.0"
  }
}

> tool ouster_lidar.capture_single_scan
{
  "hostname": "os-122200123456.local"
}

Response:
{
  "status": "success",
  "scan_summary": {
    "frame_id": 42,
    "scan_shape": {
      "h": 64,
      "w": 1024
    },
    "range_stats": {
      "min": 0.0,
      "max": 85.23,
      "mean": 12.45
    },
    "signal_stats": {
      "min": 0.0,
      "max": 255.0,
      "mean": 45.78
    },
    "reflectivity_stats": {
      "min": 0.0,
      "max": 255.0,
      "mean": 35.62
    },
    "num_valid_returns": 45678
  }
}
```

## Development

### Project Structure

- `main.py` - The core server implementation
- `test_client.py` - Client for testing server functionality
- `tests/` - Unit tests for the server and client
- `README.md` - Documentation

### Adding new tools

To add a new tool function:

1. Implement the async function using the `@mcp.tool()` decorator
2. Ensure type hints are provided for parameters and return types
3. Add comprehensive docstrings to describe functionality

Example:

```python
@mcp.tool()
async def my_new_tool(param1: str, param2: int) -> Dict[str, Any]:
    """
    Description of what the tool does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Dictionary with results
    """
    # Implementation
    return {"result": "success"}
```

### Running Tests

The project includes comprehensive unit tests for both the server and client functionality:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_server.py

# Run with verbose output
pytest -v

# Run with code coverage report
pytest --cov=.
```

### Further enhancements

Some potential enhancements for future development:

- Add support for recording/replaying Lidar data
- Implement point cloud visualization functions
- Add support for multi-sensor calibration and registration
- Implement advanced point cloud processing algorithms

## License

[MIT License](LICENSE)
