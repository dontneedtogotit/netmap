# TP-Link Archer BE550 v2 (Wi-Fi 7 BE9300) Engineering Guide

## Hardware Specifications
- **Model**: TP-Link Archer BE550 v2 (BE9300 Tri-Band Wi-Fi 7 Router)
- **Firmware Tested**: 1.12.1 Build 20260109 rel.27576(5553)
- **Processor & Architecture**: Quad-Core 64-bit Network Processing Unit
- **Ethernet Interfaces**:
  - 1x 2.5 Gbps RJ-45 WAN Port (connected to Aussie Broadband NBN NTD)
  - 4x 2.5 Gbps RJ-45 LAN Ports (Multi-Gigabit backhaul for workstations & switches)
- **USB Interface**: 1x USB 3.0 (Media Server, Apple Time Machine, FTP, Samba)
- **Wireless Bands**:
  - 2.4 GHz: Up to 574 Mbps (802.11ax/n)
  - 5 GHz: Up to 2880 Mbps (802.11be/ax/ac)
  - 6 GHz: Up to 5760 Mbps (802.11be, 320 MHz channel width)
- **Admin URL**: `https://192.168.0.1` (Self-signed TLS certificate)
- **Default Subnet**: `192.168.0.0/24` (Subnet mask `255.255.255.0`, Gateway `192.168.0.1`)
- **Default DHCP Pool**: `192.168.0.100` - `192.168.0.249`

---

## Web GUI Menu Navigation Paths

| Feature | Exact Click-Path in Archer BE550 Admin GUI | Description & Usage |
| :--- | :--- | :--- |
| **Virtual Servers (Port Forwarding)** | `Advanced > NAT Forwarding > Virtual Servers` | Forward external ports to internal hosts (e.g. 25565, 8000, 554) |
| **Port Triggering** | `Advanced > NAT Forwarding > Port Triggering` | Dynamic inbound port triggering for applications |
| **DMZ Host** | `Advanced > NAT Forwarding > DMZ` | Forward all unmapped ports to a single internal IP |
| **DHCP Address Reservation** | `Advanced > Network > DHCP Server > Address Reservation` | Bind MAC addresses to fixed IP addresses |
| **HomeShield QoS** | `HomeShield > QoS` | Prioritize devices (Gaming, Streaming) over bulk traffic |
| **MLO Network (Wi-Fi 7)** | `Wireless > MLO Network` | Aggregate 5 GHz and 6 GHz bands into a single high-speed link |
| **IoT Network & Isolation** | `Wireless > IoT Network` | Dedicated 2.4/5GHz SSID with AP device isolation for cameras & smart devices |
| **Guest Network** | `Wireless > Guest Network` | Isolated visitor wireless network |
| **WireGuard VPN Server** | `Advanced > VPN Server > WireGuard` | Built-in high-speed WireGuard tunnel server |
| **OpenVPN Server** | `Advanced > VPN Server > OpenVPN` | Standard OpenVPN server endpoint |
| **EasyMesh / Mesh** | `Advanced > EasyMesh` | Connect compatible TP-Link EasyMesh satellite nodes |
| **DNS Configuration** | `Advanced > Network > Internet > Advanced Settings > Primary/Secondary DNS` | Set custom resolvers (1.1.1.1, 9.9.9.9) |
| **Firmware Update** | `Advanced > System > Firmware Update` | Online update or manual `.bin` firmware flash |

---

## Configuration Procedures

### 1. Wi-Fi 7 Multi-Link Operation (MLO) Setup
1. Log in to `https://192.168.0.1` using your administrator password.
2. Navigate to **Wireless > MLO Network**.
3. Toggle **MLO Network** to **Enabled**.
4. Set the SSID (e.g., `BananaFarm-MLO`) and select **WPA3-SAE** security.
5. Under **Wireless > Wireless Settings > 6GHz**, verify that the **Channel Width** is set to **320 MHz**.
6. Connect Wi-Fi 7 compatible devices to aggregate 5GHz and 6GHz bands simultaneously.

### 2. CCTV & Smart Device Isolation (IoT Network)
1. Go to **Wireless > IoT Network**.
2. Enable the **IoT Network** toggle.
3. Configure SSID name (e.g., `BananaFarm-IoT`) with **WPA2-Personal** for compatibility with older smart cameras.
4. Check **Device Isolation** (Prevents IoT devices from communicating with personal PCs on `192.168.0.5`).
5. Move all IP cameras, NVRs, and smart plugs to this network.

### 3. Static IP Reservation for Servers & Workstations
1. Go to **Advanced > Network > DHCP Server > Address Reservation**.
2. Click **+ Add**.
3. Locate the MAC address (e.g. Omarchy PC `08:71:90:10:32:04`).
4. Enter target IP `192.168.0.5` and set status to **Enabled**.
5. Click **Save**.

### 4. HomeShield QoS (Eliminating Gaming Bufferbloat)
1. Go to **HomeShield > QoS**.
2. Toggle QoS **On**.
3. Enter your ISP bandwidth limits (e.g., Download: 1000 Mbps, Upload: 50 Mbps).
4. Click **+ Add Device** under High Priority and select your Omarchy gaming workstation (`192.168.0.5`).
5. Save settings to guarantee sub-1ms local router queueing under heavy load.
