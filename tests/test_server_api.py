"""
test_server_api.py - Integration tests for NetMap server REST endpoints.
"""

import unittest
import threading
import time
import urllib.request
import json

from netmap.server import ThreadedHTTPServer, NetMapHandler, STATE
from netmap.scanner import perform_full_network_scan

class TestServerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 8799
        cls.server = ThreadedHTTPServer(("127.0.0.1", cls.port), NetMapHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        # Initialize a sample topology
        STATE.update_topology({
            "wan": {"isp": "Aussie Broadband", "cgnat_active": True},
            "host": {"ip": "192.168.0.5", "gateway": "192.168.0.1", "mac": "B8:FB:B3:01:02:03"},
            "router": {"name": "Archer BE550 v2"},
            "router_settings": {"hardware": {"model_name": "Archer BE550 v2"}},
            "devices": [
                {"ip": "192.168.0.5", "mac": "B8:FB:B3:01:02:03", "name": "Workstation", "category": "host"},
                {"ip": "192.168.0.1", "mac": "B8:FB:B3:01:02:03", "name": "Archer BE550 v2", "category": "router", "model": "Archer BE550 v2"},
                {"ip": "192.168.0.136", "mac": "28:57:BE:11:22:33", "name": "Cam 1", "category": "camera"}
            ],
            "links": [
                {"source": "192.168.0.1", "target": "192.168.0.136", "type": "wired", "cable": "Cat 6"},
                {"source": "192.168.0.1", "target": "192.168.0.5", "type": "wired", "cable": "Cat 6"}
            ]
        })
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode("utf-8"))

    def _post(self, path, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode("utf-8"))

    def test_get_config(self):
        cfg = self._get("/api/config")
        self.assertIn("ai_provider", cfg)
        self.assertIn("mistral_model", cfg)
        self.assertIn("openrouter_model", cfg)

    def test_get_models(self):
        models = self._get("/api/models")
        self.assertIn("mistral", models)
        self.assertIn("openrouter", models)
        self.assertTrue(len(models["mistral"]) >= 4)
        self.assertTrue(len(models["openrouter"]) >= 4)

    def test_post_config(self):
        res = self._post("/api/config", {
            "ai_provider": "mistral",
            "mistral_model": "mistral-large-latest"
        })
        self.assertTrue(res.get("success"))
        cfg = self._get("/api/config")
        self.assertEqual(cfg["ai_provider"], "mistral")
        self.assertEqual(cfg["mistral_model"], "mistral-large-latest")

    def test_get_suggestions(self):
        sugs = self._get("/api/suggestions")
        self.assertIn("suggestions", sugs)
        self.assertGreater(len(sugs["suggestions"]), 0)

    def test_post_solve_returns_exact_mapping_for_cat6_question(self):
        payload = {
            "goal": "Which port does the cat 6 go to for my camera?",
            "agent": "orchestrator"
        }
        ans = self._post("/api/solve", payload)
        mapping = ans.get("exact_mapping") or {}
        self.assertEqual(mapping.get("cable"), "Cat 6")
        self.assertEqual(mapping.get("confidence"), "high")
        self.assertEqual(mapping["source"]["port"], "LAN1")
        self.assertEqual(mapping["target"]["ip"], "192.168.0.136")
        self.assertEqual(mapping["target"]["port"], "ETH1")

    def test_devices_settings_crud(self):
        # 1. Get presets
        dev_info = self._get("/api/devices/settings")
        self.assertIn("presets", dev_info)
        self.assertIn("roles", dev_info["presets"])

        # 2. Save custom device settings
        save_res = self._post("/api/devices/settings", {
            "identifier": "B8:FB:B3:01:02:03",
            "settings": {
                "alias": "Omarchy Master Rig",
                "role": "Gaming Rig / Console",
                "location": "Home Office / Desk",
                "priority": "High (QoS Low Latency)",
                "custom_fields": {
                    "gpu": "RTX 4090",
                    "monitors": "3"
                }
            }
        })
        self.assertTrue(save_res.get("success"))
        self.assertEqual(save_res["settings"]["alias"], "Omarchy Master Rig")

        # Verify reflected in topology
        status = self._get("/api/status")
        host_dev = next((d for d in status["topology"]["devices"] if d["ip"] == "192.168.0.5"), None)
        self.assertIsNotNone(host_dev)
        self.assertEqual(host_dev["name"], "Omarchy Master Rig")
        self.assertEqual(host_dev["user_settings"]["custom_fields"]["gpu"], "RTX 4090")

    def test_post_solve_returns_visual_diagram_and_text(self):
        res = self._post("/api/solve", {"goal": "How do I isolate my cameras on Archer BE550?"})
        self.assertIn("visual_diagram", res)
        self.assertIn("mermaid", res)
        self.assertIn("steps", res)
        self.assertIn("summary", res)
        self.assertIn("warnings", res)

if __name__ == "__main__":
    unittest.main()
