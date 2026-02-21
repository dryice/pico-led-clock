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
   - Connect to WiFi on startup
   - Sync time via NTP
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
- "Ready!" - Setup complete, starting animations

⚠️ **Security**: `config.ini` contains your WiFi password in plain text. Never commit this file to version control. It's already in `.gitignore` - keep it that way.

**Troubleshooting:**

If the clock displays "No config.ini":
- Check that `config.ini` exists in the root of your CIRCUITPY drive
- Verify file format is correct (INI format with [wifi] and [ntp] sections)
- Ensure SSID and password are correct

If the clock displays "WiFi failed":
- Check that your WiFi SSID and password are correct
- Check that your router is powered on
- Check that the Pico 2W has a clear line of sight to your WiFi router
- Verify the Pico 2W has power (LED on the board)
- Try disconnecting from your router and reconfiguring WiFi

If the clock displays "NTP failed":
- Check your internet connection is working
- Verify NTP server name is correct (pool.ntp.org is reliable)
- Check that port 123 (NTP) is not blocked by your firewall
- Try using a different NTP server temporarily




