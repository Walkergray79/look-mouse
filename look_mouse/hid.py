"""USB output to the main computer, and the lock-key listener.

The Pi appears as three ordinary devices (see scripts/setup_gadget.sh):
  /dev/hidg0  absolute pointer   "jump to X,Y"
  /dev/hidg1  keyboard           hears lock-key changes; taps the lock key back off
  /dev/hidg2  relative mouse     used only when the absolute pointer can't reach a screen
"""
import queue
import struct
import threading
import time

LOCK_KEYS = {"num": (0x01, 0x53), "caps": (0x02, 0x39), "scroll": (0x04, 0x47)}  # LED bit, key code


class HidLink:
    def __init__(self, pointer="/dev/hidg0", keyboard="/dev/hidg1", mouse="/dev/hidg2"):
        self.paths = {"pointer": pointer, "keyboard": keyboard, "mouse": mouse}
        self.error = None

    def _write(self, which, *reports):
        try:
            with open(self.paths[which], "wb", buffering=0) as f:
                for r in reports:
                    f.write(r)
                    time.sleep(0.004)
            self.error = None
            return True
        except OSError as e:
            self.error = f"{self.paths[which]}: {e.strerror or e}"
            return False

    def absolute(self, fx, fy):
        """Jump to a point given as fractions (0..1) of the absolute pointer's range."""
        x = int(min(1.0, max(0.0, fx)) * 32767)
        y = int(min(1.0, max(0.0, fy)) * 32767)
        return self._write("pointer", struct.pack("<BHH", 0, x, y))

    def relative(self, dx, dy, chunk=20):
        """Move by a number of mouse counts, horizontally first, then vertically."""
        reports = []
        for ax, total in ((0, int(round(dx))), (1, int(round(dy)))):
            while total:
                step = max(-chunk, min(chunk, total))
                total -= step
                reports.append(struct.pack("<Bbb", 0, step if ax == 0 else 0, step if ax == 1 else 0))
        return self._write("mouse", *reports) if reports else True

    def tap_key(self, code):
        return self._write("keyboard", bytes([0, 0, code, 0, 0, 0, 0, 0]), bytes(8))

    def read_leds(self):
        """Block until the main computer reports a lock-key change; return the LED byte."""
        with open(self.paths["keyboard"], "rb", buffering=0) as f:
            return f.read(1)[0]


class FakeLink:
    """Stands in for the USB link in simulation and tests. Records everything sent."""

    def __init__(self):
        self.events = []
        self.error = None
        self.leds = queue.Queue()

    def absolute(self, fx, fy):
        self.events.append(("abs", round(fx, 4), round(fy, 4)))
        return True

    def relative(self, dx, dy, chunk=20):
        self.events.append(("rel", int(round(dx)), int(round(dy))))
        return True

    def tap_key(self, code):
        self.events.append(("key", code))
        return True

    def read_leds(self):
        return self.leds.get()


class Pointer:
    """Converts a desktop pixel position into whatever the USB link needs to send."""

    def __init__(self, link, config):
        self.link = link
        self.config = config

    def move_to(self, x, y):
        cfg = self.config.data
        mons = cfg["monitors"]
        if cfg["pointer"]["mode"] == "desktop":
            x0 = min(m["x"] for m in mons)
            y0 = min(m["y"] for m in mons)
            x1 = max(m["x"] + m["w"] for m in mons)
            y1 = max(m["y"] + m["h"] for m in mons)
            return self.link.absolute((x - x0) / (x1 - x0 - 1), (y - y0) / (y1 - y0 - 1))

        p = next((m for m in mons if m.get("primary")), mons[0])
        ax = min(p["x"] + p["w"] - 3, max(p["x"] + 2, x))
        ay = min(p["y"] + p["h"] - 3, max(p["y"] + 2, y))
        ok = self.link.absolute((ax - p["x"]) / (p["w"] - 1), (ay - p["y"]) / (p["h"] - 1))
        if ok and (ax, ay) != (x, y):
            time.sleep(0.03)
            scale = cfg["pointer"]["rel_px_per_count"] or 1.0
            ok = self.link.relative((x - ax) / scale, (y - ay) / scale, cfg["pointer"]["rel_chunk"])
        return ok


class LockKeyListener(threading.Thread):
    """Calls on_trigger when the chosen lock key is pressed on the main computer's keyboard."""

    def __init__(self, link, config, on_trigger):
        super().__init__(daemon=True)
        self.link, self.config, self.on_trigger = link, config, on_trigger
        self.started_at = time.monotonic()
        self.prev = None

    def handle(self, leds):
        trig = self.config.data["trigger"]
        bit, code = LOCK_KEYS.get(trig["lock_key"], LOCK_KEYS["scroll"])
        on = bool(leds & bit)
        if trig["restore"]:
            # Only "turned on" counts; we then turn it straight back off ourselves.
            if on:
                if time.monotonic() - self.started_at > 2.0:
                    self.on_trigger()
                self.link.tap_key(code)
        elif self.prev is not None and on != self.prev:
            self.on_trigger()
        self.prev = on

    def run(self):
        while True:
            try:
                self.handle(self.link.read_leds())
            except OSError:
                time.sleep(1.0)
