# WiFi and NTP Integration Design

**Date:** 2026-02-21
**Author:** Sisyphus
**Status:** Approved

## Overview

Add WiFi connectivity and NTP time synchronization to the Pico 2W LED matrix clock. The system will read configuration from `config.ini`, connect to WiFi at startup, sync time via NTP, and periodically resync every 10 minutes during operation.

## Requirements

### Functional Requirements
- Read WiFi credentials and NTP server from `config.ini`
- Connect to WiFi on startup
- Display connection status on both LED matrix and console
- Sync time via NTP at startup
- Apply configurable timezone offset
- Resync via NTP every 10 minutes during operation
- Calculate and display time drift during each sync
- Stop and wait on configuration or startup failures

### Non-Functional Requirements
- Minimal interruption to animations during periodic sync (1-2 seconds)
- Graceful retry mechanism for periodic NTP failures
- Clear error messages on display and console
- Memory-efficient implementation (Pico 2W has limited RAM)
- Code must be maintainable and follow existing project conventions

## Architecture

### System Phases

1. **Startup Phase** (blocking, runs once):
   - Initialize display
   - Read config.ini
   - Connect to WiFi
   - Sync NTP time
   - Apply timezone offset
   - Update RTC
   - Start main loop

2. **Main Loop Phase** (infinite):
   - Run fireworks animations
   - Scroll messages with time display
   - Check NTP timer (every 10 minutes)
   - Handle NTP retry logic if needed

3. **Error Phase** (blocking):
   - Display error on LED matrix
   - Print detailed error to console
   - Wait indefinitely until user fixes issue

### Data Flow

```
Boot → Load config.ini → Connect WiFi → DHCP → Get IP →
Sync NTP → Calculate drift → Apply timezone → Update RTC →
Enter main loop → [Fireworks → Scroll → Check NPT timer → Repeat]
```

## Components

### config.ini

Location: `/config.ini` (root of CIRCUITPY volume)

```ini
[wifi]
ssid = YourNetworkName
password = YourWiFiPassword

[ntp]
server = pool.ntp.org
timezone_offset = +8
```

**Fields:**
- `wifi.ssid` - WiFi network name (required)
- `wifi.password` - WiFi password (required)
- `ntp.server` - NTP server hostname/IP (optional, default: pool.ntp.org)
- `ntp.timezone_offset` - UTC offset in hours (optional, default: 0, range: -12 to +14)

### WiFi Manager Module

**Functions:**
- `load_config()` - Parse config.ini, return dictionary
- `connect_wifi(ssid, password)` - Connect to WiFi, return IP string or None
- `display_status(message)` - Show status on LED matrix during setup
- `wifi_cleanup()` - Disconnect WiFi (optional, for power saving)

**Console Messages:**
- "Setup: connecting to wifi SSID..."
- "Connected, my IP is IP_ADDRESS"
- "Connection failed: ERROR_REASON"

**Display Messages:**
- "Connecting..." (during connection)
- "Connected: IP" (on success)
- "WiFi failed" (on failure)

### NTP Manager Module

**Functions:**
- `sync_ntp(server)` - Send NTP request, return struct_time or None
- `calculate_drift(rtc_time, ntp_time)` - Calculate difference in seconds
- `apply_timezone(time_struct, offset_hours)` - Convert UTC to local time
- `update_rtc(time_struct)` - Set system RTC

**Console Messages:**
- "Setup: syncing NTP from SERVER..."
- "Sync time via NTP, X.XXs drifted"
- "NTP sync failed: ERROR_REASON, retrying in 60s"

**Display Messages:**
- "Syncing..." (during sync)
- "Synced!" (on success)
- "NTP retry..." (on periodic failure)
- "NTP failed" (on startup failure)

### Setup Sequence

1. Initialize display (existing RGBMatrix setup)
2. Display "Setup..." on LED matrix
3. Load config.ini
   - **Fail → Display "No config.ini", wait indefinitely**
4. Validate config has required fields
   - **Fail → Display "Invalid config", wait indefinitely**
5. Display "Connecting to wifi SSID..."
6. Connect to WiFi
   - **Fail → Display "WiFi failed", wait indefinitely**
7. Display "Connected: IP_ADDRESS"
8. Display "Syncing NTP..."
9. Sync time from NTP server
   - **Fail → Display "NTP failed", wait indefinitely**
10. Calculate drift, print: "Sync time via NTP, X.XXs drifted"
11. Apply timezone offset
12. Update RTC
13. Display "Ready!"
14. Enter main loop

## Error Handling

### Startup Failures (Stop and Wait)

All startup errors follow this pattern:
1. Display short error message on LED matrix (max 64 chars)
2. Print detailed error to console with exception info
3. Enter infinite wait loop: `while True: time.sleep(1)`
4. User must fix issue and power cycle

**Error Cases:**
- Missing config.ini file
- Missing required config fields (ssid, password)
- WiFi connection timeout (10s)
- NTP sync timeout (5s)
- Invalid timezone offset (not in range -12 to +14)

### Periodic Failures (Retry in Background)

When NTP sync fails during main loop:
1. Display "NTP retry..." on LED matrix (one scroll cycle)
2. Print "NTP sync failed: ERROR, retrying in 60s" to console
3. Set retry timer and flag
4. Continue main loop animations normally
5. After 60s, retry NTP sync
6. Repeat until successful

### Connection Status Messages

**Startup:**
- "Setup: reading config.ini..."
- "Setup: connecting to wifi SSID..."
- "Connected, my IP is 192.168.1.100"
- "Connection failed: timeout"
- "Setup: syncing NTP from pool.ntp.org..."
- "Sync time via NTP, 2.34s drifted"

**Periodic:**
- "NTP sync: Sync time via NTP, 1.87s drifted" (success)
- "NTP sync failed: timeout, retrying in 60s" (failure)

## Main Loop Integration

### NTP Timer Logic

**Global Variables:**
```python
ntp_interval = 600  # 10 minutes in seconds
last_ntp_sync = time.monotonic()
ntp_retry_active = False
ntp_retry_time = 0
retry_delay = 60  # seconds
```

**NTP Check in Main Loop:**
```python
current_time = time.monotonic()
time_since_last_sync = current_time - last_ntp_sync

if ntp_retry_active:
    if current_time >= ntp_retry_time:
        # Retry NTP sync
        success = attempt_ntp_sync()
        if success:
            ntp_retry_active = False
            last_ntp_sync = current_time
        else:
            ntp_retry_time = current_time + retry_delay
elif time_since_last_sync >= ntp_interval:
    # Normal periodic sync
    success = attempt_ntp_sync()
    if success:
        last_ntp_sync = current_time
    else:
        ntp_retry_active = True
        ntp_retry_time = current_time + retry_delay
```

### Display Status During Setup

Setup phase temporarily overrides normal display:
1. Clear `main_group` (remove fireworks, scroll groups)
2. Create temporary status Label with small font
3. Update Label text as setup progresses
4. Remove status Label when complete
5. Restore normal display (recreate main_group if needed)

### Console Output Format

```
*** Running Pico HUB75 Code! ***
Setup: reading config.ini...
Setup: connecting to wifi MyNetwork...
Connected, my IP is 192.168.1.100
Setup: syncing NTP from pool.ntp.org...
Sync time via NTP, 2.34s drifted
Ready! Starting animations...

🎆 Multi Fireworks Burst

[10 minutes later]
NTP sync: Sync time via NTP, 1.87s drifted

🎆 Multi Fireworks Burst

[If NTP fails]
NTP sync failed: timeout, retrying in 60s
NTP retry...

[Continue animations normally]
```

## Dependencies

### Required CircuitPython Libraries
Add to `/lib/` folder:
- `adafruit_requests.mpy` - HTTP/HTTPS requests (for NTP)
- `adafruit_wiznet` - W5500 Ethernet driver (if using Ethernet)
- `adafruit_minimqtt` - MQTT (not used currently, but good to have)

**Note:** Pico 2W has built-in WiFi support, so we need:
- `adafruit_requests.mpy` - For NTP requests
- Use native `wifi_pool` and `wifi_radio` from CircuitPython core

### Configuration Files
- `/config.ini` - WiFi and NTP settings (user-created)

## Implementation Notes

### Memory Management
- Call `gc.collect()` after each WiFi/NTP operation
- Use small fonts for status messages (helvB08.bdf)
- Reuse Label objects instead of creating new ones
- Disconnect WiFi after NTP sync if power saving is needed

### Timezone Handling
- NTP returns UTC time
- Apply offset in hours: `local_time = utc_time + offset_hours * 3600`
- Handle negative offsets correctly
- Validate offset is in range -12 to +14

### WiFi Cleanup
Optionally disconnect WiFi after NTP sync to save power:
```python
if not wifi_cleanup():
    # Keep connected if disconnect fails
    pass
```
WiFi reconnects automatically on next NTP sync if needed.

### NTP Protocol
- Use UDP port 123
- Send 48-byte NTP request packet
- Parse 48-byte NTP response
- Extract transmit timestamp (bytes 40-47)
- Convert NTP timestamp (1900 epoch) to Unix timestamp (1970 epoch)

## Success Criteria

- ✅ Config file is read correctly
- ✅ WiFi connects on startup
- ✅ IP address is displayed
- ✅ NTP syncs time correctly
- ✅ Timezone offset is applied
- ✅ Drift is calculated and displayed
- ✅ Periodic sync works every 10 minutes
- ✅ Retry mechanism works on periodic failures
- ✅ Errors are caught and displayed
- ✅ Animations continue during retry period
- ✅ No memory leaks during extended operation
- ✅ Code follows project style guidelines

## Future Enhancements

- Add automatic timezone detection via geolocation IP
- Support multiple WiFi networks (fallback list)
- Add HTTPS support for secure NTP
- Implement timezone database with DST support
- Add MQTT integration for remote control
- Web-based configuration interface

## References

- CircuitPython WiFi documentation: https://docs.circuitpython.org/projects/wifi/en/latest/
- NTP protocol RFC: https://www.rfc-editor.org/rfc/rfc5905
- Pico 2W datasheet: https://datasheets.raspberrypi.com/pico2/pico2-datasheet.pdf
- Adafruit WiFi Nina library: https://github.com/adafruit/Adafruit_CircuitPython_WiFi_NINA
