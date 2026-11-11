"""Settings and calibration, stored as one JSON file."""
import copy
import json
import os
import threading

DEFAULT_PATH = os.path.expanduser("~/.config/look-mouse/config.json")

DEFAULTS = {
    # Windows desktop layout in real pixels (Settings > System > Display).
    # x, y are each screen's top-left corner relative to the primary screen's top-left.
    "monitors": [
        {"name": "Left (portrait)", "x": -1080, "y": -420, "w": 1080, "h": 1920, "primary": False},
        {"name": "Centre", "x": 0, "y": 0, "w": 1920, "h": 1080, "primary": True},
        {"name": "Right", "x": 1920, "y": 0, "w": 1920, "h": 1080, "primary": False},
    ],
    "pointer": {
        # "desktop": the absolute pointer spans every screen.
        # "primary": it only spans the primary screen; other screens are reached with relative moves.
        "mode": "desktop",
        "rel_px_per_count": 1.0,
        "rel_chunk": 20,
    },
    "trigger": {
        "lock_key": "scroll",   # scroll | caps | num
        "restore": True,        # press the lock key back off after each trigger
        "gpio_pin": None,       # optional push button on this BCM pin
    },
    "behaviour": {
        "precision": "gaze",    # "gaze": jump to the estimated point; "centre": jump to the screen's centre
        "use_eyes": True,       # include eye direction, not just head direction
        "window": 8,            # number of recent frames averaged for each estimate
    },
    "camera": {"source": "auto", "index": 0, "width": 640, "height": 480, "flip": False},
    # Optional glasses-mounted camera looking at one eye (see docs/glasses.md).
    "eye_camera": {"enabled": False, "source": "", "threshold": 25, "flip": False},
    # Whether the saved calibration was made with the glasses camera ("glasses") or without ("webcam").
    "calibration_source": None,
    # monitor index (as a string) -> list of {"f": [head yaw, head pitch, eye across, eye up/down], "u": 0..1, "v": 0..1}
    "calibration": {},
}


def merge(base, patch):
    """Recursively overlay patch on base. Lists and scalars are replaced whole."""
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict) and key != "calibration":
            merge(base[key], value)
        else:
            base[key] = value
    return base


class Config:
    def __init__(self, path=DEFAULT_PATH):
        self.path = path
        self.lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULTS)
        if path and os.path.exists(path):
            with open(path) as f:
                merge(self.data, json.load(f))

    def update(self, patch):
        with self.lock:
            merge(self.data, patch)
            n = len(self.data["monitors"])
            cal = self.data["calibration"]
            for key in [k for k in cal if int(k) >= n]:
                del cal[key]
            self.save()

    def save(self):
        if not self.path:
            return
        with self.lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
