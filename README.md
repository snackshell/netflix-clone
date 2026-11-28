# Wi-Fi Tool

A small, dependency-free Python CLI that scans nearby Wi-Fi networks and tests
candidate passwords from a wordlist by asking the operating system to associate
with the network one candidate at a time.

> Use it only on networks you are authorised to access.

## Requirements

- Python 3.8 or newer
- One of the OS networking tools:
  - **Linux** — `nmcli` (NetworkManager)
  - **Windows** — `netsh` (built in)
  - **macOS** — `airport` + `networksetup`

No `pip install` needed.

## Usage

```bash
# 1. See what is around
python wifi_tool.py scan

# 2. Build a wordlist (one password per line)
printf 'password\nhunter2\nMyWifi2024\n' > words.txt

# 3. Test the candidates
python wifi_tool.py test "MyNetwork" --wordlist words.txt

# Optional: slow down / speed up attempts
python wifi_tool.py test "MyNetwork" --wordlist words.txt --delay 2.0
```

If you omit `--wordlist`, a small built-in list of common passwords is used.

## How it works

1. `scan` lists SSIDs with signal strength and security type.
2. `test` walks the wordlist. For each candidate it:
   - disconnects from the current network,
   - attempts to connect with the candidate password,
   - waits ~2 seconds,
   - checks the active SSID to confirm success.
3. It stops at the first candidate that connects and prints it.

## Limits

- **Slow.** Roughly one guess every 3–4 seconds. This is a "try the obvious
  candidates" tool, not a high-speed brute-forcer. Fast WPA2 cracking uses a
  captured 4-way handshake and offline tools like hashcat/aircrack-ng.
- **Linux caching.** `nmcli` can cache a failed attempt, so the explicit
  disconnect before each try matters.
- **Windows profiles.** Each attempt adds a WLAN profile. Failed profiles linger
  in `netsh wlan show profiles`; remove one with
  `netsh wlan delete profile name="SSID"`.
- **macOS interface.** `en0` is hardcoded; change it if your Wi-Fi interface
  differs (`networksetup -listallhardwareports`).
- **WPA3 / enterprise.** The Windows profile template declares `WPA2PSK`, so
  WPA3 and enterprise networks will not connect with it as written.
