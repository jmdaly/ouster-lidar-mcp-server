"""
Unit tests for the Ouster Lidar MCP server.

These tests verify the server's tool functions and proper MCP protocol handling.
"""

import asyncio
import argparse
import importlib
import logging
import subprocess
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock the ouster.sdk.client module before importing other modules
sys.modules['ouster'] = MagicMock()
sys.modules['ouster.sdk'] = MagicMock()
sys.modules['ouster.sdk.client'] = MagicMock()

# Now import server functions and setup to test
import main
import app_setup
import sensor_operations
import scan_operations
import visualization


class MockSensorInfo:
    """Mock for ouster.client.SensorInfo"""
    def __init__(self):
        self.sn = "TEST_SERIAL"
        self.prod_line = "TEST_MODEL"
        self.fw_rev = "TEST_FW"
        self.mode = "1024x10"
        self.azimuth_window = (0, 360)
        import numpy as np
        self.beam_altitude_angles = np.array([0.1, 0.2, 0.3])
        self.beam_azimuth_angles = np.array([0.1, 0.2, 0.3])
        self.lidar_origin_to_beam_origin_mm = 10.5
        
        class Format:
            def __init__(self):
                self.pixels_per_column = 64
                self.columns_per_frame = 1024
        
        self.format = Format()
        self.udp_port_lidar = 7502
        self.udp_port_imu = 7503


class MockSensor:
    """Mock for ouster.client.Sensor and ScanSource"""
    def __init__(self, hostname, udp_port_lidar, udp_port_imu):
        self.hostname = hostname
        self.udp_port_lidar = udp_port_lidar
        self.udp_port_imu = udp_port_imu
        self.metadata = MockSensorInfo()
        self.closed = False
        self.set_config = MagicMock(return_value=True)
        self._scan_data = []  # For iteration
    
    def close(self):
        self.closed = True
    
    def read(self):
        """Simulate reading a data packet"""
        import numpy as np
        # Return mock packet data (for testing)
        return np.zeros(10)
    
    def __iter__(self):
        """Make the MockSensor iterable like a ScanSource"""
        if self._scan_data:
            return iter(self._scan_data)
        else:
            # Return a single mock scan if no data is set
            return iter([MockLidarScan()])


class MockScanBatcher:
    """Mock for ouster.client.ScanBatcher"""
    def __init__(self, sensor_info):
        self.sensor_info = sensor_info
        self.packet_count = 0
    
    def batch(self, packet):
        """Simulate creating a scan from packets"""
        self.packet_count += 1
        
        # Return a scan after receiving 5 packets
        if self.packet_count >= 5:
            return MockLidarScan()
        return None


class MockLidarScan:
    """Mock for ouster.client.LidarScan"""
    def __init__(self):
        self.frame_id = 42
        self._fields = {
            "RANGE": MockScanField(64, 1024, 0.0, 85.0, 12.5),
            "SIGNAL": MockScanField(64, 1024, 0.0, 255.0, 45.0),
            "REFLECTIVITY": MockScanField(64, 1024, 0.0, 255.0, 35.0),
        }
        
        import numpy as np
        self.timestamp = np.array([1000, 2000, 3000])
        self.measurement_id = np.array([1, 2, 3])
        self.status = np.array([0, 0, 0])
    
    def field(self, chan_field):
        if isinstance(chan_field, str):
            field_name = chan_field
        elif hasattr(chan_field, 'name'):
            field_name = chan_field.name
        elif hasattr(chan_field, '_mock_name'):
            field_name = chan_field._mock_name
        else:
            field_name = str(chan_field)

        upper_name = field_name.upper() if hasattr(field_name, 'upper') else field_name
        # Support both full names and aliases like 'R', 'S', 'REF' used by mocks
        if upper_name in ["RANGE", "R"]:
            return self._fields["RANGE"]
        if upper_name in ["SIGNAL", "S"]:
            return self._fields["SIGNAL"]
        if upper_name in ["REFLECTIVITY", "REF"]:
            return self._fields["REFLECTIVITY"]
        raise ValueError(f"Unknown field: {chan_field} (resolved to {field_name})")


class MockScanField:
    def __init__(self, h, w, min_val, max_val, mean_val):
        self.shape = (h, w)
        self._min, self._max, self._mean = min_val, max_val, mean_val
        self._sum_gt_zero = h * w * 0.7
    
    def min(self): return self._min
    def max(self): return self._max
    def mean(self): return self._mean
    def __gt__(self, val):
        r = MagicMock(); r.sum.return_value = self._sum_gt_zero; r.any.return_value = True
        r.mean.return_value = self._mean; r.__getitem__ = lambda s, i: r; return r
    def __getitem__(self, i): r = MagicMock(); r.mean.return_value = self._mean; return r


class MockContext:
    def __init__(self):
        self.info, self.error, self.report_progress = AsyncMock(), AsyncMock(), AsyncMock()


@pytest.fixture
def mock_ouster_client(monkeypatch):
    mock_cli = MagicMock()
    mock_cli.Sensor = MagicMock(side_effect=MockSensor)
    mock_cli.ScanBatcher = MagicMock(side_effect=MockScanBatcher)
    mock_cli.SensorConfig = MagicMock(return_value=MagicMock())
    mock_cli.PacketSource = MagicMock()
    mock_cli.XYZLut = MagicMock()

    def mock_osf(hostname, *a, **k): return MockSensor(hostname, 7502, 7503)
    mock_osi = MagicMock(side_effect=mock_osf)

    class CFV: __init__ = lambda s, n: setattr(s, 'name', n); __str__ = lambda s: s.name
    class MCF: RANGE, SIGNAL, REFLECTIVITY, NEAR_IR = CFV("R"),CFV("S"),CFV("REF"),CFV("NIR")
    mock_cli.ChanField = MCF

    for mod in [sensor_operations, scan_operations]:
        monkeypatch.setattr(mod, "client", mock_cli)
        if hasattr(mod, "open_source"): monkeypatch.setattr(mod, "open_source", mock_osi)
        monkeypatch.setattr(mod, "ChanField", MCF)
    if hasattr(scan_operations, 'client') and hasattr(scan_operations.client, "XYZLut"): 
        monkeypatch.setattr(scan_operations.client, "XYZLut", mock_cli.XYZLut)
    
    mock_cli.open_source = mock_osi
    return mock_cli


@pytest.fixture
def setup_test_environment():
    orig_ss = app_setup.scan_sources.copy()
    orig_vp = app_setup.visualization_processes.copy()
    app_setup.scan_sources.clear(); app_setup.visualization_processes.clear()
    yield
    app_setup.scan_sources.clear(); app_setup.scan_sources.update(orig_ss)
    app_setup.visualization_processes.clear(); app_setup.visualization_processes.update(orig_vp)


# Create a global mock for psutil to be used by tests needing to mock its import
mock_psutil = MagicMock()

class TestServerTools:
    @pytest.mark.asyncio
    async def test_connect_sensor(self, mock_ouster_client, setup_test_environment):
        ctx = MockContext()
        res = await sensor_operations.connect_sensor("test-s", ctx)
        mock_ouster_client.open_source.assert_called_once_with("test-s")
        assert res["status"] == "connected" and res["sensor_info"]["hostname"] == "test-s"
        assert "test-s" in app_setup.scan_sources

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, mock_ouster_client, setup_test_environment):
        app_setup.scan_sources["test-s"] = MockSensor("test-s", 7502, 7503)
        ctx = MockContext()
        res = await sensor_operations.connect_sensor("test-s", ctx)
        assert res["status"] == "already_connected"

    @pytest.mark.asyncio
    async def test_connect_error(self, mock_ouster_client, setup_test_environment):
        mock_ouster_client.open_source.side_effect = Exception("Conn fail")
        ctx = MockContext()
        res = await sensor_operations.connect_sensor("test-s", ctx)
        assert res["status"] == "error" and "Conn fail" in res["error"]

    @pytest.mark.asyncio
    async def test_disconnect_sensor(self, setup_test_environment):
        s = MockSensor("test-s", 7502, 7503); app_setup.scan_sources["test-s"] = s
        ctx = MockContext()
        res = await sensor_operations.disconnect_sensor("test-s", ctx)
        assert res["status"] == "disconnected" and "test-s" not in app_setup.scan_sources and s.closed

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, setup_test_environment):
        ctx = MockContext()
        res = await sensor_operations.disconnect_sensor("nonex-s", ctx)
        assert res["status"] == "not_connected"

    @pytest.mark.asyncio
    async def test_get_sensor_info(self, setup_test_environment):
        app_setup.scan_sources["test-s"] = MockSensor("test-s", 7502, 7503)
        ctx = MockContext()
        res = await sensor_operations.get_sensor_info("test-s", ctx)
        assert res["status"] == "success" and res["sensor_info"]["serial"] == "TEST_SERIAL"

    @pytest.mark.asyncio
    async def test_get_sensor_info_not_connected(self, setup_test_environment):
        ctx = MockContext()
        res = await sensor_operations.get_sensor_info("nonex-s", ctx)
        assert res["status"] == "not_connected"

    @pytest.mark.asyncio
    async def test_get_connected_sensors(self, setup_test_environment):
        app_setup.scan_sources["s1"] = MockSensor("s1",7502,7503)
        app_setup.scan_sources["s2"] = MockSensor("s2",7502,7503)
        ctx = MockContext()
        res = await sensor_operations.get_connected_sensors(ctx)
        assert res["status"] == "success" and len(res["connected_sensors"]) == 2

    @pytest.mark.asyncio
    async def test_capture_single_scan(self, mock_ouster_client, setup_test_environment):
        app_setup.scan_sources["test-s"] = MockSensor("test-s", 7502, 7503)
        ctx = MockContext(); orig_cf = scan_operations.ChanField
        scan_operations.ChanField = mock_ouster_client.ChanField
        try:
            res = await scan_operations.capture_single_scan("test-s", ctx)
        finally:
            scan_operations.ChanField = orig_cf
        assert res["status"] == "success" and res["scan_summary"]["frame_id"] == 42

    @pytest.mark.asyncio
    async def test_capture_scan_not_connected(self, setup_test_environment):
        ctx = MockContext()
        res = await scan_operations.capture_single_scan("nonex-s", ctx)
        assert res["status"] == "not_connected"

    @pytest.mark.asyncio
    async def test_process_point_cloud(self, mock_ouster_client, setup_test_environment):
        app_setup.scan_sources["test-s"] = MockSensor("test-s", 7502, 7503)
        ctx = MockContext()
        assert scan_operations.client.XYZLut is mock_ouster_client.XYZLut
        res = await scan_operations.process_point_cloud("test-s", ctx, 50.0)
        assert res["status"] in ["success", "warning"]

    @pytest.mark.asyncio
    async def test_get_scan(self, mock_ouster_client, setup_test_environment):
        s = MockSensor("test-s",7502,7503); s._scan_data=[MockLidarScan()]
        app_setup.scan_sources["test-s"] = s; ctx = MockContext()
        res = await scan_operations.get_scan("test-s", ctx)
        assert res["status"] == "success" and res["scan_data"]["frame_id"] == 42

    @pytest.mark.asyncio
    async def test_get_scan_not_connected(self, setup_test_environment):
        ctx = MockContext()
        res = await scan_operations.get_scan("nonex-s", ctx)
        assert res["status"] == "not_connected"

    @pytest.mark.asyncio
    async def test_stream_scans(self, mock_ouster_client, setup_test_environment):
        s = MockSensor("test-s",7502,7503); s._scan_data=[MockLidarScan() for _ in range(3)]
        app_setup.scan_sources["test-s"] = s; ctx = MockContext()
        res = await scan_operations.stream_scans("test-s", 3, ctx)
        assert res["status"] == "success" and res["scans_captured"] == 3

    @pytest.mark.asyncio
    async def test_stream_scans_not_connected(self, setup_test_environment):
        ctx = MockContext()
        res = await scan_operations.stream_scans("nonex-s", 5, ctx)
        assert res["status"] == "not_connected"

    @pytest.mark.asyncio
    @patch("sensor_operations.subprocess.Popen")
    async def test_discover_sensors_success(self, mock_popen, setup_test_environment):
        mp = MagicMock(); mp.returncode=0; mp.communicate.return_value=('[{"hostname":"s.l"}]',"")
        mock_popen.return_value=mp; ctx=MockContext()
        res = await sensor_operations.discover_sensors(ctx)
        assert res["status"] == "success" and len(res["sensors"]) == 1

    @pytest.mark.asyncio
    @patch("sensor_operations.subprocess.Popen")
    async def test_discover_sensors_no_sensors(self, mock_popen, setup_test_environment):
        mp = MagicMock(); mp.returncode=0; mp.communicate.return_value=("[]","")
        mock_popen.return_value=mp; ctx=MockContext()
        res = await sensor_operations.discover_sensors(ctx)
        assert res["status"] == "success" and len(res["sensors"]) == 0

    @pytest.mark.asyncio
    @patch("sensor_operations.subprocess.Popen")
    async def test_discover_sensors_command_error(self, mock_popen, setup_test_environment):
        mp = MagicMock(); mp.returncode=1; mp.communicate.return_value=("","Cmd fail")
        mock_popen.return_value=mp; ctx=MockContext()
        res = await sensor_operations.discover_sensors(ctx)
        assert res["status"] == "error"

    @pytest.mark.asyncio
    @patch("sensor_operations.subprocess.Popen")
    async def test_discover_sensors_parse_text_output(self, mock_popen, setup_test_environment):
        mp=MagicMock(); mp.returncode=0; mp.communicate.return_value=("S: h\nI: ip","")
        mock_popen.return_value=mp; ctx=MockContext()
        res = await sensor_operations.discover_sensors(ctx)
        assert res["status"] == "success" and len(res["sensors"])==1

    @pytest.mark.asyncio
    @patch("sensor_operations.subprocess.Popen")
    async def test_discover_sensors_already_connected(self, mock_popen, setup_test_environment):
        app_setup.scan_sources["s.l"] = MockSensor("s.l",7502,7503)
        mp=MagicMock(); mp.returncode=0; mp.communicate.return_value=('[{"hostname":"s.l"}]',"")
        mock_popen.return_value=mp; ctx=MockContext()
        res = await sensor_operations.discover_sensors(ctx)
        assert res["sensors"][0]["connection_status"] == "connected"

    @pytest.mark.asyncio
    @patch("sensor_operations.subprocess.Popen")
    async def test_discover_sensors_timeout(self, mock_popen, setup_test_environment):
        mp=MagicMock(); mp.communicate.side_effect = subprocess.TimeoutExpired("c",10)
        mock_popen.return_value=mp; ctx=MockContext()
        res = await sensor_operations.discover_sensors(ctx)
        assert res["status"] == "error" and "timed out" in res["error"].lower()
        
    @pytest.mark.asyncio
    @patch("visualization.subprocess.Popen")
    @patch("visualization.time.time")
    async def test_start_visualization_success(self, mock_time, mock_popen, setup_test_environment):
        app_setup.scan_sources["test-s"]=MockSensor("test-s",7502,7503); mock_time.return_value=1000.0
        mp=MagicMock(pid=123); mp.poll.return_value=None; mock_popen.return_value=mp
        ctx=MockContext(); res=await visualization.start_visualization("test-s",ctx)
        assert res["status"]=="success" and res["pid"]==123 and "test-s" in app_setup.visualization_processes

    @pytest.mark.asyncio
    @patch("visualization.subprocess.Popen")
    async def test_start_visualization_not_connected(self, mock_popen, setup_test_environment):
        ctx=MockContext(); res=await visualization.start_visualization("nonex-s",ctx)
        assert res["status"]=="not_connected" and not mock_popen.called

    @pytest.mark.asyncio
    @patch("visualization.subprocess.Popen")
    async def test_start_visualization_already_running(self, mock_popen, setup_test_environment):
        app_setup.scan_sources["test-s"]=MockSensor("test-s",7502,7503)
        app_setup.visualization_processes["test-s"]=999
        ctx=MockContext()
        global mock_psutil
        mock_psutil.pid_exists.return_value = True
        with patch.dict(sys.modules, {'psutil': mock_psutil}):
            importlib.reload(visualization)
            res=await visualization.start_visualization("test-s",ctx)
        assert res["status"]=="already_running" and not mock_popen.called

    @pytest.mark.asyncio
    @patch("visualization.subprocess.Popen")
    async def test_start_visualization_previous_process_dead(self, mock_popen, setup_test_environment):
        app_setup.scan_sources["test-s"]=MockSensor("test-s",7502,7503)
        app_setup.visualization_processes["test-s"]=999
        mp=MagicMock(pid=123); mp.poll.return_value=None; mock_popen.return_value=mp
        ctx=MockContext()
        global mock_psutil
        mock_psutil.pid_exists.return_value = False
        with patch.dict(sys.modules, {'psutil': mock_psutil}):
            importlib.reload(visualization)
            res=await visualization.start_visualization("test-s",ctx)
        assert res["status"]=="success" and res["pid"]==123

    @pytest.mark.asyncio
    @patch("visualization.subprocess.Popen")
    async def test_start_visualization_process_fails(self, mock_popen, setup_test_environment):
        app_setup.scan_sources["test-s"]=MockSensor("test-s",7502,7503)
        mp=MagicMock(); mp.poll.return_value=1; mp.communicate.return_value=(b"",b"Fail")
        mock_popen.return_value=mp; ctx=MockContext()
        res=await visualization.start_visualization("test-s",ctx)
        assert res["status"]=="error"

    @pytest.mark.asyncio
    @patch("visualization.os.kill")
    async def test_stop_visualization_success(self, mock_os_kill, setup_test_environment):
        app_setup.visualization_processes["test-s"]=123
        ctx=MockContext()
        global mock_psutil
        mock_psutil.pid_exists.return_value=True
        mp = MagicMock(); mp.children.return_value=[]
        mock_psutil.Process.return_value = mp
        mock_psutil.wait_procs.return_value=([],[]) # terminated, alive
        with patch.dict(sys.modules, {'psutil': mock_psutil}):
            importlib.reload(visualization)
            res=await visualization.stop_visualization("test-s",ctx)
        assert res["status"]=="success" and "test-s" not in app_setup.visualization_processes and mp.terminate.called

    @pytest.mark.asyncio
    async def test_stop_visualization_not_running(self, setup_test_environment):
        ctx=MockContext(); res=await visualization.stop_visualization("nonex-s",ctx)
        assert res["status"]=="not_running"

    @pytest.mark.asyncio
    async def test_stop_visualization_process_not_exists(self, setup_test_environment):
        app_setup.visualization_processes["test-s"]=123
        ctx=MockContext()
        global mock_psutil
        mock_psutil.pid_exists.return_value=False
        with patch.dict(sys.modules, {'psutil': mock_psutil}):
            importlib.reload(visualization)
            res=await visualization.stop_visualization("test-s",ctx)
        assert res["status"]=="not_running"

    @pytest.mark.asyncio
    @patch("visualization.time.time")
    async def test_list_visualizations_with_psutil(self, mock_time, setup_test_environment):
        mock_time.return_value=1000.0; app_setup.visualization_processes = {"s1":1,"s2":2,"s3":3}
        p1=MagicMock(cpu_percent=lambda interval:10, memory_percent=lambda:5, status=lambda:"run", create_time=lambda:900.0)
        p2=MagicMock(cpu_percent=lambda interval:20, memory_percent=lambda:15, status=lambda:"sleep", create_time=lambda:950.0)
        global mock_psutil
        mock_psutil.pid_exists.side_effect = lambda pid: pid != 3
        mock_psutil.Process.side_effect = lambda pid: {1:p1, 2:p2}.get(pid) or (_ for _ in ()).throw(mock_psutil.NoSuchProcess(pid))
        mock_psutil.NoSuchProcess = type('NoSuchProcess', (Exception,), {})
        ctx=MockContext()
        with patch.dict(sys.modules, {'psutil': mock_psutil}):
            importlib.reload(visualization)
            res=await visualization.list_visualizations(ctx)
        assert res["status"]=="success" and res["total_count"]==2 and "s3" not in app_setup.visualization_processes

    @pytest.mark.asyncio
    async def test_list_visualizations_without_psutil(self, setup_test_environment):
        app_setup.visualization_processes["s1"]=1; ctx=MockContext()
        orig_import = __builtins__['__import__']
        def imp_se(name, *a, **k): 
            if name=="psutil": raise ImportError("No module named psutil")
            return orig_import(name, *a, **k)
        with patch("builtins.__import__", side_effect=imp_se):
            if 'psutil' in sys.modules: del sys.modules['psutil']
            importlib.reload(visualization)
            res=await visualization.list_visualizations(ctx)
        assert res["status"]=="success" and res["visualizations"][0]["status"]=="unknown"

class TestMcpServer:
    @pytest.mark.skip(reason="Tools are registered in actual app, this is difficult to test due to module mocking")
    def test_mcp_server_initialization(self):
        assert app_setup.mcp.name == "ouster_lidar"
        tool_names = ["connect_sensor", "disconnect_sensor", "get_sensor_info", "get_connected_sensors", 
                      "discover_sensors", "capture_single_scan", "get_scan", "stream_scans", 
                      "process_point_cloud", "start_visualization", "stop_visualization", "list_visualizations"]
        registered_tools = getattr(app_setup.mcp, '_tools', getattr(app_setup.mcp, 'tools', {}))
        for tn in tool_names:
            assert tn in registered_tools, f"Tool {tn} not registered"

    @patch("app_setup.mcp.run")
    def test_main_with_stdio_transport(self, mock_run_mcp):
        with (
            patch("sys.argv", ["main.py"]),
            patch("argparse.ArgumentParser.parse_args", return_value=argparse.Namespace(debug=False, sse=False, host=None, port=None))
        ):
            main.main()
            mock_run_mcp.assert_called_once_with()

    @patch("app_setup.mcp.run")
    def test_main_with_sse_transport(self, mock_run_mcp):
        test_args = argparse.Namespace(sse=True, host="127.0.0.1", port=9000, debug=False)
        with (
            patch("sys.argv", ["main.py", "--sse", "--host", "127.0.0.1", "--port", "9000"]),
            patch("argparse.ArgumentParser.parse_args", return_value=test_args)
        ):
            main.main()
            assert os.environ["MCP_SSE_HOST"] == "127.0.0.1"
            assert os.environ["MCP_SSE_PORT"] == "9000"
            mock_run_mcp.assert_called_once_with(transport="sse")

    def test_debug_logging(self):
        mock_args = argparse.Namespace(debug=True, sse=False, host=None, port=None)
        orig_level = logging.getLogger().level
        try:
            logging.getLogger().setLevel(logging.INFO)
            with patch("argparse.ArgumentParser.parse_args", return_value=mock_args), \
                 patch("app_setup.mcp.run"):
                main.main()
                assert logging.getLogger().level == logging.DEBUG
        finally: logging.getLogger().setLevel(orig_level)
