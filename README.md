# pico-and-hub75-led-matrix
[![Watch the video](https://img.youtube.com/vi/XzjYWSvCipk/hqdefault.jpg)](https://youtu.be/XzjYWSvCipk)

Board - Any Raspberry Pi Pico, including the original, will run this code.
Wiring is the same for all Raspberry Pi Pico-family boards. If you're buying a new board, I'd get the most powerful veresion (at the time I'm writing this, that's the Pico 2 WH). 
https://www.adafruit.com/product/6315
Be sure to get a version with headers since you'll be adding this to a breadboard.

A mini breadboard. I love the ones by MonkMakes because they are labeled with the Raspberry Pi Pico pins, making breadboard wiring a lot easier.
https://www.adafruit.com/product/5422

Dispaly - most HUB75 64 x 32 displays or smaller should work. Know that if you use a display that's not 64 x 32 you'll need to modify your code for the new dimensions. Beware ultra-cheap boards. Double-check if it's been used with CircuitPython / Raspberry Pi Pico projects. Two examples below (there are many other sizes at these & different stores)
Adafruit sells these (I love Adafruit - high quality - great support): https://www.adafruit.com/product/2278 
And here is an ultra-cheap on AliExpress that seems to work, but know your price will probably increase with shipping and tarriffs:
https://www.aliexpress.us/item/2251832185365664.html?spm=a2g0o.order_list.order_list_main.53.3eff1802I6SLPf&gatewayAdapt=glo2usa

Power Cable - the HUB75 power cable with U-shaped ground & power ends, plus 4 pin port to plug into the HUB75 display should be included with every display.

Power Supply - 5v power supply w/at least 2 amps, but ideally 4 amps or more for full brightness. One with a barrel jack can connect to the plug below. Example below also has an adaptor plug:
https://a.co/d/cgor85U

Power Adapter Plug - Female DC Power Adapter 2.1mm Jack to Screw Terminal Block. Example:
https://www.adafruit.com/product/368

A microUSB cable & a power supply for the pico if you plan to run it when not connected to your computer. If you've been working with a pico you probably have these.

And if you prefer to diffuse the LEDs for a more "square" look to the pixels that also aren't as garishly bright, you can cover the display with diffusion acrylic like this: https://www.adafruit.com/product/4594

**Pico 2W** (with WiFi) - Required for NTP time sync
https://www.raspberrypi.com/products/raspberry-pi-pico-2-w/

## WiFi and NTP Setup

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

Drag files & folders onto a Pico configured with the latest CircuitPython from CircuitPython.org (if you don't know how to set up a pico with CircuitPython see the lesson at https://bit.ly/pico-school). The "lib" folder above shows you which libraries are used, but I'd STRONGLY advise downloading the newest version from CircuitPython.org. If you're new to CircuitPython and will do more projects, use CIRCUP. There is a lesson in pico-school on circup, as well. All tutorials for the University Course I teach to new-to-coding/new-to-electronics students is at: https://bit.ly/circuitpython-school. Pico only at https://bit.ly/pico-school

CONSIDERATION: As mentioned, you might consider the super-easy setup of buying an Adafruit MatrixPortal S3 (go for the S3 and not the M4, the S3 is newer, more capable with more storage, and cheaper). Using a Matrix Portal S3 allows you to use just one USB-style power supply (which you probably have laying around the house, for mobile phones, etc) and one USB-C cable to power both the board & the display. At the time I created this, that board was only $19.95 US at Adafruit: https://www.adafruit.com/product/5778
The code for this is only slightly different (and easier). AI can write the difference for you & if you want a vidoe tutorial, see: 
https://youtu.be/hb2HtoIEXM8?si=B6loUfyd5mQOX45j and
https://youtu.be/OV67IjXsQbA?si=ETBBG7LJgcw_CoTv

IMPORTANT:
The original video lesson did not mention the need for a common ground. Be sure to connect the shared – (minus) terminal of the barrel jack back to any GND pin on the Pico. This step is critical for stable operation.
ALSO: I discovered that using short 3" pin-to-pin wires connected through the ribbon cable completely eliminated the interference I saw when I tried to skip the ribbon and use only long 8" pin-socket jumpers.
The diagrams below show the correct orientation for the ribbon cable and how to use the shorter 3" pin-pin wires. This setup greatly reduced distortion and interference compared to using long 8" jumpers alone.

Wiring &amp; code to run a "Happy Graduation" on a Raspberry Pi Pico with a 64 x 32 HUB75 LED Matrix Display
<img width="800" height="450" alt="improved wiring diagram for hub75 and pico" src="https://github.com/user-attachments/assets/0985a79c-e9b0-41b5-bbf1-3da0da7d6aa4" />
<img width="800" height="537" alt="photo of hub75 and pico" src="https://github.com/user-attachments/assets/73a2579b-e8d7-4235-91d1-9f0822a25d9a" />
<img width="800" height="450" alt="Showing How to Wire with Ribbon" src="https://github.com/user-attachments/assets/26c134b2-5aae-4334-ac2f-ea60aa28bfc9" />



