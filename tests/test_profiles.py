"""
test_profiles.py - Tests for Multi-Profile Network Mapping per Wi-Fi Access Point.
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch

import netmap.profile_manager as pm
from netmap.device_store import load_device_settings, update_settings_for_device, get_settings_for_device
from netmap.server import ThreadedHTTPServer, NetMapHandler, STATE
import urllib.request
import threading
import time

class TestProfileManager(unittest.TestCase):
    def setUp(self):
        # Use temporary directory for profiles
        self.temp_dir = tempfile.mkdtemp()
        self.orig_profiles_dir = pm.PROFILES_DIR
        pm.PROFILES_DIR = Path(self.temp_dir)

    def tearDown(self):
        pm.PROFILES_DIR = self.orig_profiles_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_profile_id_generation(self):
        host_wifi_1 = {
            "wifi": {
                "ssid": "BananaFarm",
                "bssid": "B8:FB:B3:80:57:EF"
            },
            "gateway": "192.168.0.1"
        }
        id1 = pm.get_profile_id_for_host(host_wifi_1)
        self.assertIn("bananafarm", id1)
        self.assertIn("b8fbb38057ef", id1)

        host_wifi_2 = {
            "wifi": {
                "ssid": "CommBankFreeWiFi",
                "bssid": "0A:8D:DB:6E:4F:57"
            },
            "gateway": "10.128.128.128"
        }
        id2 = pm.get_profile_id_for_host(host_wifi_2)
        self.assertIn("commbankfreewifi", id2)
        self.assertIn("0a8ddb6e4f57", id2)
        self.assertNotEqual(id1, id2)

        host_eth = {
            "wifi": {},
            "gateway": "192.168.1.1",
            "gateway_mac": "00:50:56:C0:00:08"
        }
        id3 = pm.get_profile_id_for_host(host_eth)
        self.assertTrue(id3.startswith("eth_"))
        self.assertNotEqual(id1, id3)

    def test_create_and_switch_profiles_on_different_wifi(self):
        # 1. Connect to Wi-Fi 1 (Home)
        host_home = {
            "ip": "192.168.0.5",
            "gateway": "192.168.0.1",
            "wifi": {"ssid": "BananaFarm", "bssid": "B8:FB:B3:80:57:EF"}
        }
        p1, is_new1 = pm.get_or_create_profile_for_host(host_home)
        self.assertTrue(is_new1)
        self.assertEqual(p1["ssid"], "BananaFarm")
        self.assertEqual(p1["name"], "BananaFarm")

        # Re-checking same AP returns existing profile
        p1_again, is_new1_again = pm.get_or_create_profile_for_host(host_home)
        self.assertFalse(is_new1_again)
        self.assertEqual(p1["id"], p1_again["id"])

        # 2. Connect to Wi-Fi 2 (Different Access Point / Coffee Shop)
        host_work = {
            "ip": "10.54.33.234",
            "gateway": "10.128.128.128",
            "wifi": {"ssid": "CommBankFreeWiFi", "bssid": "0A:8D:DB:6E:4F:57"}
        }
        p2, is_new2 = pm.get_or_create_profile_for_host(host_work)
        self.assertTrue(is_new2)
        self.assertEqual(p2["ssid"], "CommBankFreeWiFi")
        self.assertEqual(p2["name"], "CommBankFreeWiFi")
        self.assertNotEqual(p1["id"], p2["id"])

        # Listing profiles returns both profiles
        profiles = pm.list_profiles(active_id=p2["id"])
        self.assertEqual(len(profiles), 2)
        p2_meta = next(p for p in profiles if p["id"] == p2["id"])
        self.assertTrue(p2_meta["is_active"])

    def test_per_profile_device_settings_isolation(self):
        # Setup two profiles
        p1, _ = pm.get_or_create_profile_for_host({
            "ip": "192.168.0.5",
            "gateway": "192.168.0.1",
            "wifi": {"ssid": "Network-A", "bssid": "AA:BB:CC:11:22:33"}
        })
        p2, _ = pm.get_or_create_profile_for_host({
            "ip": "10.0.0.5",
            "gateway": "10.0.0.1",
            "wifi": {"ssid": "Network-B", "bssid": "AA:BB:CC:44:55:66"}
        })

        dev_mac = "12:34:56:78:9A:BC"

        # Update device in Profile 1
        pm.update_profile_device_settings(p1["id"], dev_mac, {
            "alias": "Living Room Cam",
            "role": "CCTV Security Camera"
        })

        # Update device with same MAC in Profile 2
        pm.update_profile_device_settings(p2["id"], dev_mac, {
            "alias": "Office Workstation",
            "role": "Primary Workstation / PC"
        })

        # Verify settings are isolated per profile
        s1 = pm.get_profile_device_settings(p1["id"])
        s2 = pm.get_profile_device_settings(p2["id"])

        self.assertEqual(s1[dev_mac]["alias"], "Living Room Cam")
        self.assertEqual(s1[dev_mac]["role"], "CCTV Security Camera")

        self.assertEqual(s2[dev_mac]["alias"], "Office Workstation")
        self.assertEqual(s2[dev_mac]["role"], "Primary Workstation / PC")

    def test_rename_and_delete_profile(self):
        p, _ = pm.get_or_create_profile_for_host({
            "ip": "192.168.1.5",
            "gateway": "192.168.1.1",
            "wifi": {"ssid": "MyHotspot", "bssid": "00:11:22:33:44:55"}
        })
        pid = p["id"]

        # Rename
        ok = pm.rename_profile(pid, "Phone 5G Hotspot")
        self.assertTrue(ok)
        reloaded = pm.get_profile(pid)
        self.assertEqual(reloaded["name"], "Phone 5G Hotspot")

        # Delete
        del_ok = pm.delete_profile(pid)
        self.assertTrue(del_ok)
        self.assertIsNone(pm.get_profile(pid))


class TestProfileServerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.orig_profiles_dir = pm.PROFILES_DIR
        pm.PROFILES_DIR = Path(cls.temp_dir)

        cls.port = 8798
        cls.server = ThreadedHTTPServer(("127.0.0.1", cls.port), NetMapHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

        # Create two sample profiles
        p1, _ = pm.get_or_create_profile_for_host({
            "ip": "192.168.0.5",
            "gateway": "192.168.0.1",
            "wifi": {"ssid": "Home-WiFi", "bssid": "B8:FB:B3:01:02:03"}
        })
        p1["topology"] = {
            "profile": {"id": p1["id"], "name": "Home-WiFi"},
            "devices": [{"ip": "192.168.0.5", "mac": "B8:FB:B3:01:02:03", "name": "Home PC"}]
        }
        pm.save_profile(p1)

        p2, _ = pm.get_or_create_profile_for_host({
            "ip": "10.1.1.20",
            "gateway": "10.1.1.1",
            "wifi": {"ssid": "Cafe-WiFi", "bssid": "CC:DD:EE:01:02:03"}
        })
        p2["topology"] = {
            "profile": {"id": p2["id"], "name": "Cafe-WiFi"},
            "devices": [{"ip": "10.1.1.20", "mac": "CC:DD:EE:01:02:03", "name": "Laptop"}]
        }
        pm.save_profile(p2)

        cls.p1_id = p1["id"]
        cls.p2_id = p2["id"]

        STATE.active_profile_id = cls.p1_id
        STATE.viewing_profile_id = cls.p1_id
        STATE.update_topology(p1["topology"])
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        pm.PROFILES_DIR = cls.orig_profiles_dir
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _get(self, path):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        with urllib.request.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode("utf-8"))

    def _post(self, path, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode("utf-8"))

    def _delete(self, path):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method="DELETE")
        with urllib.request.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode("utf-8"))

    def test_get_profiles_endpoint(self):
        res = self._get("/api/profiles")
        self.assertIn("profiles", res)
        self.assertEqual(len(res["profiles"]), 2)
        self.assertEqual(res["active_profile_id"], self.p1_id)

    def test_get_single_profile(self):
        res = self._get(f"/api/profiles/{self.p2_id}")
        self.assertIn("profile", res)
        self.assertEqual(res["profile"]["name"], "Cafe-WiFi")

    def test_select_viewing_profile(self):
        res = self._post(f"/api/profiles/{self.p2_id}/select", {})
        self.assertTrue(res.get("success"))
        self.assertEqual(STATE.viewing_profile_id, self.p2_id)
        # Topology should now reflect Cafe-WiFi
        topo = STATE.get_topology()
        self.assertEqual(topo["profile"]["name"], "Cafe-WiFi")

    def test_rename_profile_endpoint(self):
        res = self._post(f"/api/profiles/{self.p2_id}/rename", {"name": "Corner Bakery Wi-Fi"})
        self.assertTrue(res.get("success"))
        self.assertEqual(res["name"], "Corner Bakery Wi-Fi")
        p = pm.get_profile(self.p2_id)
        self.assertEqual(p["name"], "Corner Bakery Wi-Fi")

    def test_cannot_delete_active_connected_profile(self):
        try:
            self._delete(f"/api/profiles/{self.p1_id}")
            self.fail("Should have failed to delete active connected profile")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

if __name__ == "__main__":
    unittest.main()
