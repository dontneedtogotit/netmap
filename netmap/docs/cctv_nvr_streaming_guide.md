# CCTV, IP Camera & NVR Streaming Architecture Guide

## Protocol and Port Standards

| Port | Protocol | Purpose & Service |
| :--- | :--- | :--- |
| **554** | RTSP (TCP/UDP) | Standard Real-Time Streaming Protocol (H.264 / H.265 video feeds) |
| **8554** | RTSP Alt | Alternative RTSP streaming port (used by Docker & WebRTC gateways) |
| **8000** | Media Service | Hikvision / General DVR / NVR proprietary media service port |
| **37777** | TCP | Dahua / Amcrest Private NVR management port |
| **37778** | RTSP | Dahua / Amcrest secondary RTSP stream port |
| **8899** | HTTP / SOAP | ONVIF Device Management and Discovery |
| **7443** | HTTPS | Ubiquiti UniFi Protect Web Portal |
| **7444** | RTSPS | UniFi Protect Encrypted Video Stream |
| **9000** | Media / Discovery | Reolink Client discovery and media transport |

---

## Local Linux Viewing via Omarchy (tvpc & mpv)
Omarchy includes native camera integration via `tvpc cameras` and `mpv`. Configuration is stored in `~/.config/tvpc/cameras.conf`:

```
# Camera Name | RTSP URL | Aspect | Buffer | Group | Enabled
Driveway | rtsp://admin:password@192.168.0.136:554/stream1 | 16:9 | 200 | Exterior | 1
FrontDoor | rtsp://admin:password@192.168.0.137:554/h264Preview_01_main | 16:9 | 200 | Exterior | 1
```

### Low-Latency Direct Stream Testing Command:
```bash
mpv --profile=low-latency --untimed --opengl-glfinish=yes rtsp://admin:password@<CAMERA-IP>:554/stream
```

---

## Security Architecture: IoT VLAN Isolation
Security cameras should **never** have unrestricted access to your primary LAN:

```mermaid
graph TD
  subgraph IoT Network [Archer BE550 IoT Network: BananaFarm-IoT]
    Cam1[IP Camera 192.168.0.136]
    Cam2[IP Camera 192.168.0.137]
  end

  subgraph Main LAN [Main Private LAN: BananaFarm]
    Host[Omarchy Workstation 192.168.0.5]
    TV[Smart TVs]
  end

  Cam1 -.x|Device Isolation Blocks Lateral Probing| Host
  Host -->|Unidirectional RTSP Pull :554| Cam1
  Host -->|Encrypted Remote Access| Tailscale[Tailscale VPN]
```

### Archer BE550 IoT Configuration Checklist:
1. Open `https://192.168.0.1` > **Wireless > IoT Network**.
2. Enable IoT Network: SSID `BananaFarm-IoT`.
3. Check **Device Isolation**: This restricts cameras so they can only transmit outbound internet packets or respond to initiated inbound connections, preventing rogue camera firmware from scanning Omarchy workstations.
