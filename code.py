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
import rtc
from adafruit_requests import Session
import socketpool
import adafruit_ntp

# NTP sync tracking
last_ntp_sync = 0
ntp_retry_active = False
ntp_retry_time = 0
STARTUP_RETRY_DELAY = 10

# Display mode: "setup" = full-screen multi-line log, "clock" = bottom-quarter single line
display_mode = "setup"
status_history = []
STATUS_HISTORY_MAX = 5
STATUS_DIM = 0x888888


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
    """Display status message on LED matrix.

    In "setup" mode: shows a multi-line status log on the full screen
    (newest at top in white, history below in dim gray).
    In "clock" mode: shows a single truncated line in the bottom quarter
    (y=48) to avoid covering the clock display.
    """
    global main_group, status_history
    print(message)

    # Track history for setup-mode log
    status_history.append(message)
    status_history = status_history[-STATUS_HISTORY_MAX:]

    # Clear main group by creating a new one
    main_group = displayio.Group()
    display.root_group = main_group

    max_chars = 14

    try:
        if display_mode == "setup":
            # Full screen: show status history log, newest at top
            line_spacing = 12
            y_start = 6
            for i, msg in enumerate(reversed(status_history)):
                y = y_start + (i * line_spacing)
                if y >= 64:
                    break

                if len(msg) > max_chars:
                    display_msg = msg[: max_chars - 3] + "..."
                else:
                    display_msg = msg

                color = WHITE if i == 0 else STATUS_DIM
                label = Label(font_small, text=display_msg, color=color, x=2, y=y)
                main_group.append(label)
        else:
            # Clock mode: single line in bottom quarter only
            if len(message) > max_chars:
                display_message = message[: max_chars - 3] + "..."
            else:
                display_message = message

            status_label = Label(
                font_small, text=display_message, color=WHITE, x=2, y=48
            )
            main_group.append(status_label)

        display.refresh()
    except Exception as e:
        print(f"✗ Display error: {e}")

    gc.collect()


def connect_wifi(ssid, password):
    """Connect to WiFi and return (ip_address, requests) tuple or None on failure."""
    display_status("Connecting...")
    time.sleep(1)

    try:
        # Validate inputs
        if not ssid or not password:
            print("✗ Connection failed: ssid and password required")
            display_status("WiFi failed")
            return None

        # Connect to network
        print(f"Connecting to {ssid}...")
        wifi.radio.connect(ssid, password)

        # Wait for connection (max 10 seconds)
        timeout = time.monotonic() + 10
        while not wifi.radio.connected and time.monotonic() < timeout:
            time.sleep(0.1)

        if not wifi.radio.connected:
            print(f"✗ Connection failed: timeout after 10s")
            display_status("WiFi failed")
            return None

        # Get IP address
        ip_address = wifi.radio.ipv4_address
        print(f"✓ Connected, my IP is {ip_address}")
        display_status(f"Connected: {ip_address}")
        time.sleep(1)  # Show success message for 1 second

        # Create socket pool for requests
        pool = socketpool.SocketPool(wifi.radio)
        requests = Session(pool)
        gc.collect()

        return ip_address, requests

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        display_status("WiFi failed")
        return None


def sync_ntp(server, show_status=True):
    """Sync time from NTP server and return struct_time or None on failure."""
    if show_status:
        print(f"Setup: syncing NTP from {server}...")
    else:
        print(f"Syncing NTP from {server}...")
    if show_status:
        display_status("Syncing...")

    try:
        # Create socket pool for NTP
        pool = socketpool.SocketPool(wifi.radio)

        # Create NTP client (tz_offset=0 means UTC)
        ntp = adafruit_ntp.NTP(pool, server=server, tz_offset=0)

        # Get NTP time as struct_time
        ntp_time = ntp.datetime

        # Convert to Unix timestamp for drift calculation
        # time.mktime() converts struct_time to Unix timestamp
        unix_timestamp = time.mktime(ntp_time)

        print(f"✓ NTP sync successful")
        return ntp_time, unix_timestamp

    except Exception as e:
        print(f"✗ NTP sync failed: {e}")
        if show_status:
            display_status("NTP failed")
        return None, None


def retry_wifi_until_connected(ssid, password, retry_delay=STARTUP_RETRY_DELAY):
    """Retry WiFi connection until successful, returning (ip_address, requests)."""
    while True:
        result = connect_wifi(ssid, password)
        if result is not None:
            return result

        print(f"WiFi connection failed, retrying in {retry_delay} seconds")
        display_status(f"WiFi retry {retry_delay}s")
        time.sleep(retry_delay)
        gc.collect()


def retry_ntp_until_synced(server, ssid, password, retry_delay=STARTUP_RETRY_DELAY):
    """Retry NTP sync until successful, returning (ntp_time, ntp_unix, refreshed_requests)."""
    refreshed_requests = None

    while True:
        if not wifi.radio.connected:
            print("WiFi disconnected before NTP sync, reconnecting...")
            display_status(f"WiFi retry {retry_delay}s")
            ip_address, refreshed_requests = retry_wifi_until_connected(
                ssid, password, retry_delay
            )

        ntp_time, ntp_unix = sync_ntp(server)
        if ntp_time is not None:
            return ntp_time, ntp_unix, refreshed_requests

        print(f"NTP sync failed, retrying in {retry_delay} seconds")
        display_status(f"NTP retry {retry_delay}s")
        time.sleep(retry_delay)
        gc.collect()


def apply_timezone(unix_timestamp, offset_hours):
    """Apply timezone offset to UTC Unix timestamp.

    Converts a UTC Unix timestamp to local time by applying timezone offset.

    Args:
        unix_timestamp: Unix timestamp (seconds since epoch, UTC)
        offset_hours: Timezone offset in hours (e.g., 8 for UTC+8)

    Returns:
        struct_time: Local time as struct_time object
    """
    # Validate offset_hours
    if not isinstance(offset_hours, (int, float)):
        raise TypeError(f"offset_hours must be numeric, got {type(offset_hours)}")

    if offset_hours < -12 or offset_hours > 14:
        raise ValueError(
            f"offset_hours must be between -12 and +14, got {offset_hours}"
        )

    # Apply offset (convert hours to seconds)
    offset_seconds = int(offset_hours * 3600)
    local_ts = unix_timestamp + offset_seconds

    # Convert to struct_time (use localtime since gmtime doesn't exist in CircuitPython)
    return time.localtime(local_ts)


def calculate_drift(rtc_unix_timestamp, ntp_unix_timestamp):
    """Calculate time drift in seconds between RTC and NTP time.

    Args:
        rtc_unix_timestamp: RTC time as Unix timestamp (seconds since epoch)
        ntp_unix_timestamp: NTP time as Unix timestamp (seconds since epoch)

    Returns:
        int: Drift in seconds (positive = NTP ahead of RTC)
    """
    return ntp_unix_timestamp - rtc_unix_timestamp


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

    # Connect to WiFi, retrying transient failures forever
    ip_address, requests = retry_wifi_until_connected(wifi_ssid, wifi_password)
    gc.collect()

    # Sync NTP, retrying transient failures forever
    ntp_time, ntp_unix, refreshed_requests = retry_ntp_until_synced(
        ntp_server, wifi_ssid, wifi_password
    )
    if refreshed_requests is not None:
        requests = refreshed_requests
    gc.collect()

    # Calculate drift
    current_rtc_time = time.localtime()
    rtc_unix = int(time.mktime(current_rtc_time))
    drift = calculate_drift(rtc_unix, ntp_unix)
    print(f"Sync time via NTP, {drift:.3f}s drifted")

    # Apply timezone
    local_time = apply_timezone(ntp_unix, offset_hours)

    # Update RTC
    rtc.RTC().datetime = local_time
    gc.collect()

    # Set last NTP sync time
    last_ntp_sync = time.monotonic()

    # Ready to start
    display_status("Ready!")
    time.sleep(2)
    display_status("")

    return config, requests, offset_hours, ntp_server


def attempt_ntp_sync(ntp_server, timezone_offset, show_status=True):
    """Attempt NTP sync, return True on success, False on failure."""
    global last_ntp_sync

    try:
        # Sync NTP
        ntp_time, ntp_unix = sync_ntp(ntp_server, show_status)
        if ntp_time is None:
            return False

        # Convert current_rtc_time to Unix timestamp
        current_rtc_time = time.localtime()
        rtc_unix = int(time.mktime(current_rtc_time))

        # Calculate drift
        drift = calculate_drift(rtc_unix, ntp_unix)
        print(f"Sync time via NTP, {drift:.3f}s drifted")

        # Apply timezone and update RTC
        local_time = apply_timezone(ntp_unix, timezone_offset)
        rtc.RTC().datetime = local_time

        if show_status:
            display_status("Time synced")
            time.sleep(1)

        # Update last NTP sync time
        last_ntp_sync = time.monotonic()

        gc.collect()
        return True

    except Exception as e:
        print(f"✗ NTP sync failed: {e}")
        if show_status:
            display_status("NTP retry...")
        return False


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

# === Firework Constants ===
FIREWORK_POOL_SIZE = 48
FIREWORK_BURST_INTERVAL = 1.2
FIREWORK_DIM_DIVISOR = 4

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


def dim_color(color):
    r = ((color >> 16) & 0xFF) // FIREWORK_DIM_DIVISOR
    g = ((color >> 8) & 0xFF) // FIREWORK_DIM_DIVISOR
    b = (color & 0xFF) // FIREWORK_DIM_DIVISOR
    return (r << 16) | (g << 8) | b


# Lean firework colors toward warm tones
firework_colors = [WHITE, GOLDENROD, WARM_GOLD, DEEP_CORAL, SOFT_RED, TANGERINE]
dim_firework_colors = [dim_color(c) for c in firework_colors]

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
SCROLL_STEP = 1
STATIC_MESSAGE_SECONDS = 5

# === Layout Constants ===
TOP_BAND_Y = 0
TOP_BAND_HEIGHT = 16
CLOCK_BAND_Y = 16
CLOCK_BAND_HEIGHT = 32
MESSAGE_BAND_Y = 48
MESSAGE_BAND_HEIGHT = 16
FRAME_DELAY = 0.05

# === NTP Sync Settings ===
NTP_INTERVAL = 600  # Sync time every 10 minutes
NTP_RETRY_DELAY = 60  # Wait 60 seconds before retrying failed NTP sync

# === Clock Bitmap Renderer ===
CLOCK_DIGIT_GLYPHS = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    ":": ["000", "010", "000", "010", "000"],
}

CLOCK_DIGIT_SCALE = 4
CLOCK_DIGIT_GAP = 1
CLOCK_COLOR = WARM_GOLD
CLOCK_BACKGROUND_INDEX = 0
CLOCK_FOREGROUND_INDEX = 1
CLOCK_TEXT_START_X = 4
CLOCK_TEXT_START_Y = 6


def create_clock_bitmap():
    clock_bitmap = displayio.Bitmap(WIDTH, CLOCK_BAND_HEIGHT, 2)
    clock_palette = displayio.Palette(2)
    clock_palette[CLOCK_BACKGROUND_INDEX] = 0x000000
    clock_palette[CLOCK_FOREGROUND_INDEX] = CLOCK_COLOR
    clock_palette.make_transparent(CLOCK_BACKGROUND_INDEX)
    clock_tilegrid = displayio.TileGrid(
        clock_bitmap,
        pixel_shader=clock_palette,
        x=0,
        y=CLOCK_BAND_Y,
    )
    return clock_bitmap, clock_palette, clock_tilegrid


def clear_clock_bitmap(clock_bitmap):
    for y in range(CLOCK_BAND_HEIGHT):
        for x in range(WIDTH):
            clock_bitmap[x, y] = CLOCK_BACKGROUND_INDEX


def draw_scaled_cell(clock_bitmap, x, y, scale):
    for cell_y in range(scale):
        for cell_x in range(scale):
            clock_bitmap[x + cell_x, y + cell_y] = CLOCK_FOREGROUND_INDEX


def draw_clock_text(clock_bitmap, text):
    clear_clock_bitmap(clock_bitmap)
    x = CLOCK_TEXT_START_X

    for char in text[:5]:
        glyph = CLOCK_DIGIT_GLYPHS.get(char)
        if glyph is None:
            x += (3 * CLOCK_DIGIT_SCALE) + CLOCK_DIGIT_GAP
            continue

        if char == ":":
            for glyph_row in (1, 3):
                draw_scaled_cell(
                    clock_bitmap,
                    x,
                    CLOCK_TEXT_START_Y + (glyph_row * CLOCK_DIGIT_SCALE),
                    CLOCK_DIGIT_SCALE,
                )
            x += CLOCK_DIGIT_SCALE
        else:
            for glyph_row, row in enumerate(glyph):
                for glyph_col, pixel in enumerate(row):
                    if pixel == "1":
                        draw_scaled_cell(
                            clock_bitmap,
                            x + (glyph_col * CLOCK_DIGIT_SCALE),
                            CLOCK_TEXT_START_Y + (glyph_row * CLOCK_DIGIT_SCALE),
                            CLOCK_DIGIT_SCALE,
                        )
            x += 3 * CLOCK_DIGIT_SCALE

        x += CLOCK_DIGIT_GAP


clock_bitmap, clock_palette, clock_tilegrid = create_clock_bitmap()


def get_date_string():
    """Generate formatted date string: 'Mon Feb 21'"""
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

    return f"{day_name} {month_name} {t.tm_mday}"


def get_time_string():
    """Generate formatted time string: 'HH:MM'"""
    t = time.localtime()
    return f"{t.tm_hour:02d}:{t.tm_min:02d}"


def get_full_time_string():
    """Generate formatted date and time string: 'Mon Feb 21 10:30'"""
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


def _create_positioned_label(text, color=None):
    """Create a label with proper color and vertical centering in y=48..63 band.

    Internal helper for label creation. Lit pixels are vertically centered
    within the 16px band.

    Args:
        text: String text to display
        color: Optional color (defaults to random celebration color if None)

    Returns:
        Label: Positioned label ready to append to a group
    """
    label_color = color if color is not None else random.choice(celebration_colors)
    label = Label(font_small, text=text, color=label_color)

    # Position label to vertically center lit pixels within y=48..63 band
    label.y = MESSAGE_BAND_Y - label.bounding_box[1] + (MESSAGE_BAND_HEIGHT - label.bounding_box[3]) // 2

    return label


def create_message_group(text, color=None):
    """Create a displayio.Group with a label positioned in y=48..63 band.

    The label is positioned with absolute bottom-band coordinates. The returned
    group can be directly appended to main_group without extra y-offsets.

    Lit pixels are vertically centered within the 16px band.

    Args:
        text: String text to display
        color: Optional color (defaults to random celebration color if None)

    Returns:
        displayio.Group: Group with a positioned label child
    """
    group = displayio.Group()
    label = _create_positioned_label(text, color)
    group.append(label)

    return group


def message_fits(label):
    """Check if label fits within display width.

    Args:
        label: A Label object with a bounding_box attribute

    Returns:
        bool: True if label width <= WIDTH, False otherwise
    """
    return label.bounding_box[2] <= WIDTH


def init_message_state(messages=None):
    """Initialize message state for bottom-band display.

    Args:
        messages: Optional list of message tuples (msg1, msg2, logo_path, optional_color).
                  Defaults to module-level messages list if not provided.

    Returns:
        dict: Message state with keys:
            - messages: The messages list
            - msg_index: Current message index (0-based)
            - msg_group: Persistent displayio.Group (never swapped)
            - msg_label: Current Label within group
            - msg_fits: Boolean, whether current message fits in width
            - msg_display_time: When current message was first displayed (monotonic time)
    """
    if messages is None:
        messages = globals().get("messages", [])

    if not messages:
        empty_group = displayio.Group()
        return {
            "messages": [],
            "msg_index": 0,
            "msg_group": empty_group,
            "msg_label": None,
            "msg_fits": True,
            "msg_display_time": time.monotonic(),
        }

    # Get first message
    msg1, msg2, logo_path, *optional_color = messages[0]

    # Skip logo if present
    if logo_path:
        print(f"Skipping logo in 16px message band: {logo_path}")

    # Resolve callable messages
    if callable(msg1):
        msg1 = msg1()

    # Create persistent group and label
    color = optional_color[0] if optional_color else None
    msg_group = create_message_group(msg1, color)
    msg_label = msg_group[0]  # Get the label child

    # Determine if message fits
    fits = message_fits(msg_label)

    # Position label
    if fits:
        # Center horizontally
        msg_label.x = (WIDTH - msg_label.bounding_box[2]) // 2
        # y already positioned by create_message_group() using bounding-box offset
    else:
        # Start at right edge for scrolling
        msg_label.x = WIDTH
        # y already positioned by create_message_group() using bounding-box offset

    state = {
        "messages": messages,
        "msg_index": 0,
        "msg_group": msg_group,
        "msg_label": msg_label,
        "msg_fits": fits,
        "msg_display_time": time.monotonic(),
    }

    return state


def step_message(message_state, now):
    """Step message state, advancing to next message when current completes.

    Keeps the persistent group object and mutates its child label on advance.

    Args:
        message_state: dict from init_message_state()
        now: Current monotonic time

    Returns:
        bool: True if message group should remain displayed, False if completed
    """
    if not message_state["messages"]:
        return True

    msg_fits = message_state["msg_fits"]
    msg_label = message_state["msg_label"]
    msg_group = message_state["msg_group"]

    if msg_fits:
        # Static message: check display duration
        display_duration = now - message_state["msg_display_time"]
        if display_duration >= STATIC_MESSAGE_SECONDS:
            # Advance to next message
            message_state["msg_index"] += 1
            if message_state["msg_index"] >= len(message_state["messages"]):
                return False

            # Setup next message by mutating the persistent group
            msg1, msg2, logo_path, *optional_color = message_state["messages"][message_state["msg_index"]]

            # Skip logo if present
            if logo_path:
                print(f"Skipping logo in 16px message band: {logo_path}")

            # Resolve callable messages
            if callable(msg1):
                msg1 = msg1()

            # Remove old label, create new one using helper for proper defaults
            msg_group.remove(msg_label)
            color = optional_color[0] if optional_color else None
            new_label = _create_positioned_label(msg1, color)
            msg_group.append(new_label)

            # Determine if message fits
            fits = message_fits(new_label)
            message_state["msg_fits"] = fits
            message_state["msg_label"] = new_label

            # Position label
            if fits:
                new_label.x = (WIDTH - new_label.bounding_box[2]) // 2
            else:
                new_label.x = WIDTH

            message_state["msg_display_time"] = now

        return True

    else:
        # Scrolling message: move left by SCROLL_STEP
        msg_label.x -= SCROLL_STEP

        # Check if scroll complete (x < -text_width)
        text_width = msg_label.bounding_box[2]
        if msg_label.x < -text_width:
            # Advance to next message
            message_state["msg_index"] += 1
            if message_state["msg_index"] >= len(message_state["messages"]):
                return False

            # Setup next message by mutating the persistent group
            msg1, msg2, logo_path, *optional_color = message_state["messages"][message_state["msg_index"]]

            # Skip logo if present
            if logo_path:
                print(f"Skipping logo in 16px message band: {logo_path}")

            # Resolve callable messages
            if callable(msg1):
                msg1 = msg1()

            # Remove old label, create new one using helper for proper defaults
            msg_group.remove(msg_label)
            color = optional_color[0] if optional_color else None
            new_label = _create_positioned_label(msg1, color)
            msg_group.append(new_label)

            # Determine if message fits
            fits = message_fits(new_label)
            message_state["msg_fits"] = fits
            message_state["msg_label"] = new_label

            # Position label
            if fits:
                new_label.x = (WIDTH - new_label.bounding_box[2]) // 2
            else:
                new_label.x = WIDTH

            message_state["msg_display_time"] = now

        return True


# === Messages: (text, unused, logo_path, optional_color)
# Only the first element (text) is displayed. Logos are skipped in the 16px band.
# You can add or remove elements from the messages list as you like.
messages = [
    ('->', '', None, WHITE),
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


def create_fireworks_state():
    fireworks_group = displayio.Group()
    sparks = []

    for _ in range(FIREWORK_POOL_SIZE):
        bitmap = displayio.Bitmap(1, 1, 1)
        palette = displayio.Palette(1)
        palette[0] = 0x000000
        sprite = displayio.TileGrid(bitmap, pixel_shader=palette, x=-1, y=-1)
        fireworks_group.append(sprite)
        sparks.append(
            {
                "sprite": sprite,
                "palette": palette,
                "x": -1.0,
                "y": -1.0,
                "dx": 0.0,
                "dy": 0.0,
                "life": 0,
                "active": False,
                "color": 0x000000,
            }
        )

    return {
        "group": fireworks_group,
        "sparks": sparks,
        "last_burst_time": 0,
        "next_spark_index": 0,
    }


def activate_spark(state, cx, cy, color):
    spark = state["sparks"][state["next_spark_index"]]
    state["next_spark_index"] = (state["next_spark_index"] + 1) % FIREWORK_POOL_SIZE

    angle = random.uniform(0, 2 * math.pi)
    speed = random.uniform(1.5, 3.0)
    spark["sprite"].x = cx
    spark["sprite"].y = cy
    spark["palette"][0] = color
    spark["x"] = float(cx)
    spark["y"] = float(cy)
    spark["dx"] = speed * math.cos(angle)
    spark["dy"] = speed * math.sin(angle) - 2.0
    spark["life"] = random.randint(15, 25)
    spark["active"] = True
    spark["color"] = color


def trigger_firework_burst(state):
    cx = random.randint(8, WIDTH - 8)
    cy = random.randint(6, HEIGHT // 2)
    color = random.choice(dim_firework_colors)

    for _ in range(12):
        activate_spark(state, cx, cy, color)


def step_fireworks(state, now):
    if now - state["last_burst_time"] >= FIREWORK_BURST_INTERVAL:
        trigger_firework_burst(state)
        state["last_burst_time"] = now

    for spark in state["sparks"]:
        if not spark["active"]:
            continue

        spark["x"] += spark["dx"]
        spark["y"] += spark["dy"]
        spark["dy"] += 0.15
        spark["life"] -= 1

        if spark["life"] <= 0:
            spark["sprite"].x = -1
            spark["sprite"].y = -1
            spark["active"] = False
            continue

        spark["sprite"].x = int(spark["x"])
        spark["sprite"].y = int(spark["y"])

        fade = spark["life"] / 25
        r = int(((spark["color"] >> 16) & 0xFF) * fade)
        g = int(((spark["color"] >> 8) & 0xFF) * fade)
        b = int((spark["color"] & 0xFF) * fade)
        spark["palette"][0] = (r << 16) | (g << 8) | b


def build_clock_scene():
    global main_group

    try:
        main_group.remove(clock_tilegrid)
    except Exception:
        pass

    main_group = displayio.Group()
    display.root_group = main_group

    fireworks_state = create_fireworks_state()
    main_group.append(fireworks_state["group"])

    date_label = Label(font_small, text=get_date_string(), color=WHITE)
    date_label.x = (WIDTH - date_label.bounding_box[2]) // 2
    date_label.y = TOP_BAND_Y - date_label.bounding_box[1] + (TOP_BAND_HEIGHT - date_label.bounding_box[3]) // 2
    main_group.append(date_label)

    draw_clock_text(clock_bitmap, get_time_string())
    main_group.append(clock_tilegrid)

    message_state = init_message_state()
    main_group.append(message_state["msg_group"])

    current_time = time.localtime()
    return {
        "fireworks": fireworks_state,
        "date_label": date_label,
        "last_date_day": current_time.tm_mday,
        "last_clock_minute": current_time.tm_min,
        "message": message_state,
        "frame_count": 0,
    }


def clear_clock_scene(state):
    if not state:
        return

    try:
        main_group.remove(state["message"]["msg_group"])
    except Exception:
        pass

    try:
        main_group.remove(clock_tilegrid)
    except Exception:
        pass

    try:
        main_group.remove(state["date_label"])
    except Exception:
        pass

    try:
        main_group.remove(state["fireworks"]["group"])
    except Exception:
        pass

    state.clear()


def update_date_label(state):
    current_time = time.localtime()
    if current_time.tm_mday == state["last_date_day"]:
        return

    label = state["date_label"]
    label.text = get_date_string()
    label.x = (WIDTH - label.bounding_box[2]) // 2
    label.y = TOP_BAND_Y - label.bounding_box[1] + (TOP_BAND_HEIGHT - label.bounding_box[3]) // 2
    state["last_date_day"] = current_time.tm_mday


def update_clock_bitmap(state):
    current_time = time.localtime()
    if current_time.tm_min == state["last_clock_minute"]:
        return


    draw_clock_text(clock_bitmap, get_time_string())
    state["last_clock_minute"] = current_time.tm_min


print("*** Running Pico HUB75 Code! ***")

# Setup WiFi and NTP
try:
    config, requests, timezone_offset, ntp_server = setup()
except Exception as e:
    print(f"✗ Setup failed: {e}")
    display_status("Setup failed")
    while True:
        time.sleep(1)  # Stop and wait

# Build persistent layered scene
gc.collect()  # Free memory from setup() before allocating scene objects
print(f"Free memory before scene build: {gc.mem_free()} bytes")
try:
    scene_state = build_clock_scene()
except Exception as e:
    print(f"✗ Scene build failed: {e}")
    import traceback
    traceback.print_exception(type(e), e, e.__traceback__)
    # Show error on LED matrix for diagnosis without serial console
    try:
        display_status(f"Err:{str(e)[:10]}")
    except Exception:
        pass
    while True:
        time.sleep(1)  # Stop and wait

# Clock scene is live — switch display to bottom-quarter-only mode
display_mode = "clock"

# === Main Loop ===
while True:
    try:
        current_time = time.monotonic()

        if ntp_retry_active:
            if current_time >= ntp_retry_time:
                success = attempt_ntp_sync(ntp_server, timezone_offset, show_status=False)
                if success:
                    ntp_retry_active = False
                else:
                    ntp_retry_time = current_time + NTP_RETRY_DELAY
        elif last_ntp_sync > 0 and current_time - last_ntp_sync >= NTP_INTERVAL:
            success = attempt_ntp_sync(ntp_server, timezone_offset, show_status=False)
            if not success:
                ntp_retry_active = True
                print(f"NTP sync failed, retrying in {NTP_RETRY_DELAY}s")
                ntp_retry_time = current_time + NTP_RETRY_DELAY

        step_fireworks(scene_state["fireworks"], current_time)
        update_clock_bitmap(scene_state)
        update_date_label(scene_state)
        if not step_message(scene_state["message"], current_time):
            main_group.remove(scene_state["message"]["msg_group"])
            scene_state["message"] = init_message_state()
            main_group.append(scene_state["message"]["msg_group"])

        scene_state["frame_count"] += 1
        if scene_state["frame_count"] >= 200:
            gc.collect()
            scene_state["frame_count"] = 0

        time.sleep(FRAME_DELAY)

    except MemoryError:
        print("\U0001f4a5 MemoryError! Trying to recover...")
        clear_clock_scene(scene_state)
        scene_state = None
        gc.collect()
        scene_state = build_clock_scene()
        time.sleep(1)
