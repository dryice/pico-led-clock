# Code to run fireworks animation, then scrolling marquees
# of text surrounded by icons.
# Video to set up this code can be found in the playlist:
# https://bit.ly/pico-school
# Diagram & files/folders at: https://github.com/gallaugher/pico-and-hub75-led-matrix
# Icons are stored in a folder named "graphics" on the CIRCUITPY volume,
# .bdf fonts are stored ina  folder named "fonts"
# For pico use, the "lib" folder needs:
# folders named: adafruit_bitmap_font & adafruit_display_text
# and the library named adafruit_ticks.mpy

import board, displayio, time, gc, random, math, rgbmatrix, framebufferio
import rtc

from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label

import wifi
import wifi_pool
import wifi_radio
import socket
from adafruit_requests import Session
import socketpool


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
                    # Remove inline comments
                    if "#" in value:
                        value = value.split("#")[0]
                    config[current_section][key.strip().lower()] = value.strip()

        # Validate required fields
        if "wifi" not in config:
            raise ValueError("Missing [wifi] section in config.ini")
        if "ssid" not in config["wifi"]:
            raise ValueError("Missing wifi.ssid in config.ini")
        if "password" not in config["wifi"]:
            raise ValueError("Missing wifi.password in config.ini")

        # Set defaults for optional fields
        if "ntp" not in config:
            config["ntp"] = {}
        config["ntp"].setdefault("server", "pool.ntp.org")
        config["ntp"].setdefault("timezone_offset", "0")

        print("✓ Config loaded successfully")
        return config

    except FileNotFoundError:
        print("✗ Error: config.ini not found")
        raise
    except Exception as e:
        print(f"✗ Error parsing config.ini: {e}")
        raise


def display_status(message):
    """Display status message on LED matrix."""
    print(message)

    # Clear main group
    main_group.clear()

    # Create status label
    status_label = Label(font_small, text=message, color=WHITE, x=2, y=32)

    main_group.append(status_label)
    display.refresh()
    gc.collect()


def connect_wifi(ssid, password):
    """Connect to WiFi and return (ip_address, requests) tuple or None on failure."""
    print(f"Setup: connecting to wifi {ssid}...")
    display_status("Connecting...")

    try:
        # Validate inputs
        if not ssid or not password:
            print("✗ Connection failed: ssid and password required")
            display_status("WiFi failed")
            return None

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
        pool = socketpool.SocketPool(wifi_radio)
        requests = Session(pool)
        gc.collect()

        return ip_address, requests

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        display_status("WiFi failed")
        return None


def sync_ntp(server):
    """Sync time from NTP server and return struct_time or None on failure."""
    print(f"Setup: syncing NTP from {server}...")
    display_status("Syncing...")

    sock = None
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

        # Validate response length
        if len(response) < 48:
            raise ValueError(f"Invalid NTP response: {len(response)} bytes")

        # Extract transmit timestamp (bytes 40-47)
        ntp_timestamp = int.from_bytes(response[40:48], byteorder="big")

        # Validate timestamp range (must be >= 1900 epoch)
        if ntp_timestamp < 2208988800:
            raise ValueError(f"Invalid NTP timestamp: {ntp_timestamp}")

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
    finally:
        if sock:
            sock.close()
            gc.collect()


def apply_timezone(time_struct, offset_hours):
    """Apply timezone offset to UTC time."""
    # Convert to Unix timestamp
    unix_ts = time.mktime(time_struct)

    # Apply offset (convert hours to seconds)
    offset_seconds = int(offset_hours * 3600)
    local_ts = unix_ts + offset_seconds

    # Convert back to struct_time
    return time.gmtime(local_ts)


def calculate_drift(rtc_time, ntp_unix_time):
    """Calculate time drift in seconds between RTC and NTP time."""
    # Convert RTC to Unix timestamp
    rtc_unix = time.mktime(rtc_time)

    # Calculate drift
    drift = ntp_unix_time - rtc_unix

    return drift


displayio.release_displays()

# === Setup for Pico ===
# Setup rgbmatrix display (change pins to match your wiring)
matrix = rgbmatrix.RGBMatrix(
    width=64,  # Change width & height if you have an LED matrix with different dimensions
    height=64,
    bit_depth=6,
    rgb_pins=[  # Preserve GP4 & GP5 for standard STEMMA-QT
        board.GP2,  # R1
        board.GP3,  # G1
        board.GP6,  # B1
        board.GP7,  # R2
        board.GP8,  # G2
        board.GP9,  # B2
    ],
    addr_pins=[
        board.GP10,  # A
        board.GP16,  # B
        board.GP18,  # C
        board.GP20,  # D
        board.GP21,  # E
    ],
    clock_pin=board.GP11,
    latch_pin=board.GP12,
    output_enable_pin=board.GP13,
    tile=1,
    serpentine=False,
    doublebuffer=True,
)

display = framebufferio.FramebufferDisplay(matrix)
# === end of pico setup === #

WIDTH = display.width
HEIGHT = display.height

# === Set Initial Time ===
# Update year, month, day, hour, minute below as needed
# CircuitPython will keep time running from this point
current_time = time.struct_time((2025, 2, 21, 10, 30, 0, 0, -1, -1))
try:
    rtc.RTC().datetime = current_time
except Exception as e:
    print(f"⚠️ RTC initialization failed: {e}")
    print("Continuing with system time...")

main_group = displayio.Group()
display.root_group = main_group

# === Fonts ===
font_small = bitmap_font.load_font("/fonts/helvB08.bdf")
font_large = bitmap_font.load_font("/fonts/helvB12.bdf")

# === COLOR VARIABLES ===
WHITE = 0xFFFFFF
SOFT_RED = 0xCC4444
DEEP_CORAL = 0xFF6F61
PEACH = 0xFFDAB9
WARM_GOLD = 0xFFD700
GOLDENROD = 0xDAA520
TANGERINE = 0xFFA07A

# Lean firework colors toward warm tones
firework_colors = [WHITE, GOLDENROD, WARM_GOLD, DEEP_CORAL, SOFT_RED, TANGERINE]

celebration_colors = [
    WHITE,
    GOLDENROD,
    WARM_GOLD,
    DEEP_CORAL,
    SOFT_RED,
    TANGERINE,
    PEACH,
]

# === Timing Parameters ===
SCROLL_DELAY = 0.025
SCROLL_STEP = 1

# === NTP Sync Settings ===
NTP_INTERVAL = 600  # Sync time every 10 minutes
NTP_RETRY_DELAY = 60  # Wait 60 seconds before retrying failed NTP sync


def get_time_string():
    """Generate formatted time string: 'Mon Feb 21 10:30'"""
    t = time.localtime()
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    day_name = days[t.tm_wday]
    month_name = months[t.tm_mon - 1]

    return f"{day_name} {month_name} {t.tm_mday} {t.tm_hour:02d}:{t.tm_min:02d}"


# === Messages: (line1, line2, image_path, optional_color)
# You can add or remove elements from the messages lists, as you like.
# Add a second line of text in the empty strings for a two-line message in smaller font
messages = [
    (get_time_string, "", None, None),  # Time display, no logo
]


def create_scroll_group(logo_path, text1, text2, color=None):
    group = displayio.Group()
    logo_width = 0
    logo_spacing = 33
    logo_tilegrid = None

    if color:
        color1 = color
        color2 = color
    else:
        color1 = random.choice(celebration_colors)
        color2 = random.choice([c for c in celebration_colors if c != color1])

    if logo_path:
        try:
            logo_bitmap = displayio.OnDiskBitmap(logo_path)
            logo_tilegrid = displayio.TileGrid(
                logo_bitmap, pixel_shader=logo_bitmap.pixel_shader, x=2, y=33
            )
            group.append(logo_tilegrid)
            logo_width = logo_tilegrid.width
        except Exception as e:
            print(f"Error loading image {logo_path}: {e}")

    text_start = logo_width + logo_spacing if logo_path else 0

    if text2.strip() == "":
        label1 = Label(font_large, text=text1, color=color1)
        label1.x = text_start
        label1.y = 16
        # label1.y = 48
        group.append(label1)
        text_width = label1.bounding_box[2]
    else:
        label1 = Label(font_small, text=text1, color=color1)
        label1.x = text_start
        label1.y = 10
        group.append(label1)

        label2 = Label(font_small, text=text2, color=color2)
        label2.x = text_start
        label2.y = 22
        # label2.y = 54
        group.append(label2)

        text_width = max(label1.bounding_box[2], label2.bounding_box[2])

    total_width = text_start + text_width

    # Add second logo directly after text, no extra spacing
    if logo_path and logo_tilegrid:
        try:
            logo_bitmap = displayio.OnDiskBitmap(logo_path)
            second_logo = displayio.TileGrid(
                logo_bitmap,
                pixel_shader=logo_bitmap.pixel_shader,
                x=text_start + text_width,
                y=0,
            )
            group.append(second_logo)
            total_width += second_logo.width + 1  # Ensure full scroll off screen
        except Exception as e:
            print(f"Error loading second logo image: {e}")

    return group, total_width


def fireworks_animation(duration=2.5, burst_count=5, sparks_per_burst=40):
    print("\U0001f386 Multi Fireworks Burst")
    animation_group = displayio.Group()
    main_group.append(animation_group)

    start_time = time.monotonic()
    sparks = []

    for i in range(burst_count):
        cx = random.randint(8, WIDTH - 8)
        cy = random.randint(6, HEIGHT // 2)
        base_color = random.choice(firework_colors)
        launch_delay = i * 0.1

        for _ in range(sparks_per_burst):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1.5, 3.0)
            dx = speed * math.cos(angle)
            dy = speed * math.sin(angle) - 2.0

            bmp = displayio.Bitmap(1, 1, 1)
            pal = displayio.Palette(1)
            pal[0] = base_color
            pixel = displayio.TileGrid(bmp, pixel_shader=pal, x=cx, y=cy)

            sparks.append(
                {
                    "sprite": pixel,
                    "x": float(cx),
                    "y": float(cy),
                    "dx": dx,
                    "dy": dy,
                    "life": random.randint(15, 25),
                    "color": base_color,
                    "delay": launch_delay,
                }
            )
            animation_group.append(pixel)

    gravity = 0.15

    while time.monotonic() - start_time < duration + 1:
        t = time.monotonic() - start_time
        for spark in sparks:
            if t < spark["delay"]:
                continue

            if spark["life"] <= 0:
                if spark["sprite"] in animation_group:
                    animation_group.remove(spark["sprite"])
                continue

            spark["x"] += spark["dx"]
            spark["y"] += spark["dy"]
            spark["dy"] += gravity
            spark["life"] -= 1

            spark["sprite"].x = int(spark["x"])
            spark["sprite"].y = int(spark["y"])

            fade = spark["life"] / 25
            r = int(((spark["color"] >> 16) & 0xFF) * fade)
            g = int(((spark["color"] >> 8) & 0xFF) * fade)
            b = int((spark["color"] & 0xFF) * fade)
            spark["sprite"].pixel_shader[0] = (r << 16) | (g << 8) | b

        time.sleep(0.05)

    main_group.remove(animation_group)
    gc.collect()


print("*** Running Pico HUB75 Code! ***")

# === Main Loop ===
while True:
    fireworks_animation(duration=2.5, burst_count=3, sparks_per_burst=40)
    for i, (msg1, msg2, logo_path, *optional_color) in enumerate(messages):
        try:
            gc.collect()

            # Handle callable messages (time display)
            if callable(msg1):
                msg1 = msg1()

            color = optional_color[0] if optional_color else None
            scroll_group, content_width = create_scroll_group(
                logo_path, msg1, msg2, color
            )
            scroll_group.x = WIDTH
            main_group.append(scroll_group)

            # while scroll_group.x > -content_width - 1:
            while scroll_group.x > -content_width - 32:
                scroll_group.x -= SCROLL_STEP
                time.sleep(SCROLL_DELAY)

            main_group.remove(scroll_group)
            gc.collect()
            time.sleep(0.5)

        except MemoryError:
            print("\U0001f4a5 MemoryError! Trying to recover...")
            main_group = displayio.Group()
            display.root_group = main_group
            gc.collect()
            time.sleep(1)
