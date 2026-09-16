"""
test_agents.py - Unit and integration tests for NetMap's agentic framework,
diagnostic tools, knowledge base docs, and REST API endpoints.
"""

import unittest
import threading
import time
import urllib.request
import json

from netmap.agents import (
    AGENT_CATALOG,
    tool_ping,
    tool_portscan,
    tool_list_docs,
    tool_read_docs,
    tool_get_device,
    AgentOrchestrator
)
from netmap.server import ThreadedHTTPServer, NetMapHandler, STATE


class TestAgentTools(unittest.TestCase):
    def setUp(self):
        self.sample_topo = {
            "wan": {"isp": "Aussie Broadband", "cgnat_active": True},
            "host": {"ip": "127.0.0.1", "gateway": "192.168.0.1", "mac": "B8:FB:B3:01:02:03"},
            "router": {"name": "Archer BE550 v2"},
            "router_settings": {"hardware": {"model_name": "Archer BE550 v2"}},
            "devices": [
                {"ip": "127.0.0.1", "mac": "B8:FB:B3:01:02:03", "name": "Workstation", "category": "host"},
                {"ip": "192.168.0.136", "mac": "28:57:BE:11:22:33", "name": "Driveway Cam", "category": "camera"}
            ]
        }

    def test_tool_ping_loopback(self):
        res = tool_ping("127.0.0.1", count=1)
        self.assertIn("reachable", res)
        self.assertIn("host", res)
        self.assertEqual(res["host"], "127.0.0.1")

    def test_tool_portscan_loopback(self):
        res = tool_portscan("127.0.0.1", ports=[65432, 65433])
        self.assertIn("open_ports", res)
        self.assertIn("scanned", res)
        self.assertEqual(res["scanned"], [65432, 65433])

    def test_tool_list_docs(self):
        docs = tool_list_docs()
        self.assertIsInstance(docs, list)
        self.assertGreater(len(docs), 0)
        filenames = [d["filename"] for d in docs]
        self.assertIn("router_be550_guide.md", filenames)
        self.assertIn("cgnat_and_isp_guide.md", filenames)
        self.assertIn("cctv_nvr_streaming_guide.md", filenames)

    def test_tool_read_docs(self):
        doc = tool_read_docs("cgnat_and_isp_guide.md")
        self.assertTrue(doc["found"])
        self.assertIn("Aussie Broadband", doc["content"])
        self.assertIn("100.91.128.1", doc["content"])

        bad = tool_read_docs("non_existent_file.md")
        # Falls back to router guide or returns found=True fallback
        self.assertIn("filename", bad)

    def test_tool_get_device(self):
        dev = tool_get_device(self.sample_topo, "192.168.0.136")
        self.assertIsNotNone(dev)
        self.assertEqual(dev["name"], "Driveway Cam")

        dev_mac = tool_get_device(self.sample_topo, "B8:FB:B3:01:02:03")
        self.assertIsNotNone(dev_mac)
        self.assertEqual(dev_mac["name"], "Workstation")


class TestAgentOrchestrator(unittest.TestCase):
    def setUp(self):
        self.sample_topo = {
            "wan": {"isp": "Aussie Broadband", "cgnat_active": True},
            "host": {"ip": "192.168.0.5", "gateway": "192.168.0.1", "mac": "B8:FB:B3:01:02:03"},
            "router": {"name": "Archer BE550 v2"},
            "router_settings": {"hardware": {"model_name": "Archer BE550 v2"}},
            "devices": [
                {"ip": "192.168.0.5", "mac": "B8:FB:B3:01:02:03", "name": "Workstation", "category": "host"},
                {"ip": "192.168.0.136", "mac": "28:57:BE:11:22:33", "name": "Cam 1", "category": "camera", "open_ports": [554]}
            ]
        }
        self.orchestrator = AgentOrchestrator()

    def test_agent_catalog(self):
        self.assertIn("orchestrator", AGENT_CATALOG)
        self.assertIn("security", AGENT_CATALOG)
        self.assertIn("performance", AGENT_CATALOG)
        self.assertIn("surveillance", AGENT_CATALOG)
        self.assertIn("media", AGENT_CATALOG)
        self.assertIn("hardware", AGENT_CATALOG)

    def test_run_cctv_workflow(self):
        res = self.orchestrator.run_agentic_workflow(
            "How do I set up CCTV security cameras or NVR with tvpc, view RTSP streams, and access them remotely?",
            self.sample_topo,
            requested_agent="surveillance"
        )
        self.assertIn("agent_trace", res)
        self.assertGreater(len(res["agent_trace"]), 0)
        self.assertIn("action_items", res)
        self.assertGreater(len(res["action_items"]), 0)
        self.assertIn("visual_diagram", res)
        self.assertIn("mermaid", res)
        self.assertEqual(res["lead_agent"]["id"], "surveillance")

    def test_run_lag_gaming_workflow(self):
        res = self.orchestrator.run_agentic_workflow(
            "Fix lag spikes, bufferbloat, and reduce my gaming ping",
            self.sample_topo
        )
        self.assertEqual(res["lead_agent"]["id"], "performance")
        self.assertTrue(any("Ping" in a["label"] for a in res["action_items"]))

    def test_multi_turn_chat(self):
        res = self.orchestrator.chat_multi_turn(
            "session_test_1",
            "How do I remove CGNAT on Aussie Broadband?",
            self.sample_topo
        )
        self.assertIn("summary", res)
        self.assertIn("action_items", res)
        self.assertIn("session_id", res)
        self.assertEqual(res["session_id"], "session_test_1")


class TestServerAgentEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 8798
        cls.server = ThreadedHTTPServer(("127.0.0.1", cls.port), NetMapHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        # Sample topology
        STATE.update_topology({
            "wan": {"isp": "Aussie Broadband", "cgnat_active": True},
            "host": {"ip": "127.0.0.1", "gateway": "192.168.0.1", "mac": "B8:FB:B3:01:02:03"},
            "router": {"name": "Archer BE550 v2"},
            "router_settings": {"hardware": {"model_name": "Archer BE550 v2"}},
            "devices": [
                {"ip": "127.0.0.1", "mac": "B8:FB:B3:01:02:03", "name": "Workstation", "category": "host"},
                {"ip": "192.168.0.136", "mac": "28:57:BE:11:22:33", "name": "Cam 1", "category": "camera", "open_ports": [554]}
            ]
        })
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

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

    def test_api_agent_catalog(self):
        res = self._get("/api/agent/agents")
        self.assertIn("orchestrator", res)
        self.assertIn("security", res)
        self.assertTrue(len(res) >= 6)

    def test_api_agent_tools(self):
        res = self._get("/api/agent/tools")
        self.assertIsInstance(res, list)
        self.assertTrue(len(res) >= 4)
        tool_names = [t["name"] for t in res]
        self.assertIn("tool_ping", tool_names)
        self.assertIn("tool_portscan", tool_names)

    def test_api_agent_run(self):
        res = self._post("/api/agent/run", {
            "goal": "How do I isolate CCTV security cameras on Archer BE550?",
            "agent": "security"
        })
        self.assertIn("agent_trace", res)
        self.assertIn("action_items", res)
        self.assertEqual(res["lead_agent"]["id"], "security")

    def test_api_agent_chat(self):
        res = self._post("/api/agent/chat", {
            "session_id": "test_session_api",
            "message": "What is MLO on Wi-Fi 7?"
        })
        self.assertIn("summary", res)
        self.assertIn("session_id", res)

    def test_api_agent_execute_action(self):
        res = self._post("/api/agent/execute-action", {
            "type": "tool_read_docs",
            "params": {"topic": "be550"}
        })
        self.assertTrue(res.get("success"))
        self.assertIn("BE550", res["result"]["content"])

    def test_api_docs(self):
        # 1. Index
        index = self._get("/api/docs")
        self.assertIn("articles", index)
        self.assertTrue(len(index["articles"]) >= 6)

        # 2. Specific article
        art = self._get("/api/docs?id=cgnat_and_isp_guide")
        self.assertTrue(art.get("found"))
        self.assertIn("Aussie Broadband", art["content"])


if __name__ == "__main__":
    unittest.main()
