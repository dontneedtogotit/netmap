"""
router_client.py - Router Authentication & Live Configuration Client for NetMap.
Supports TP-Link Archer BE550 v2 / modern LuCI routers via RSA key exchange
and session tokens, as well as HTTP Basic/Digest and OpenWrt fallbacks.
"""

import os
import json
import ssl
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

CREDENTIALS_FILE = Path(os.path.expanduser("~/.config/netmap/router_credentials.json"))


def rsa_encrypt_pkcs1(plaintext: str, n_hex: str, e_hex: str) -> str:
    """
    Encrypt a plaintext string using RSA PKCS#1 v1.5 block type 2 padding
    in pure Python standard library (no external crypto dependencies).
    """
    n = int(n_hex, 16)
    e = int(e_hex, 16)
    k = (len(n_hex) + 1) // 2  # modulus length in bytes (e.g. 256 for 2048-bit)

    m = plaintext.encode("utf-8")
    # PKCS#1 v1.5 padding: 0x00 || 0x02 || PS || 0x00 || M
    # len(PS) must be at least 8 bytes and k - 3 - len(m) in total
    ps_len = k - 3 - len(m)
    if ps_len < 8:
        raise ValueError("Password is too long for RSA key modulus")

    ps = bytearray()
    while len(ps) < ps_len:
        rand_byte = os.urandom(1)[0]
        if rand_byte != 0:
            ps.append(rand_byte)

    em = b"\x00\x02" + bytes(ps) + b"\x00" + m
    m_int = int.from_bytes(em, "big")
    c_int = pow(m_int, e, n)
    c_hex = format(c_int, f"0{k * 2}x")
    return c_hex


def save_stored_credentials(gateway: str, username: str, password: str) -> None:
    """Save router credentials locally with secure 0600 file permissions."""
    try:
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        creds = {}
        if CREDENTIALS_FILE.exists():
            try:
                with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                    creds = json.load(f)
            except Exception:
                creds = {}

        gw_key = gateway.strip().rstrip("/")
        creds[gw_key] = {
            "username": username.strip(),
            "password": password
        }

        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = 0o600
        fd = os.open(str(CREDENTIALS_FILE), flags, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=2)
    except Exception as e:
        print(f"[RouterClient] Warning: Could not save credentials: {e}")


def load_stored_credentials(gateway: str) -> Optional[Dict[str, str]]:
    """Retrieve stored credentials for a specific router gateway."""
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            creds = json.load(f)
        gw_key = gateway.strip().rstrip("/")
        return creds.get(gw_key)
    except Exception:
        return None


def clear_stored_credentials(gateway: str) -> bool:
    """Remove stored credentials for a specific gateway."""
    if not CREDENTIALS_FILE.exists():
        return False
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            creds = json.load(f)
        gw_key = gateway.strip().rstrip("/")
        if gw_key in creds:
            del creds[gw_key]
            with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
                json.dump(creds, f, indent=2)
            return True
    except Exception:
        pass
    return False


class RouterClient:
    """
    HTTP/HTTPS client for interacting with router management portals.
    Specialized for TP-Link Archer BE550 v2 / modern LuCI with RSA authentication,
    plus HTTP Basic/Digest fallback for other routers.
    """

    def __init__(
        self,
        base_url: str = "https://192.168.0.1",
        username: str = "admin",
        password: str = "",
        timeout: float = 4.0
    ):
        clean_url = base_url.strip().rstrip("/")
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"https://{clean_url}"
        self.base_url = clean_url
        self.username = username.strip() or "admin"
        self.password = password
        self.timeout = timeout
        self.stok: Optional[str] = None
        self.auth_type: str = "tplink_luci"
        self.router_model: str = "Archer BE550 v2"

        # SSL context ignoring self-signed local router certificates
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def _post_form(self, path: str, data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """Send application/x-www-form-urlencoded POST request."""
        url = f"{self.base_url}{path}"
        encoded_body = urllib.parse.urlencode(data).encode("utf-8")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (NetMap-Omarchy/1.0)",
            "Accept": "application/json, text/plain, */*"
        }
        req = urllib.request.Request(url, data=encoded_body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ctx) as r:
                content = r.read().decode("utf-8", errors="ignore")
                try:
                    return r.status, json.loads(content)
                except Exception:
                    return r.status, {"raw": content}
        except urllib.error.HTTPError as he:
            err_content = he.read().decode("utf-8", errors="ignore")
            try:
                return he.code, json.loads(err_content)
            except Exception:
                return he.code, {"error": str(he), "raw": err_content}
        except Exception as ex:
            return 0, {"error": str(ex)}

    def check_connection(self) -> Dict[str, Any]:
        """Test reachability of the router portal."""
        paths_to_try = [
            "/cgi-bin/luci/login?form=keys",
            "/cgi-bin/luci/login?form=check_factory_default",
            "/webpages/index.html",
            "/"
        ]
        for p in paths_to_try:
            code, resp = self._post_form(p, {"operation": "read"})
            if code in [200, 302, 401]:
                return {
                    "reachable": True,
                    "status_code": code,
                    "gateway": self.base_url,
                    "endpoint_matched": p
                }
        return {
            "reachable": False,
            "gateway": self.base_url,
            "error": "Gateway not reachable or not responding"
        }

    def login(self) -> Dict[str, Any]:
        """
        Authenticate against the router.
        Executes TP-Link RSA PKCS#1 v1.5 key exchange and extracts session token `stok`.
        """
        if not self.password:
            return {
                "success": False,
                "error": "Password is required to log into the router"
            }

        # 1. Fetch RSA Public Key from /cgi-bin/luci/login?form=keys
        key_paths = [
            "/cgi-bin/luci/login?form=keys",
            "/cgi-bin/luci/;stok=/login?form=keys",
            "/login?form=keys"
        ]
        key_data = None
        for kp in key_paths:
            code, res = self._post_form(kp, {"operation": "read"})
            if code == 200 and res.get("success") and "password" in res.get("data", {}):
                key_data = res["data"]["password"]
                break

        if not key_data or len(key_data) < 2:
            # Check if router uses HTTP Basic Auth instead (OpenWrt / DD-WRT / Netgear)
            return self._try_http_basic_login()

        n_hex = key_data[0]
        e_hex = key_data[1]

        # 2. Encrypt user password using PKCS#1 v1.5 RSA
        try:
            encrypted_password = rsa_encrypt_pkcs1(self.password, n_hex, e_hex)
        except Exception as err:
            return {
                "success": False,
                "error": f"RSA encryption failed: {err}"
            }

        # 3. Submit login request to /cgi-bin/luci/login?form=login
        login_paths = [
            "/cgi-bin/luci/login?form=login",
            "/cgi-bin/luci/;stok=/login?form=login"
        ]
        login_resp = None
        for lp in login_paths:
            code, res = self._post_form(
                lp,
                {
                    "password": encrypted_password,
                    "operation": "login"
                }
            )
            login_resp = res
            if code == 200:
                if res.get("success") and "stok" in res.get("data", {}):
                    self.stok = res["data"]["stok"]
                    self.auth_type = "tplink_luci"
                    return {
                        "success": True,
                        "auth_type": "tplink_luci",
                        "stok": self.stok,
                        "gateway": self.base_url,
                        "message": "Successfully authenticated with TP-Link Archer BE550 router."
                    }
                elif res.get("errorcode") == "login failed" or not res.get("success"):
                    fail_info = res.get("data", {})
                    attempts_left = fail_info.get("attemptsAllowed", fail_info.get("remainTime", "unknown"))
                    fail_count = fail_info.get("failureCount", 1)
                    return {
                        "success": False,
                        "error": "Incorrect router password",
                        "failure_count": fail_count,
                        "attempts_remaining": attempts_left,
                        "details": res
                    }

        return {
            "success": False,
            "error": "Login request failed or rejected by router",
            "details": login_resp
        }

    def _try_http_basic_login(self) -> Dict[str, Any]:
        """Fallback for routers using standard HTTP Basic or Digest authentication."""
        passman = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        passman.add_password(None, self.base_url, self.username, self.password)
        auth_handler = urllib.request.HTTPBasicAuthHandler(passman)
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self.ctx),
            auth_handler
        )
        try:
            with opener.open(f"{self.base_url}/", timeout=self.timeout) as r:
                if r.status in [200, 302]:
                    self.auth_type = "http_basic"
                    return {
                        "success": True,
                        "auth_type": "http_basic",
                        "gateway": self.base_url,
                        "message": "Authenticated via HTTP Basic auth."
                    }
        except urllib.error.HTTPError as he:
            if he.code == 401:
                return {
                    "success": False,
                    "error": "Invalid username or password (HTTP 401 Unauthorized)"
                }
        except Exception as ex:
            return {
                "success": False,
                "error": f"HTTP authentication failed: {ex}"
            }
        return {
            "success": False,
            "error": "Could not establish authentication session with router"
        }

    def fetch_live_settings(self) -> Dict[str, Any]:
        """
        Extract live configuration from router admin endpoints.
        If authenticated, queries live API endpoints.
        """
        settings = {
            "authenticated": bool(self.stok or self.auth_type == "http_basic"),
            "auth_type": self.auth_type,
            "gateway": self.base_url,
            "status_all": {},
            "wan_status": {},
            "lan_status": {},
            "wireless_status": {},
            "security_status": {},
            "qos_status": {},
            "system_info": {}
        }

        if not self.stok:
            return settings

        # Endpoints to query on modern TP-Link LuCI routers:
        stok_prefix = f"/cgi-bin/luci/;stok={self.stok}"
        endpoints = {
            "status_all": f"{stok_prefix}/admin/status?form=all",
            "internet": f"{stok_prefix}/admin/status?form=internet",
            "wan_ipv4": f"{stok_prefix}/admin/network?form=wan_ipv4_status",
            "network_status": f"{stok_prefix}/admin/network?form=status_ipv4",
            "sysmode": f"{stok_prefix}/admin/system?form=sysmode",
            "wan_speed": f"{stok_prefix}/admin/status?form=wan_speed",
            "cloud_device": f"{stok_prefix}/admin/cloud_account?form=get_deviceInfo"
        }

        for key, path in endpoints.items():
            code, res = self._post_form(path, {"operation": "read"})
            if code == 200 and res.get("success"):
                settings[key] = res.get("data", {})
            else:
                settings[key] = {}

        return settings

    def logout(self) -> bool:
        """Terminate the active router session."""
        if not self.stok:
            return True
        logout_path = f"/cgi-bin/luci/;stok={self.stok}/admin/system?form=logout"
        code, _ = self._post_form(logout_path, {"operation": "write"})
        self.stok = None
        return code in [200, 302]
