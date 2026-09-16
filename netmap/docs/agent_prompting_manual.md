# NetMap AI Agent Prompting & Diagnostic Manual

## How NetMap Agents Operate
NetMap utilizes a collaborative multi-agent architecture designed to diagnose, optimize, and resolve home and office network problems. Each agent has a specialized domain and is equipped with real diagnostic tools.

### Specialized Agent Personas
1. **Orchestrator Agent**: Triages user goals, selects appropriate specialized agents, plans tool executions, and formats visual diagrams and action plans.
2. **Security & CGNAT Agent**: Expert in Carrier-Grade NAT bypass (Aussie Broadband 100.91.128.1), Tailscale WireGuard tunnels, firewall rules, and IoT camera network isolation.
3. **Performance & Latency Agent**: Expert in eliminating bufferbloat, setting up HomeShield QoS, Wi-Fi 7 MLO aggregation, and 2.5 Gbps Ethernet backhauls.
4. **CCTV & Surveillance Agent**: Expert in RTSP streaming (ports 554, 8554), ONVIF device management, NVR recording paths, and Omarchy `tvpc` integration.
5. **Media & Streaming Agent**: Expert in Google Cast discovery, Chromecast TV streams (ports 8009), and Jellyfin / Plex server deployment.
6. **Hardware Specialist Agent**: Deep engineering knowledge of the TP-Link Archer BE550 v2, Netgear EX6250v2, and NBN Optical Terminals.

---

## Best Practices for Prompting NetMap Agents

### 1. Leverage User-Configured Device Context
Before asking the agent complex questions, set your device's friendly Alias, Role, Location, and QoS priority in the Device Inspector drawer. The agents receive this full dictionary in their context.

*Example Query with Context:*
> "How do I optimize traffic for my Omarchy Gaming Rig so that 4K streaming to Bedroom TV doesn't cause ping spikes?"

### 2. Instructing Agents to Perform Diagnostics
Agents have access to live diagnostic tools. You can explicitly ask them to test devices:
> "Test if RTSP port 554 is open on 192.168.0.136 and check my ping to the gateway."

### 3. Requesting Architectural Diagrams
Agents can generate interactive flowcharts and Mermaid diagrams:
> "Provide a Mermaid sequence diagram showing how video travels from my IP camera through the Archer BE550 to my phone via Tailscale."
