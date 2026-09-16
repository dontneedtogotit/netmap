# Aussie Broadband NBN & Carrier-Grade NAT (CGNAT) Engineering Guide

## Upstream Architecture Overview
- **Internet Service Provider (ISP)**: Aussie Broadband (AS4764 Aussie Fibre Pty Ltd)
- **Point of Interconnect (POI)**: Brisbane / Queensland Regional Core
- **Connection Type**: NBN (National Broadband Network) - FTTP (Fibre to the Premises) or HFC
- **NBN NTD (Network Termination Device)**: Optical Network Terminal with 1G/2.5G WAN handoff
- **Router WAN Interface**: 2.5 Gbps WAN port on TP-Link Archer BE550 v2

---

## Carrier-Grade NAT (CGNAT) Explained
Aussie Broadband utilizes Carrier-Grade NAT (RFC 6598, `100.64.0.0/10`) by default for residential connections to conserve IPv4 addresses:
- **CGNAT Hop**: `100.91.128.1` (or within `100.64.0.0/10`)
- **Public External IPv4**: Shared among multiple households (e.g. `117.20.69.236`)

### Consequences of Active CGNAT
1. **Traditional Port Forwarding is Ineffective**: Inbound packets hitting `117.20.69.236` at external ports (e.g. `25565`, `554`, `8000`) cannot route through Aussie Broadband's CGNAT gateway to your Archer BE550 router.
2. **Direct P2P Gaming & CCTV Remote Access Blocked**: Hosting Minecraft, Palworld, Valheim, or accessing RTSP CCTV streams from mobile cellular networks fails without a dynamic public IP or peer-to-peer overlay.
3. **WireGuard / OpenVPN Inbound Tunnels Fail**: The router cannot listen on public UDP ports without external port mapping.

---

## Solution 1: Free 1-Click CGNAT Opt-Out (Recommended)
Aussie Broadband provides a free, instant opt-out from CGNAT that assigns your Archer BE550 a real, public dynamic IPv4 address:

1. Open the **MyAussie app** on your iOS/Android phone or visit [my.aussiebroadband.com.au](https://my.aussiebroadband.com.au).
2. Log in with your Aussie Broadband account credentials.
3. Select your active Broadband service.
4. Go to **Service Settings > Connection Settings**.
5. Locate the **Opt-out of CGNAT** toggle.
6. Switch the toggle to **ON**.
7. Wait 5-15 minutes. To immediately refresh your WAN lease:
   - In Archer BE550 Web GUI (`https://192.168.0.1`), navigate to **Advanced > Network > Internet** and click **Renew**.
   - Or click "Kick Connection" in the MyAussie app.
8. Once complete, your WAN IP will match your public IP (no `100.x.x.x` CGNAT hop), and standard Virtual Server port forwards will function immediately!

---

## Solution 2: Zero-Port Forwarding via Tailscale (CGNAT Traversal)
If you prefer not to expose public ports to the raw internet, Tailscale establishes secure WireGuard tunnels using STUN/DERP NAT traversal:

1. Install Tailscale on Omarchy Linux:
   ```bash
   sudo pacman -S tailscale
   sudo systemctl enable --now tailscaled
   sudo tailscale up
   ```
2. Enable Subnet Routing to access your entire home LAN (192.168.0.0/24) while away:
   ```bash
   sudo tailscale up --advertise-routes=192.168.0.0/24
   ```
3. Approve the subnet route in your Tailscale Admin Console.
4. Install Tailscale on your mobile phone or travel laptop. You can now access your Archer BE550 (`https://192.168.0.1`), CCTV cameras, and local game servers with zero open ports!
