#!/usr/bin/env python3
"""Step 1 test: where does Windows put an absolute pointer, and can the Pi hear Scroll Lock?

  python3 test_pointer.py sweep    cursor visits 5 positions, 3 s each; note which screen(s) it lands on
  python3 test_pointer.py listen   prints a line every time Scroll Lock is toggled on the main keyboard
  python3 test_pointer.py jump     Scroll Lock toggles jump the cursor to the centre of the pointer's range
"""
import struct
import sys
import time

POINTER = "/dev/hidg0"
KEYBOARD = "/dev/hidg1"
SCROLL_LOCK = 0x04  # bit 2 of the LED byte (bit 0 Num Lock, bit 1 Caps Lock)


def move(fx, fy):
    """Jump to a position given as fractions (0..1) of the pointer's full range."""
    x, y = int(fx * 32767), int(fy * 32767)
    with open(POINTER, "wb") as f:
        f.write(struct.pack("<BHH", 0, x, y))


def scroll_lock_toggles():
    """Yield once per Scroll Lock change reported by the main computer."""
    last = None
    with open(KEYBOARD, "rb", buffering=0) as f:
        while True:
            state = f.read(1)[0] & SCROLL_LOCK
            if last is not None and state != last:
                yield
            last = state


def sweep():
    spots = [("centre", .5, .5), ("top-left", .02, .02), ("top-right", .98, .02),
             ("bottom-right", .98, .98), ("bottom-left", .02, .98)]
    for name, fx, fy in spots:
        print(f"{name:13s} -> which screen is the cursor on?")
        move(fx, fy)
        time.sleep(3)


def listen():
    print("Press Scroll Lock on the main keyboard (Ctrl+C to stop)")
    for _ in scroll_lock_toggles():
        print("toggle heard")


def jump():
    print("Each Scroll Lock press jumps the cursor (Ctrl+C to stop)")
    for _ in scroll_lock_toggles():
        move(.5, .5)


if __name__ == "__main__":
    {"sweep": sweep, "listen": listen, "jump": jump}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
