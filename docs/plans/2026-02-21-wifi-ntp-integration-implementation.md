# WiFi and NTP Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add WiFi connectivity and NTP time synchronization to Pico 2W LED matrix clock with configurable settings from config.ini.

**Architecture:** Sequential setup phase (config → WiFi → NTP) followed by main loop with periodic NTP sync every 10 minutes. Uses native Pico 2W WiFi support with retry mechanism for periodic failures.

**Tech Stack:** CircuitPython 9+, Pico 2W native WiFi, adafruit_requests, NTP protocol (UDP), INI config parsing

---

## Prerequisites

**Required CircuitPython libraries in `/lib/`:**
- `adafruit_requests.mpy` - HTTP/HTTPS requests
- `adafruit_wifi.mpy` - WiFi networking (native Pico 2W)
- `adafruit_ntp.mpy` - NTP client (optional, can implement manually)

**Note:** We'll implement NTP manually to avoid extra dependencies and have full control over the protocol.

---

### Task 1: Create config.ini template

**Files:**
- Create: `/config.ini` (user will edit this)

**Step 1: Create config.ini template**

```ini
[wifi]
ssid = YourNetworkName
password = YourWiFiPassword

[ntp]
server = pool.ntp.org
timezone_offset = +8
```

**Step 2: Commit**

```bash
git add config.ini
git commit -m "feat: add config.ini template for WiFi and NTP settings"
```

---

### Task 2: Remove MatrixPortal S3 code

**Files:**
- Modify: `code.py:15-16, 22-24`

**Step 1: Remove MatrixPortal import**

Remove lines 15-16:
```python
# If you use a Matrix Portal S3, you'll need to import the coe below,
# from adafruit_matrixportal.matrixportal import MatrixPortal
```

**Step 2: Remove MatrixPortal setup comments**

Remove lines 22-24:
```python
# === Setup for Matrix Portal S3 ===
# matrixportal = MatrixPortal(status_neopixel=board.NEOPIXEL, bit_depth=6, debug=True)
# display = matrixportal.graphics.display
```

**Step 3: Test display still works**

Manual verification: Run code.py on Pico 2W with LED matrix connected
Expected: Fireworks animation and scrolling time display work

**Step 4: Commit**

```bash
git add code.py
git commit -m "refactor: remove MatrixPortal S3 code, Pico 2W only"
```

---

### Task 3: Add WiFi imports and global variables

**Files:**
- Modify: `code.py:12-19`

**Step 1: Add WiFi imports**

Add after existing imports (line 19):
```python
import wifi_pool
import wifi_radio
from adafruit_requests import Session
import socketpool
```

**Step 2: Add NTP timer global variables**

Add after `SCROLL_DELAY = 0.025` (line 102):
```python
# NTP sync settings
NTP_INTERVAL = 600  # 10 minutes in seconds
NTP_RETRY_DELAY = 60  # seconds
```

**Step 3: Commit**

```bash
git add code.py
git commit -m "feat: add WiFi imports and NTP timer variables"
```

---

### Task 4: Implement config.ini reader

**Files:**
- Modify: `code.py` (add function before main code)

**Step 1: Add load_config() function**

Add after imports (line 20):
```python
def load_config():
    """Load config.ini and return dictionary of settings."""
    print("Setup: reading config.ini...")

    try:
        config = {}
        current_section = None

        with open("/config.ini", "r") as f:
            for line in f:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Section headers
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1].lower()
                    config[current_section] = {}
                    continue

                # Key-value pairs
                if "=" in line and current_section:
                    key, value = line.split("=", 1)
                    config[current_section][key.strip().lower()] = value.strip()

        # Validate required fields
        if "wifi" not in config or "ssid" not in config["wifi"]:
            raise ValueError("Missing wifi.ssid in config.ini")
        if "wifi" not in config or "password" not in config["wifi"]:
            raise ValueError("Missing wifi.password in config.ini")

        print("✓ Config loaded successfully")
        return config

    except FileNotFoundError:
        print("✗ Error: config.ini not found")
        raise
    except Exception as e:
        print(f"✗ Error parsing config.ini: {e}")
        raise
```

**Step 2: Test config reading (manual)**

Create test config.ini with dummy values, run in REPL:
```python
config = load_config()
print(config)
```
Expected: Dictionary with wifi and ntp sections

**Step 3: Commit**

```bash
git add code.py
git commit -m "feat: implement config.ini reader with validation"
```

---

### Task 5: Implement display_status() function

**Files:**
- Modify: `code.py` (add function after load_config)

**Step 1: Add display_status() function**

Add after load_config() function:
```python
def display_status(message):
    """Display status message on LED matrix."""
    print(message)

    # Clear main group
    main_group.clear()
    main_group.append(displayio.Group())

    # Create status label
    status_label = Label(
        font_small,
        text=message,
        color=WHITE,
        x=2,
        y=32
    )

    main_group.append(status_label)
    display.refresh()
```

**Step 2: Test status display (manual)**

Run in REPL:
```python
display_status("Test Message")
```
Expected: "Test Message" appears on LED matrix

**Step 3: Commit**

```bash
git add code.py
git commit -m "feat: add display_status() for setup messages"
```

---

### Task 6: Implement connect_wifi() function

**Files:**
- Modify: `code.py` (add function after display_status)

**Step 1: Add connect_wifi() function**

Add after display_status() function:
```python
def connect_wifi(ssid, password):
    """Connect to WiFi and return IP address or None on failure."""
    print(f"Setup: connecting to wifi {ssid}...")
    display_status("Connecting...")

    try:
        # Enable WiFi radio
        wifi_radio.enabled = True
        wifi_radio.hostname = "pico-led-clock"

        # Connect to network
        wifi_pool.init()
        wifi_radio.connect(ssid, password)

        # Wait for connection (max 10 seconds)
        timeout = time.monotonic() + 10
        while not wifi_radio.connected and time.monotonic() < timeout:
            time.sleep(0.1)

        if not wifi_radio.connected:
            print(f"✗ Connection failed: timeout after 10s")
            display_status("WiFi failed")
            return None

        # Get IP address
        ip_address = wifi_radio.ipv4_address
        print(f"✓ Connected, my IP is {ip_address}")
        display_status(f"Connected: {ip_address}")

        # Create socket pool for requests
        socket_pool = socketpool.SocketPool(wifi_radio)
        requests = Session(socket_pool)

        return ip_address, requests

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        display_status("WiFi failed")
        return None
```

**Step 2: Test WiFi connection (manual)**

Run in REPL with real credentials:
```python
ip, req = connect_wifi("YourSSID", "YourPassword")
print(ip)
```
Expected: IP address printed, "Connected: IP" on display

**Step 3: Commit**

```bash
git add code.py
git commit -m "feat: implement WiFi connection function"
```

---

### Task 7: Implement NTP sync function

**Files:**
- Modify: `code.py` (add function after connect_wifi)

**Step 1: Add sync_ntp() function**

Add after connect_wifi() function:
```python
def sync_ntp(requests, server):
    """Sync time from NTP server and return struct_time or None on failure."""
    print(f"Setup: syncing NTP from {server}...")
    display_status("Syncing...")

    try:
        # NTP request packet (48 bytes)
        NTP_PACKET = bytearray(48)
        NTP_PACKET[0] = 0x1B  # LI=0, VN=3, Mode=3 (client)

        # Get server IP
        server_ip = socket.getaddrinfo(server, 123)[0][4][0]

        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)

        # Send request
        sock.sendto(NTP_PACKET, (server_ip, 123))

        # Receive response
        response, _ = sock.recvfrom(48)
        sock.close()

        # Extract transmit timestamp (bytes 40-47)
        ntp_timestamp = int.from_bytes(response[40:48], byteorder='big')

        # Convert NTP timestamp (1900 epoch) to Unix timestamp (1970 epoch)
        # NTP epoch = Jan 1, 1900
        # Unix epoch = Jan 1, 1970
        # Difference = 70 years = 2208988800 seconds
        unix_timestamp = ntp_timestamp - 2208988800

        # Convert to struct_time
        ntp_time = time.gmtime(unix_timestamp)

        print(f"✓ NTP sync successful")
        return ntp_time, unix_timestamp

    except Exception as e:
        print(f"✗ NTP sync failed: {e}")
        display_status("NTP failed")
        return None, None
```

**Step 2: Test NTP sync (manual)**

Run in REPL after WiFi connected:
```python
ntp_time, unix_ts = sync_ntp(requests, "pool.ntp.org")
print(ntp_time)
```
Expected: Valid struct_time returned

**Step 3: Commit**

```bash
git add code.py
git commit -m "feat: implement NTP sync function"
```

---

### Task 8: Implement timezone and drift functions

**Files:**
- Modify: `code.py` (add functions after sync_ntp)

**Step 1: Add apply_timezone() function**

Add after sync_ntp() function:
```python
def apply_timezone(time_struct, offset_hours):
    """Apply timezone offset to UTC time."""
    # Convert to Unix timestamp
    unix_ts = time.mktime(time_struct)

    # Apply offset (convert hours to seconds)
    offset_seconds = int(offset_hours * 3600)
    local_ts = unix_ts + offset_seconds

    # Convert back to struct_time
    return time.gmtime(local_ts)
```

**Step 2: Add calculate_drift() function**

Add after apply_timezone() function:
```python
def calculate_drift(rtc_time, ntp_unix_time):
    """Calculate time drift in seconds between RTC and NTP time."""
    # Convert RTC to Unix timestamp
    rtc_unix = time.mktime(rtc_time)

    # Calculate drift
    drift = ntp_unix_time - rtc_unix

    return drift
```

**Step 3: Test timezone and drift (manual)**

Run in REPL:
```python
utc_time = time.gmtime()
local_time = apply_timezone(utc_time, 8)  # UTC+8
print(local_time)
```
Expected: Local time with offset applied

**Step 4: Commit**

```bash
git add code.py
git commit -m "feat: implement timezone offset and drift calculation"
```

---

### Task 9: Implement setup phase

**Files:**
- Modify: `code.py` (add setup() function, call before main loop)

**Step 1: Add setup() function**

Add before main loop (after messages list, line 136):
```python
def setup():
    """Setup WiFi and NTP, return config and requests session."""
    global last_ntp_sync

    # Display setup message
    display_status("Setup...")

    # Load config
    try:
        config = load_config()
    except Exception as e:
        display_status("No config.ini")
        while True:
            time.sleep(1)  # Stop and wait

    # Get config values
    wifi_ssid = config["wifi"]["ssid"]
    wifi_password = config["wifi"]["password"]
    ntp_server = config.get("ntp", {}).get("server", "pool.ntp.org")
    timezone_offset = config.get("ntp", {}).get("timezone_offset", "0")

    # Validate timezone offset
    try:
        offset_hours = float(timezone_offset)
        if offset_hours < -12 or offset_hours > 14:
            raise ValueError(f"Invalid timezone offset: {offset_hours}")
    except ValueError as e:
        print(f"✗ Invalid timezone offset: {e}")
        display_status("Invalid config")
        while True:
            time.sleep(1)  # Stop and wait

    # Connect to WiFi
    result = connect_wifi(wifi_ssid, wifi_password)
    if result is None:
        while True:
            time.sleep(1)  # Stop and wait

    ip_address, requests = result

    # Sync NTP
    ntp_time, ntp_unix = sync_ntp(requests, ntp_server)
    if ntp_time is None:
        while True:
            time.sleep(1)  # Stop and wait

    # Calculate drift
    current_rtc_time = time.localtime()
    drift = calculate_drift(current_rtc_time, ntp_unix)
    print(f"Sync time via NTP, {drift:.2f}s drifted")

    # Apply timezone
    local_time = apply_timezone(ntp_time, offset_hours)

    # Update RTC
    rtc.RTC().datetime = local_time

    # Set last NTP sync time
    last_ntp_sync = time.monotonic()

    # Ready to start
    display_status("Ready!")
    time.sleep(2)

    return config, requests, offset_hours, ntp_server
```

**Step 2: Call setup() before main loop**

Replace line 277-280:
```python
print("*** Running Pico HUB75 Code! ***")

# === Main Loop ===
while True:
```

With:
```python
print("*** Running Pico HUB75 Code! ***")

# Setup WiFi and NTP
try:
    config, requests, timezone_offset, ntp_server = setup()
except Exception as e:
    print(f"✗ Setup failed: {e}")
    display_status("Setup failed")
    while True:
        time.sleep(1)  # Stop and wait

# === Main Loop ===
while True:
```

**Step 3: Add global variables for NPT tracking**

Add at top with other globals (after imports):
```python
# NTP sync tracking
last_ntp_sync = 0
ntp_retry_active = False
ntp_retry_time = 0
```

**Step 4: Test setup (manual)**

Create config.ini with real credentials, run code.py
Expected: Setup completes, "Ready!" displayed, main loop starts

**Step 5: Commit**

```bash
git add code.py
git commit -m "feat: implement setup phase with WiFi and NTP"
```

---

### Task 10: Implement periodic NTP sync in main loop

**Files:**
- Modify: `code.py` (add NTP check in main loop)

**Step 1: Add attempt_ntp_sync() function**

Add after setup() function:
```python
def attempt_ntp_sync(requests, ntp_server, timezone_offset):
    """Attempt NTP sync, return True on success, False on failure."""
    global last_ntp_sync

    try:
        # Sync NTP
        ntp_time, ntp_unix = sync_ntp(requests, ntp_server)
        if ntp_time is None:
            return False

        # Calculate drift
        current_rtc_time = time.localtime()
        drift = calculate_drift(current_rtc_time, ntp_unix)
        print(f"NTP sync: Sync time via NTP, {drift:.2f}s drifted")

        # Apply timezone
        local_time = apply_timezone(ntp_time, timezone_offset)

        # Update RTC
        rtc.RTC().datetime = local_time

        # Update last sync time
        last_ntp_sync = time.monotonic()

        return True

    except Exception as e:
        print(f"✗ NTP sync failed: {e}")
        display_status("NTP retry...")
        time.sleep(2)  # Show message briefly
        return False
```

**Step 2: Add NTP check in main loop**

Add at start of main loop (after "while True:", line ~280):
```python
    # Check NTP sync
    current_time = time.monotonic()

    if ntp_retry_active:
        if current_time >= ntp_retry_time:
            # Retry NTP sync
            success = attempt_ntp_sync(requests, ntp_server, timezone_offset)
            if success:
                ntp_retry_active = False
            else:
                ntp_retry_time = current_time + NTP_RETRY_DELAY
    elif last_ntp_sync > 0 and current_time - last_ntp_sync >= NTP_INTERVAL:
        # Normal periodic sync
        success = attempt_ntp_sync(requests, ntp_server, timezone_offset)
        if not success:
            ntp_retry_active = True
            print(f"NTP sync failed, retrying in {NTP_RETRY_DELAY}s")
            ntp_retry_time = current_time + NTP_RETRY_DELAY
```

**Step 3: Test periodic sync (manual)**

Run code.py, wait 10 minutes
Expected: NTP sync message appears, time updates if drifted

**Step 4: Commit**

```bash
git add code.py
git commit -m "feat: implement periodic NTP sync in main loop with retry"
```

---

### Task 11: Add example config.ini to repo

**Files:**
- Create: `config.ini.example`

**Step 1: Create example config**

```ini
[wifi]
ssid = YourNetworkName
password = YourWiFiPassword

[ntp]
server = pool.ntp.org
timezone_offset = +8
```

**Step 2: Update .gitignore**

Add to `.gitignore`:
```
# WiFi and NTP config
config.ini
```

**Step 3: Commit**

```bash
git add config.ini.example .gitignore
git commit -m "docs: add config.ini.example and update .gitignore"
```

---

### Task 12: Create README update

**Files:**
- Modify: `README.md` (add WiFi and NTP setup section)

**Step 1: Add WiFi setup section to README**

Add after hardware list:
```markdown
## WiFi and NTP Setup

To enable automatic time synchronization, you'll need a **Pico 2W** (with built-in WiFi).

1. Copy `config.ini.example` to `config.ini`
2. Edit `config.ini` with your WiFi credentials:
   ```ini
   [wifi]
   ssid = YourNetworkName
   password = YourWiFiPassword

   [ntp]
   server = pool.ntp.org
   timezone_offset = +8  # Your timezone offset from UTC
   ```

3. Copy `config.ini` to your CIRCUITPY drive
4. The clock will:
   - Connect to WiFi on startup
   - Sync time via NTP
   - Resync every 10 minutes
   - Display connection status on LED matrix

**Timezone offsets:**
- UTC-8 (Pacific Time): `-8`
- UTC+0 (GMT): `0`
- UTC+8 (Singapore/China): `+8`
- UTC+9 (Japan): `+9`

**Status messages:**
- "Setup..." - Initializing
- "Connecting..." - Connecting to WiFi
- "Connected: IP" - WiFi connected
- "Syncing..." - Syncing NTP
- "Ready!" - Setup complete, starting animations
```

**Step 2: Update hardware requirements**

Add to hardware list:
```markdown
- **Pico 2W** (with WiFi) - Required for NTP time sync
  https://www.raspberrypi.com/products/raspberry-pi-pico-2-w/
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add WiFi and NTP setup instructions to README"
```

---

### Task 13: Final testing and validation

**Files:**
- Test: Manual hardware testing

**Step 1: Test with invalid config**

Rename config.ini to config.ini.bak
Run code.py
Expected: "No config.ini" on display, waits indefinitely

**Step 2: Test with missing password**

Create config.ini with only SSID
Run code.py
Expected: "Invalid config" on display, waits indefinitely

**Step 3: Test with wrong WiFi credentials**

Create config.ini with wrong password
Run code.py
Expected: "WiFi failed" on display, waits indefinitely

**Step 4: Test with valid config**

Create config.ini with correct credentials
Run code.py
Expected: Setup completes, "Ready!" displayed, animations start, console shows connection messages

**Step 5: Test NTP sync**

Wait 10 minutes
Expected: "NTP sync: Sync time via NTP, X.XXs drifted" in console

**Step 6: Test NTP retry**

Disconnect WiFi while running
Wait for NTP sync attempt
Expected: "NTP sync failed, retrying in 60s", animations continue, "NTP retry..." appears briefly

**Step 7: Test timezone offset**

Set different timezone in config.ini
Run code.py
Expected: Time displayed is correct for timezone

**Step 8: Commit**

```bash
git add docs/plans/
git commit -m "docs: update plan with testing results"
```

---

### Task 14: Clean up and finalize

**Files:**
- Modify: Various cleanup tasks

**Step 1: Remove debug prints**

Remove excessive print statements, keep only key status messages

**Step 2: Optimize memory**

Add gc.collect() after WiFi operations:
- After WiFi connect
- After NTP sync

**Step 3: Add error handling to display_status**

Wrap display_status in try-except to prevent crashes if display errors

**Step 4: Final code review**

Check all functions follow project style guidelines:
- Snake_case function names
- Clear docstrings
- Consistent error handling
- Proper memory management

**Step 5: Commit**

```bash
git add code.py
git commit -m "refactor: clean up code and optimize memory usage"
```

---

## Success Criteria Verification

- [ ] Config file is read correctly with validation
- [ ] WiFi connects on startup with correct IP
- [ ] IP address is displayed on LED matrix
- [ ] NTP syncs time correctly on startup
- [ ] Timezone offset is applied correctly
- [ ] Drift is calculated and displayed
- [ ] Periodic sync works every 10 minutes
- [ ] Retry mechanism works on periodic failures
- [ ] Errors are caught and displayed clearly
- [ ] Animations continue during retry period
- [ ] No memory leaks during extended operation
- [ ] Code follows project style guidelines
- [ ] README has clear setup instructions
- [ ] config.ini.example provided

## Rollback Plan

If any critical issue arises:

1. Revert to commit before "feat: implement setup phase with WiFi and NTP"
2. Manual time setting via RTC will continue to work
3. Animations will run without WiFi/NTP

## Estimated Time

- Setup phase: 2-3 hours
- Testing and validation: 1-2 hours
- Documentation: 30 minutes
- Total: 4-6 hours
