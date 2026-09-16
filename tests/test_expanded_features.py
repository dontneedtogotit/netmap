"""
test_expanded_features.py - Automated tests for NetMap expanded capabilities:
Wake-on-LAN, tvpc sync, RTSP test, Bufferbloat benchmark, Wi-Fi spectrum survey,
and Waybar desktop integration.
"""

import unittest
import json
import socket
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from netmap.hardware import add_tvpc_camera, load_tvpc_cameras, test_rtsp_stream
from netmap.tracer import send_wake_on_lan, run_bufferbloat_test, get_wifi_spectrum_survey
from netmap.server import NetMapHandler, STATE, ThreadedHTTPServer
import urllib.request

class TestHardwareAndTvpc(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conf_path = Path(self.temp_dir.name) / "cameras.conf"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_tvpc_camera(self):
        # Add first camera
        res1 = add_tvpc_camera("Driveway", "rtsp://admin:pass@192.168.0.136:554/ch0", group="Perimeter", conf_file=str(self.conf_path))
        self.assertTrue(res1["success"])
        self.assertEqual(res1["action"], "added")

        # Verify it can be loaded
        cams = load_tvpc_cameras(conf_file=str(self.conf_path))
        self.assertEqual(len(cams), 1)
        self.assertEqual(cams[0]["name"], "Driveway")

        # Update existing camera
        res2 = add_tvpc_camera("Driveway", "rtsp://admin:pass@192.168.0.136:554/ch1", group="Perimeter", conf_file=str(self.conf_path))
        self.assertTrue(res2["success"])
        self.assertEqual(res2["action"], "updated")

        # Add second camera
        res3 = add_tvpc_camera("Loft Cam", "rtsp://admin:pass@192.168.0.137:554/ch0", group="Indoor", conf_file=str(self.conf_path))
        self.assertTrue(res3["success"])
        self.assertEqual(res3["action"], "added")

        cams_after = load_tvpc_cameras(conf_file=str(self.conf_path))
        self.assertEqual(len(cams_after), 2)

    def test_test_rtsp_stream(self):
        # Test invalid host / port
        res = test_rtsp_stream("127.0.0.1", port=59999, timeout=0.1)
        self.assertFalse(res["success"])
        self.assertIn("error", res)

class TestTracerAndDiagnostics(unittest.TestCase):
    def test_send_wake_on_lan_invalid_mac(self):
        res = send_wake_on_lan("invalid_mac")
        self.assertFalse(res["success"])
        self.assertIn("Invalid MAC", res["error"])

    def test_send_wake_on_lan_valid_mac(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value.__enter__.return_value = mock_sock

            mac = "B8:FB:B3:01:02:03"
            res = send_wake_on_lan(mac)
            self.assertTrue(res["success"])
            self.assertEqual(res["bytes_sent"], 102)
            mock_sock.setsockopt.assert_called_once()
            mock_sock.sendto.assert_called_once()

    def test_run_bufferbloat_test(self):
        with patch("netmap.tracer.ping_host") as mock_ping:
            # First call idle, second call loaded
            mock_ping.side_effect = [
                {"reachable": True, "avg": 10.0},
                {"reachable": True, "avg": 14.0}
            ]
            res = run_bufferbloat_test("1.1.1.1", count=2)
            self.assertIn("grade", res)
            self.assertEqual(res["idle_ping_ms"], 10.0)
            self.assertEqual(res["loaded_ping_ms"], 14.0)
            self.assertEqual(res["delta_ms"], 4.0)
            self.assertEqual(res["grade"], "A+")

    def test_get_wifi_spectrum_survey(self):
        survey = get_wifi_spectrum_survey()
        self.assertIn("bands", survey)
        self.assertIn("2.4GHz", survey["bands"])
        self.assertIn("5GHz", survey["bands"])
        self.assertIn("6GHz", survey["bands"])
        self.assertGreater(survey["total_aps"], 0)

class TestServerExpandedAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 8925
        cls.server = ThreadedHTTPServer(('127.0.0.1', cls.port), NetMapHandler)
        import threading
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_api_spectrum(self):
        url = f"http://127.0.0.1:{self.port}/api/diagnostics/spectrum"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            self.assertIn("bands", data)
            self.assertIn("5GHz", data["bands"])

    def test_api_wol(self):
        url = f"http://127.0.0.1:{self.port}/api/devices/wol"
        payload = json.dumps({"mac": "B8:FB:B3:01:02:03"}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("success"))

    def test_api_camera_test(self):
        url = f"http://127.0.0.1:{self.port}/api/camera/test"
        payload = json.dumps({"host": "127.0.0.1", "port": 59998}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            self.assertFalse(data.get("success"))

    def test_api_camera_add_tvpc(self):
        url = f"http://127.0.0.1:{self.port}/api/camera/add-tvpc"
        payload = json.dumps({
            "name": "Front Door",
            "url": "rtsp://admin:admin@192.168.0.138:554/stream",
            "group": "Perimeter"
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("name"), "Front Door")

    def test_api_bufferbloat(self):
        url = f"http://127.0.0.1:{self.port}/api/diagnostics/bufferbloat"
        payload = json.dumps({"target": "1.1.1.1"}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            self.assertIn("grade", data)
            self.assertIn("delta_ms", data)

    def test_api_execute_action_new_tools(self):
        url = f"http://127.0.0.1:{self.port}/api/agent/execute-action"
        
        # Test tool_wake_on_lan
        payload = json.dumps({
            "type": "tool_wake_on_lan",
            "params": {"mac": "B8:FB:B3:01:02:03"}
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("success"))
            self.assertTrue(data.get("result", {}).get("success"))

        # Test tool_wifi_spectrum
        payload2 = json.dumps({
            "type": "tool_wifi_spectrum",
            "params": {}
        }).encode()
        req2 = urllib.request.Request(url, data=payload2, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req2, timeout=10) as resp:
            data2 = json.loads(resp.read().decode())
            self.assertTrue(data2.get("success"))
            self.assertIn("bands", data2.get("result", {}))

if __name__ == "__main__":
    unittest.main()
