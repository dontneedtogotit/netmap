# NetMap - Network Topology Mapper, Suggestions & AI Problem Solver for Omarchy

NetMap is a native desktop and web GUI application tailored for the **Omarchy Linux** desktop (Hyprland / Wayland). NetMap actively traces your local and upstream network—discovering your exact modem, router model, mesh extenders, CCTV security cameras, NVRs, and LAN devices—and includes an intelligent **Problem Solver & Setup Advisor** (*"I want to do X, what do I do, how to set it up the best"*).

![NetMap Icon](assets/icon.svg)

---

## Key Features

1. **Mistral AI & OpenRouter Integration**:
   - **Mistral AI Official API**: Seamless integration with official Mistral API keys (`console.mistral.ai`) and top models (`mistral-small-latest`, `mistral-large-latest`, `codestral-latest`, `open-mistral-nemo`, and `ministral-8b-latest`).
   - **OpenRouter Support**: Access free and open-source models (Qwen 2.5 Coder 32B free, DeepSeek R1 free, Llama 3.3 70B free).
   - **Local Offline Expert**: Built-in deterministic expert engine when no API keys are configured.

2. **Visuals Alongside Text Recommendations**:
   - **Dual Visual Engines**: Every AI response generates both **Interactive SVG Flowcharts** (with animated nodes, status colors, and protocol directional arrows) and **Mermaid Architecture Diagrams**.
   - **Router Configuration Cards**: Displays exact web GUI paths and configuration fields to enter in your TP-Link Archer BE550 v2 router.
   - **Topology Map Highlighting**: Direct "Highlight Nodes on Map" bridge to visually inspect affected devices.

3. **Proactive Network Settings Suggestions**:
   - Dedicated **Network Suggestions** dashboard analyzing your live topology against networking best practices.
   - Automated detection and remediation for:
     - **Aussie Broadband CGNAT Opt-Out**: 1-click guidance to remove inbound port blocking.
     - **Camera & IoT Isolation**: Restricting security cameras (RTSP 554/8554) and smart devices to the Archer BE550 IoT Network.
     - **Wi-Fi 7 & MLO Band Steering**: Optimizing 5 GHz / 6 GHz 320 MHz channels for high-performance clients.
     - **Extender AP Backhaul**: Mitigating Netgear EX6250v2 repeater half-duplex latency penalties.
     - **Static DHCP Leases**: Permanent address reservations for workstations, NVRs, and media servers.
     - **HomeShield QoS Prioritization**: Eliminating gaming bufferbloat.
     - **Ultra-Fast DNS**: Switching from unencrypted ISP resolvers to Cloudflare 1.1.1.1 or Quad9 9.9.9.9.
   - One-click "Ask AI to Solve" button on each suggestion.

4. **Per-Device Customizable Settings & Full AI Context**:
   - Customize device settings directly from the Device Inspector Drawer.
   - **Preset Fields**: Friendly Alias, Device Role, Physical Location, QoS / Traffic Priority, Network Segment / VLAN, IP Reservation status, and Context Notes.
   - **Dynamic Custom Fields**: Add arbitrary user-defined key-value attributes (e.g. `gpu`, `stream_url`, `backup_schedule`, `os`).
   - **Full Context Injection**: All preset and dynamic custom device settings are persistently stored in `~/.config/netmap/device_settings.json` and fed into Mistral and OpenRouter prompts, enabling hyper-personalized AI advice.

5. **Polished GUI & UX Enhancements**:
   - **Device Inventory Search & Filter**: Real-time search across aliases, IPs, MACs, roles, locations, and custom fields, with category filter chips (Cameras/NVR, TVs, PCs, Routers, Custom Configured).
   - **Non-blocking Toast Notifications**: Instant, sleek feedback replacing browser alerts.
   - **Glassmorphism Dark Theme**: Refined typography, glowing status dots, and smooth drawer transitions.

6. **Expanded Diagnostics & Desktop Ecosystem**:
   - **Bufferbloat & Loaded Latency Benchmark**: Live idle vs. loaded ping analysis with letter grades (A+ to F) evaluating TP-Link HomeShield QoS queue delay.
   - **Wi-Fi Spectrum & Channel Survey**: Analyzes 2.4 GHz, 5 GHz, and 6 GHz Wi-Fi crowding to recommend clean channels for Archer BE550.
   - **Wake-on-LAN (WoL)**: 1-click magic packet broadcasting to power on sleeping workstations, NAS, and TVs directly from the Device Inspector.
   - **CCTV Stream Verification & tvpc Sync**: Test RTSP stream reachability and sync camera entries directly to Omarchy's `~/.config/tvpc/cameras.conf`.
   - **Waybar Custom Module**: `netmap --waybar` outputs real-time Wi-Fi/Ethernet status, gateway ping, and device count JSON for your Hyprland Waybar status bar.

---

## Launching NetMap

From your Omarchy terminal:
```bash
netmap
```

Or search for **NetMap** in your Omarchy application launcher (Super key / Rofi / Wofi / Walker).

To launch in your default web browser instead of the native PySide6 window:
```bash
netmap --web
```

To run a headless CLI scan and dump network JSON:
```bash
netmap --scan-cli
```

To output real-time network status for your Waybar panel:
```bash
netmap --waybar
```

#### Waybar Configuration Example
Add this to your `~/.config/waybar/config.jsonc`:
```jsonc
"custom/netmap": {
  "format": "{}",
  "return-type": "json",
  "exec": "netmap --waybar",
  "interval": 10,
  "on-click": "netmap"
}
```

---

## Running Tests

NetMap includes automated unit and integration tests covering the Mistral integration, suggestions engine, device custom fields store, WoL, tvpc sync, bufferbloat test, spectrum survey, and REST API:
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```
