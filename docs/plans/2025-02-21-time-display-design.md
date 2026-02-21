# Time Display Feature Design

**Date**: 2025-02-21
**Author**: Design Document
**Status**: Approved

## Overview

Add a time display feature to the LED matrix that shows current date and time in a scrolling format, replacing the existing static messages while keeping the fireworks animation between displays.

## Requirements

- **Time Format**: "Mon Feb 21 10:30" (Day Month Date Hour:Minute)
- **Time Source**: Manual (hardcoded in code), updated via RTC
- **Display Mode**: Scrolling time message, replaces predefined messages and icons
- **Animation**: Keep fireworks animation between time displays
- **Hardware**: Raspberry Pi Pico with 64x64 LED matrix

## Architecture

### Integration Approach

The time display integrates into the existing scrolling message system using **Appro 1: Simple String Format**. The time is treated as just another message in the `messages` list, leveraging all existing scrolling and display logic.

### Data Flow

```
main loop
    ↓
get_time_string() generates formatted time
    ↓
create_scroll_group(time_string, "", None, None) creates display group
    ↓
scroll animation (existing logic)
    ↓
fireworks_animation() (existing logic)
    ↓
repeat with updated time
```

### Time Source

- Manual time setting via `rtc.RTC().datetime`
- Initial time hardcoded in code
- Clock runs independently once set
- No network sync or external dependencies

## Implementation Details

### New Code Components

#### 1. Import RTC Module
```python
import rtc
```

#### 2. Set Initial Time
```python
# === Set Initial Time ===
current_time = time.struct_time((2025, 2, 21, 10, 30, 0, 0, -1, -1))
rtc.RTC().datetime = current_time
```

#### 3. Time Formatter Function
```python
def get_time_string():
    t = time.localtime()
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    day_name = days[t.tm_wday]
    month_name = months[t.tm_mon - 1]

    return f"{day_name} {month_name} {t.tm_mday} {t.tm_hour:02d}:{t.tm_min:02d}"
```

#### 4. Updated Messages List
```python
messages = [
    (get_time_string, "", None, None),  # Time display as callable
]
```

**Note**: The first message element changes from a string to a callable function. This requires a small modification in the main loop to evaluate callables.

### Main Loop Modification

The main loop needs to check if a message is callable and evaluate it:

```python
while True:
    fireworks_animation(duration=2.5, burst_count=3, sparks_per_burst=40)

    for msg1, msg2, logo_path, *optional_color in messages:
        try:
            gc.collect()

            # Handle callable messages (time display)
            if callable(msg1):
                msg1 = msg1()

            color = optional_color[0] if optional_color else None
            scroll_group, content_width = create_scroll_group(logo_path, msg1, msg2, color)
            # ... rest of scrolling logic
```

## Display Behavior

- Time message scrolls left-to-right like other messages
- Time updates once per display cycle (every ~10-15 seconds)
- No icons displayed with time (logo_path = None)
- After time completes scrolling, fireworks animation plays
- Then time displays again with updated current time
- Continuous cycle: time → fireworks → time → fireworks...

## Memory Management

- Time string generated once per cycle (not continuously)
- Uses same memory footprint as other messages
- No additional display objects needed
- Existing `gc.collect()` calls remain in place
- Function call overhead is negligible

## Error Handling

- Existing try-except blocks for MemoryError recovery remain
- Time formatting uses standard library functions (no new error sources)
- RTC setting is done once at startup (low risk)

## Testing

**On Hardware**:
1. Upload modified `code.py` to CIRCUITPY drive
2. Observe time scrolls across display
3. Verify format matches "Mon Feb 21 10:30"
4. Confirm time updates on each cycle
5. Verify fireworks still play between displays
6. Check memory stability over extended run (1+ hour)

**Manual Time Adjustment**:
1. Edit hardcoded time in code
2. Re-upload to CIRCUITPY
3. Verify display shows new time

## Future Considerations

- **RTC with manual set**: Could add initial setup via USB console
- **Network time sync**: Only possible with MatrixPortal S3 + WiFi
- **Dynamic time formats**: Easy to change `get_time_string()` return format
- **Multiple time displays**: Could add different formats as separate messages

## Files Modified

- `code.py`: Main implementation file
  - Add imports (rtc)
  - Add time setup (~2 lines)
  - Add `get_time_string()` function (~15 lines)
  - Modify messages list (1 line)
  - Update main loop to handle callables (~3 lines)

**Total estimated changes**: ~21 lines of new/modified code

## Success Criteria

- [ ] Time displays in format "Mon Feb 21 10:30"
- [ ] Time updates on each display cycle
- [ ] Scrolling works identically to previous messages
- [ ] Fireworks animation plays between time displays
- [ ] No memory errors or crashes after extended use
- [ ] Manual time adjustment works correctly
