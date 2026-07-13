# Backgrounds

I like [jnthas/clockwise: do-it-yourself, full-featured and smart wall clock device](https://github.com/jnthas/clockwise), but I only have a Pi Pico 2W, and a 64x64 LED. [gallaugher/pico-and-hub75-led-matrix: Wiring & code to run a "Happy Graduation" on a Raspberry Pi Pico with a 64 x 32 HUB75 LED Matrix DIsplay](https://github.com/gallaugher/pico-and-hub75-led-matrix) is the closed thing I can find. So I forked it and try to make a small clock out of it.

# Hardware changes

Most of the documents in the parent repo still works, except these two:

- Because I want WiFi/NTP support, it needs to be a board with wifi. I'm using Pi Pico 2W
- Because I'm using a 64x64 LED matrix, so I connected the "empty" ping on HUB75 to GP21 on the Pico
<img width="800" height="450" alt="improved wiring diagram for hub75 and pico" src="https://github.com/user-attachments/assets/0985a79c-e9b0-41b5-bbf1-3da0da7d6aa4" />

# WiFi and NTP Setup

To enable automatic time synchronization, you'll need a **Pico 2W** (with built-in WiFi).

1. Copy `config.ini.example` to the root of your CIRCUITPY drive as `config.ini`
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
   - Connect to WiFi on startup, retrying every 10 seconds until success
   - Sync time via NTP on startup, retrying every 10 seconds until success
   - Resync every 10 minutes
   - Display connection status on LED matrix

**Timezone offsets:**
- UTC-8 (Pacific Time): `-8`
- UTC-5 (US Eastern, Peru): `-5`
- UTC+0 (GMT): `0`
- UTC+5:30 (India): `+5.5`
- UTC+8 (Singapore/China): `+8`
- UTC+9 (Japan): `+9`
- UTC+10 (Australia Eastern): `+10`

For regions with Daylight Saving Time, update `timezone_offset` twice yearly.

**Status messages:**
- "Setup..." - Initializing
- "Connecting..." - Connecting to WiFi
- "Connected: IP" - WiFi connected
- "Syncing..." - Syncing NTP
- "WiFi retry 10s" - WiFi connection failed, retrying in 10 seconds (console shows full message)
- "NTP retry 10s" - NTP sync failed, retrying in 10 seconds (console shows full message)
- "Ready!" - Setup complete, starting animations

⚠️ **Security**: `config.ini` contains your WiFi password in plain text. Never commit this file to version control. It's already in `.gitignore` - keep it that way.

**Troubleshooting:**

If the clock displays "No config.ini" or "Invalid config":
- Check that `config.ini` exists in the root of your CIRCUITPY drive
- Verify file format is correct (INI format with [wifi] and [ntp] sections)
- Ensure timezone offset is valid (-12 to +14, or use fractions like +5.5)
- These are **blocking errors** - missing/invalid `config.ini` or invalid timezone require fixing the configuration file; the clock will stop and wait

If the clock displays "WiFi retry 10s":
- This is a **transient** state - the clock is automatically retrying WiFi connection
- Common causes: incorrect SSID/password, router offline, weak WiFi signal
- Check your WiFi credentials in `config.ini`
- Ensure your router is powered on and within range
- The clock will continue retrying every 10 seconds until connection succeeds

If the clock displays "NTP retry 10s":
- This is a **transient** state - the clock is automatically retrying NTP sync
- Common causes: no internet connection, blocked NTP port (123), NTP server down
- Verify your internet connection is working
- Check that port 123 (NTP) is not blocked by your firewall
- Ensure NTP server name in `config.ini` is correct (pool.ntp.org is reliable)
- The clock will continue retrying every 10 seconds until sync succeeds




