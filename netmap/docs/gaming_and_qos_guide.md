# Gaming Network Optimization & Bufferbloat Mitigation Guide

## Understanding Bufferbloat and Latency Spikes
Bufferbloat occurs when network equipment excessively buffers packets rather than dropping them, causing latency to spike from 10ms to over 200ms when an upload or download is active in the home.

---

## 4-Step Optimization Strategy

### 1. Enable Archer BE550 HomeShield QoS
The TP-Link Archer BE550 v2 features active queue management (HomeShield QoS):
1. Open `https://192.168.0.1` > **HomeShield > QoS**.
2. Toggle QoS **Enabled**.
3. Set your bandwidth limits matching Aussie Broadband speed tests (e.g. 1000 Mbps download, 50 Mbps upload).
4. Add your primary PC (`192.168.0.5`) to the **High Priority** list.
5. This prioritizes real-time gaming packets (UDP) above background cloud backups or video streaming.

### 2. Connect via 2.5 Gbps Ethernet or Wi-Fi 7 6GHz
- Avoid 2.4 GHz entirely for latency-sensitive applications (Bluetooth and microwave interference cause 50ms+ jitter).
- The Archer BE550 features four **2.5 Gbps LAN ports**. Direct Cat6 cabling drops local ping to **< 0.3ms**.
- If wireless, connect to the **Wi-Fi 7 MLO** network or dedicated 5GHz/6GHz band.

### 3. Ensure Direct Gateway Association (Bypassing Repeater)
If a Netgear EX6250v2 is nearby, ensure your PC connects directly to the Archer BE550 (`B8:FB:B3:80:57:EF`) rather than hopping through the extender.
Check current BSSID in Omarchy terminal:
```bash
nmcli -t -f ACTIVE,SSID,BSSID,CHAN,FREQ,RATE,SIGNAL dev wifi | grep '^yes'
```

### 4. Benchmark Ping & Jitter
Run a local diagnostic ping to verify jitter:
```bash
ping -c 20 192.168.0.1
ping -c 20 1.1.1.1
```
Target average to Cloudflare DNS in Brisbane/Sydney: **10 - 18ms** with **< 2ms jitter**.
