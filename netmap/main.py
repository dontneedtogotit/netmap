#!/usr/bin/env python3
"""
main.py - Main entry point and GUI launcher for NetMap on Omarchy.
Launches the native PySide6 QtWebEngine application or standalone web mode.
"""

import sys
import os
import argparse
import socket
import threading
import time
import webbrowser
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from netmap.server import ThreadedHTTPServer, NetMapHandler, STATE
from netmap.scanner import perform_full_network_scan

def find_free_port(start_port: int = 8765) -> int:
    """Find an available TCP port starting from start_port."""
    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
        port += 1
    return start_port

def start_background_server(port: int) -> ThreadedHTTPServer:
    """Start local API and static HTTP server in a daemon thread."""
    server = ThreadedHTTPServer(('127.0.0.1', port), NetMapHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

def launch_pyside_gui(url: str):
    """Launch native PySide6 desktop window."""
    try:
        from PySide6 import QtCore, QtWidgets, QtGui, QtWebEngineWidgets
    except ImportError as e:
        print(f"[NetMap] PySide6 not found: {e}. Opening in web browser instead.")
        webbrowser.open(url)
        return

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("NetMap")
    app.setOrganizationName("Omarchy")
    app.setDesktopFileName("netmap")

    # Set dark palette matching Omarchy
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#0c0e14"))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#e2e8f0"))
    app.setPalette(palette)

    # Set window icon if available
    icon_path = Path(__file__).parent.parent / "assets" / "icon.svg"
    if icon_path.exists():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))

    # Main Window
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("NetMap - Omarchy Network Topology & Problem Solver")
    window.resize(1200, 780)

    # Center on screen
    screen_geo = QtGui.QGuiApplication.primaryScreen().geometry()
    x = (screen_geo.width() - 1200) // 2
    y = (screen_geo.height() - 780) // 2
    window.move(max(0, x), max(0, y))

    # QWebEngineView
    view = QtWebEngineWidgets.QWebEngineView()
    view.setStyleSheet("background-color: #0c0e14;")
    view.load(QtCore.QUrl(url))
    
    window.setCentralWidget(view)
    window.show()

    sys.exit(app.exec())

def main():
    parser = argparse.ArgumentParser(description="NetMap - GUI Network Topology Mapper & Problem Solver for Omarchy")
    parser.add_argument("--web", action="store_true", help="Launch in default web browser instead of native desktop window")
    parser.add_argument("--port", type=int, default=8765, help="Port to run local server on (default: 8765)")
    parser.add_argument("--scan-cli", action="store_true", help="Run scan in CLI and print JSON output")
    parser.add_argument("--waybar", action="store_true", help="Output network status in JSON format for Waybar custom module")
    args = parser.parse_args()

    if args.waybar:
        import json
        from netmap.scanner import get_local_host_info
        from netmap.tracer import ping_host
        host = get_local_host_info()
        wifi = host.get("wifi", {})
        ssid = wifi.get("ssid") or "Wired"
        gateway = host.get("gateway", "192.168.0.1")

        gw_ping = ping_host(gateway, count=1)
        lat = f"{gw_ping.get('avg', 1.0):.1f}ms" if gw_ping.get("reachable") else "Offline"

        icon = "󰖩" if wifi.get("ssid") else "󰈀"
        signal_pct = 85
        try:
            signal_pct = int(wifi.get("signal", 85))
        except Exception:
            pass

        data = {
            "text": f"{icon} {ssid} ({lat})",
            "tooltip": f"Network: {ssid}\nGateway: {gateway} ({lat})\nInterface: {host.get('interface', 'wlo1')}\nIP: {host.get('ip', '192.168.0.5')}",
            "class": "online" if gw_ping.get("reachable") else "offline",
            "percentage": signal_pct
        }
        print(json.dumps(data))
        return

    if args.scan_cli:
        import json
        topo = perform_full_network_scan()
        print(json.dumps(topo, indent=2))
        return

    port = find_free_port(args.port)
    url = f"http://127.0.0.1:{port}"

    print(f"[NetMap] Starting local server at {url} ...")
    start_background_server(port)

    # Kick off initial scan in background
    threading.Thread(target=lambda: STATE.update_topology(perform_full_network_scan()), daemon=True).start()

    if args.web:
        print(f"[NetMap] Opening {url} in your browser...")
        webbrowser.open(url)
        # Keep process alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[NetMap] Exiting.")
    else:
        launch_pyside_gui(url)

if __name__ == "__main__":
    main()
