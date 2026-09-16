# Netgear EX6250v2 AC1750 Mesh Extender Optimization Guide

## Hardware Specifications
- **Model**: NETGEAR AC1750 Mesh WiFi Extender (EX6250v2)
- **Radios**: Dual-Band 802.11ac (2.4 GHz 450 Mbps, 5 GHz 1300 Mbps)
- **Physical Interface**: 1x Gigabit RJ-45 Ethernet Port (Auto-sensing 10/100/1000)
- **Default IP**: `192.168.0.76` (or `http://mywifiext.local`)

---

## The Wireless Repeater Penalty (Half-Duplex Degradation)
When operated as a traditional wireless range extender, the EX6250v2 must receive and retransmit data packets over the same wireless channel:
- **50% Throughput Cut**: Peak bandwidth is halved because the radio cannot transmit and receive simultaneously on the same channel.
- **10-25ms Jitter Spikes**: Channel contention and airtime utilization introduce noticeable latency spikes, degrading online gaming and live 4K casting.

---

## Optimal Architecture: Access Point (AP) Mode via Ethernet Backhaul

```mermaid
graph LR
  Router[Archer BE550 2.5G Port] ===|Cat6 Ethernet Backhaul 1 Gbps| Extender[Netgear EX6250v2 in AP Mode]
  Extender -.->|Full 1300 Mbps Wi-Fi| Clients[Smart TVs, Laptops & Phones]
```

### Step-by-Step Conversion to AP Mode:
1. Run a Cat6 Ethernet cable from one of the **2.5 Gbps LAN ports** on your Archer BE550 router to the **Gigabit Ethernet port** on the Netgear EX6250v2.
2. In your browser, navigate to `http://192.168.0.76` or `http://mywifiext.local`.
3. Log in with your Netgear extender admin credentials.
4. Go to **Setup > Wireless > Access Point Mode** (or select **AP Mode** during wizard setup).
5. Set the SSID and Wi-Fi password to match your primary network (`BananaFarm`), allowing wireless clients to roam seamlessly.
6. Save and reboot the device.
7. Result: 100% full gigabit throughput with zero repeating latency penalty!
