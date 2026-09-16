"""
test_features.py - Unit tests for Mistral API integration, network suggestions,
per-device custom settings store, and visual diagram formatting.
"""

import unittest
import json
import os
import tempfile
from pathlib import Path

from netmap.device_store import (
    load_device_settings,
    save_device_settings,
    get_settings_for_device,
    update_settings_for_device,
    DEVICE_SETTINGS_FILE
)
from netmap.suggestions import generate_network_suggestions
from netmap.advisor import (
    NetworkAdvisor,
    extract_json_from_text,
    RECOMMENDED_MISTRAL_MODELS,
    RECOMMENDED_FREE_MODELS
)

class TestDeviceStore(unittest.TestCase):
    def setUp(self):
        # Backup original settings if any
        self.original_exists = DEVICE_SETTINGS_FILE.exists()
        self.original_content = None
        if self.original_exists:
            with open(DEVICE_SETTINGS_FILE, "r") as f:
                self.original_content = f.read()

    def tearDown(self):
        # Restore original
        if self.original_exists and self.original_content:
            with open(DEVICE_SETTINGS_FILE, "w") as f:
                f.write(self.original_content)

    def test_save_and_retrieve_device_settings(self):
        mac = "00:11:22:33:44:55"
        data = {
            "alias": "Living Room 4K TV",
            "role": "Smart TV / Streaming Player",
            "location": "Living Room",
            "priority": "High (QoS Low Latency)",
            "network_segment": "Main LAN (Wi-Fi 7 / 5GHz)",
            "ip_reservation": "Reserved: 192.168.0.153",
            "notes": "Chromecast Ultra built-in",
            "custom_fields": {
                "hdr_support": "Dolby Vision",
                "max_resolution": "4K 120Hz"
            }
        }
        updated = update_settings_for_device(mac, data)
        self.assertEqual(updated["alias"], "Living Room 4K TV")
        self.assertEqual(updated["custom_fields"]["hdr_support"], "Dolby Vision")

        # Retrieve by MAC
        retrieved = get_settings_for_device(mac=mac, ip="192.168.0.153")
        self.assertEqual(retrieved["alias"], "Living Room 4K TV")
        self.assertEqual(retrieved["role"], "Smart TV / Streaming Player")
        self.assertEqual(retrieved["custom_fields"]["max_resolution"], "4K 120Hz")

class TestNetworkSuggestions(unittest.TestCase):
    def test_generate_network_suggestions(self):
        dummy_topo = {
            "wan": {"cgnat_active": True, "isp": "Aussie Broadband"},
            "host": {
                "ip": "192.168.0.5",
                "mac": "B8:FB:B3:01:02:03",
                "wifi": {"frequency": "5180 MHz", "channel": "36"},
                "dns": ["192.168.0.1"]
            },
            "devices": [
                {
                    "ip": "192.168.0.136",
                    "category": "camera",
                    "name": "Driveway Cam",
                    "user_settings": {
                        "role": "CCTV Security Camera",
                        "priority": "Normal"
                    }
                },
                {
                    "ip": "192.168.0.76",
                    "category": "extender",
                    "model": "EX6250v2",
                    "name": "Netgear Extender"
                }
            ],
            "has_cameras": True,
            "router_settings": {}
        }
        suggestions = generate_network_suggestions(dummy_topo)
        self.assertGreater(len(suggestions), 0)
        
        # Verify CGNAT suggestion present
        cgnat_sug = next((s for s in suggestions if s["id"] == "sug-cgnat"), None)
        self.assertIsNotNone(cgnat_sug)
        self.assertEqual(cgnat_sug["priority"], "critical")
        self.assertIn("MyAussie", cgnat_sug["recommended_state"])

        # Verify IoT isolation suggestion present
        iot_sug = next((s for s in suggestions if s["id"] == "sug-iot-isolation"), None)
        self.assertIsNotNone(iot_sug)
        self.assertEqual(iot_sug["priority"], "critical")
        self.assertIn("BananaFarm-IoT", iot_sug["recommended_state"])

        # Verify Extender AP suggestion present
        ext_sug = next((s for s in suggestions if s["id"] == "sug-extender-ap"), None)
        self.assertIsNotNone(ext_sug)
        self.assertIn("Access Point", ext_sug["recommended_state"])

class TestAdvisorAndMistral(unittest.TestCase):
    def test_json_extractor_clean(self):
        raw = '{"category": "Test", "summary": "Looks good"}'
        parsed = extract_json_from_text(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["category"], "Test")

    def test_json_extractor_markdown_fence(self):
        raw = 'Here is the solution:\n```json\n{"category": "Camera", "steps": [{"step": 1}]}\n```\nHope this helps!'
        parsed = extract_json_from_text(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["category"], "Camera")
        self.assertEqual(len(parsed["steps"]), 1)

    def test_local_advisor_produces_visual_diagram_and_mermaid(self):
        advisor = NetworkAdvisor()
        dummy_topo = {
            "wan": {"isp": "Aussie Broadband", "cgnat_active": True},
            "host": {"ip": "192.168.0.5", "gateway": "192.168.0.1"},
            "devices": [
                {
                    "ip": "192.168.0.136",
                    "category": "camera",
                    "name": "Front Cam",
                    "user_settings": {"role": "CCTV Security Camera"}
                }
            ]
        }
        res = advisor.solve("How do I set up CCTV security cameras?", dummy_topo)
        self.assertIn("visual_diagram", res)
        self.assertIn("mermaid", res)
        self.assertIn("steps", res)
        self.assertEqual(res["visual_diagram"]["type"], "flowchart")
        self.assertGreater(len(res["visual_diagram"]["nodes"]), 0)
        self.assertTrue(res["mermaid"].startswith("graph"))

if __name__ == "__main__":
    unittest.main()
