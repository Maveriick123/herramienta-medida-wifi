# wifi_scanner.py
"""
* Uso de `iw dev <iface> scan ap-force`.
* iwlist está roto en iwlwifi con kernels 6.x+ (bug upstream).
* nmcli no devuelve RSSI en dBm.
* `ap-force` fuerza active scan (probe requests a todos los canales).
"""

import subprocess
import re
import os
import time


class WifiScanner:
    """Escáner WiFi basado en iw dev scan ap-force."""

    # ─── Regex ────────────────────────────────────────────────────
    RE_BSS         = re.compile(r"^BSS\s+([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s*\(on\s+(\w+)\)")
    RE_SIGNAL      = re.compile(r"signal:\s*(-?[\d.]+)\s*dBm")
    RE_FREQ        = re.compile(r"freq:\s*(\d+)")
    RE_SSID        = re.compile(r"SSID:\s*(.+)")
    RE_CHANNEL     = re.compile(r"DS Parameter set:\s*channel\s+(\d+)")
    RE_STANDARD    = re.compile(r"standard:\s*(\S+)")
    RE_WIDTH       = re.compile(r"channel width:\s*\d+\s*\((\d+) MHz\)")
    RE_LAST_SEEN   = re.compile(r"last seen:\s*(\d+)\s*ms ago")
    RE_BEACON_INT  = re.compile(r"beacon interval:\s*(\d+)\s*TUs")

    # Fallback: detectar standard de las líneas de capabilities
    RE_HT_CAP      = re.compile(r"^HT capabilities:")
    RE_VHT_CAP     = re.compile(r"^VHT capabilities:")
    RE_HE_CAP      = re.compile(r"^HE capabilities:")
    RE_EHT_CAP     = re.compile(r"^EHT capabilities:")

    # Security
    RE_RSN         = re.compile(r"^RSN:")
    RE_WPA         = re.compile(r"^WPA:")
    RE_WEP         = re.compile(r"Authentication:\s*WEP")

    # Connected (iw dev <iface> link)
    RE_LINK_BSSID  = re.compile(r"Connected to\s+([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})")

    _STANDARD_PRIORITY = {"802.11n": 1, "802.11ac": 2, "802.11ax": 3, "802.11be": 4}

    def __init__(self, interface: str | None = None):
        self.interface = interface or self._detect_interface()
        if self.interface is None:
            raise RuntimeError("No se encontró interfaz WiFi (wl*).")
        self._connected_bssid = self._get_connected_bssid()

    @staticmethod
    def _detect_interface() -> str | None:
        try:
            for iface in os.listdir("/sys/class/net"):
                if iface.startswith("wl"):
                    return iface
        except OSError:
            pass
        return None

    def _get_connected_bssid(self) -> str | None:
        """Devuelve el BSSID al que está conectado, o None."""
        try:
            proc = subprocess.run(
                ["sudo", "iw", "dev", self.interface, "link"],
                capture_output=True, text=True, timeout=10
            )
            if proc.returncode != 0:
                return None
            m = self.RE_LINK_BSSID.search(proc.stdout)
            return m.group(1).lower() if m else None
        except (subprocess.TimeoutExpired, OSError):
            return None

    def scan(self) -> dict:
        proc = subprocess.run(
            ["sudo", "iw", "dev", self.interface, "scan", "ap-force"],
            capture_output=True, text=True, timeout=30
        )
        if proc.returncode != 0:
            raise RuntimeError(f"iw scan falló: {proc.stderr.strip()}")
        return self._parse(proc.stdout)

    def scan_burst(self, n: int, interval: float = 1.0) -> list[dict]:
        results = []
        for i in range(n):
            print(f"  [{i+1}/{n}] Escaneando...")
            results.append(self.scan())
            if i < n - 1:
                time.sleep(interval)
        return results

    # ─── Parser ───────────────────────────────────────────────────
    def _parse(self, output: str) -> dict:
        networks: list[dict] = []
        cur: dict | None = None

        for line in output.splitlines():
            s = line.strip()

            # ── Nuevo BSS ──
            m = self.RE_BSS.match(s)
            if m:
                if cur:
                    networks.append(cur)
                cur = {
                    "bssid": m.group(1),
                    "ssid": None,  # None = red oculta (no hay línea SSID:)
                    "channel": None,
                    "frequency_mhz": None,
                    "signal_dbm": None,
                    "last_seen_ms": None,
                    "beacon_interval_tus": None,
                    "security": None,
                    "standard": None,
                    "channel_width_mhz": None,
                    "connected": m.group(1).lower() == self._connected_bssid
                                if self._connected_bssid else False,
                }
                continue

            if cur is None:
                continue

            # ── SSID (solo si iw lo imprime; redes ocultas no tienen esta línea) ──
            m = self.RE_SSID.search(s)
            if m:
                ssid_val = m.group(1).strip()
                if ssid_val:  # SSID vacío = red oculta
                    cur["ssid"] = ssid_val
                continue

            # ── Frecuencia ──
            m = self.RE_FREQ.search(s)
            if m:
                cur["frequency_mhz"] = int(m.group(1))
                continue

            # ── Canal ──
            m = self.RE_CHANNEL.search(s)
            if m:
                cur["channel"] = int(m.group(1))
                continue

            # ── Signal ──
            m = self.RE_SIGNAL.search(s)
            if m:
                cur["signal_dbm"] = float(m.group(1))
                continue

            # ── Last seen (solo "ms ago") ──
            m = self.RE_LAST_SEEN.search(s)
            if m:
                cur["last_seen_ms"] = int(m.group(1))
                continue

            # ── Beacon interval ──
            m = self.RE_BEACON_INT.search(s)
            if m:
                cur["beacon_interval_tus"] = int(m.group(1))
                continue

            # ── Standard (directo de iw) ──
            m = self.RE_STANDARD.search(s)
            if m:
                cur["standard"] = m.group(1)
                continue

            # ── Channel width (directo de iw) ──
            m = self.RE_WIDTH.search(s)
            if m:
                cur["channel_width_mhz"] = int(m.group(1))
                continue

            # ── Standard (fallback: líneas de capabilities) ──
            if self.RE_EHT_CAP.match(s):
                self._set_standard(cur, "802.11be")
                continue
            if self.RE_HE_CAP.match(s):
                self._set_standard(cur, "802.11ax")
                continue
            if self.RE_VHT_CAP.match(s):
                self._set_standard(cur, "802.11ac")
                continue
            if self.RE_HT_CAP.match(s):
                self._set_standard(cur, "802.11n")
                continue

            # ── Security ──
            if self.RE_RSN.match(s):
                cur["security"] = "WPA2"
            elif self.RE_WPA.match(s):
                if cur["security"] is None:
                    cur["security"] = "WPA"
            elif self.RE_WEP.search(s):
                cur["security"] = "WEP"

        if cur:
            networks.append(cur)

        return {
            "interface": self.interface,
            "networks": networks,
            "count": len(networks),
        }

    @staticmethod
    def _set_standard(cur: dict, std: str):
        cur_std = cur["standard"]
        if cur_std is None or WifiScanner._STANDARD_PRIORITY[std] > WifiScanner._STANDARD_PRIORITY.get(cur_std, 0):
            cur["standard"] = std   