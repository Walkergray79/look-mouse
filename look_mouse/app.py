"""The core: estimate where the user is looking, and jump the cursor there on a trigger."""
import statistics
import threading
import time

from .gaze import GazeModel
from .hid import Pointer


class App:
    def __init__(self, config, tracker, link):
        self.config = config
        self.tracker = tracker
        self.link = link
        self.pointer = Pointer(link, config)
        self.lock = threading.Lock()
        self.last_jump = None
        self.last_trigger = 0.0
        self._model = None
        self._model_key = None

    # ---- estimating ------------------------------------------------------------

    def features(self):
        frames = self.tracker.recent(self.config.data["behaviour"]["window_ms"] / 1000)
        if not frames:
            return None
        return [statistics.median(col) for col in zip(*frames)]

    def model(self):
        data = self.config.data
        key = (repr(data["calibration"]), data["behaviour"]["use_eyes"])
        if key != self._model_key:
            self._model = GazeModel(data["calibration"], data["behaviour"]["use_eyes"])
            self._model_key = key
        return self._model

    def gaze(self):
        f = self.features()
        return self.model().predict(f) if f else None

    def pixel(self, monitor, u, v):
        m = self.config.data["monitors"][monitor]
        return round(m["x"] + u * (m["w"] - 1)), round(m["y"] + v * (m["h"] - 1))

    # ---- actions ---------------------------------------------------------------

    def jump(self):
        """Move the cursor to where the user is looking. Called by every kind of trigger."""
        with self.lock:
            now = time.monotonic()
            if now - self.last_trigger < 0.25:
                return self.last_jump
            self.last_trigger = now
            result = {"time": time.time(), "ok": False}
            if self.features() is None:
                result["reason"] = "No face in view"
            else:
                g = self.gaze()
                if g is None or g["monitor"] >= len(self.config.data["monitors"]):
                    result["reason"] = "Not calibrated yet"
                else:
                    u, v = g["u"], g["v"]
                    if self.config.data["behaviour"]["precision"] == "centre" or not g["precise"]:
                        u = v = 0.5
                    x, y = self.pixel(g["monitor"], u, v)
                    result.update(monitor=g["monitor"], x=x, y=y, ok=self.pointer.move_to(x, y))
                    if not result["ok"]:
                        result["reason"] = "USB link to the main computer is down"
            self.last_jump = result
            return result

    def send_to(self, monitor, u=0.5, v=0.5):
        """Move the cursor to a chosen spot, ignoring the gaze. Used to check the pointer mapping."""
        x, y = self.pixel(monitor, u, v)
        return {"ok": self.pointer.move_to(x, y), "x": x, "y": y, "error": self.link.error}

    def nudge(self, counts):
        """Send a raw relative move, so the browser can measure pixels per count."""
        return {"ok": self.link.relative(counts, 0, self.config.data["pointer"]["rel_chunk"])}

    def add_sample(self, monitor, u, v):
        f = self.features()
        if f is None:
            return {"ok": False, "reason": "No face in view"}
        cal = dict(self.config.data["calibration"])
        cal[str(monitor)] = cal.get(str(monitor), []) + [{"f": [round(x, 5) for x in f], "u": u, "v": v}]
        self.config.update({"calibration": cal})
        return {"ok": True, "count": len(cal[str(monitor)])}

    def clear_samples(self, monitor=None):
        cal = {} if monitor is None else {k: v for k, v in self.config.data["calibration"].items()
                                         if k != str(monitor)}
        self.config.update({"calibration": cal})
        return {"ok": True}

    def diagnostics(self):
        """Everything behind one estimate, for the diagnostics view. Only computed when asked for."""
        f = self.features()
        rows = self.model().explain(f) if f else []
        g = self.model().predict(f, rows) if f else None
        if g and g["monitor"] >= len(self.config.data["monitors"]):
            g = None
        return {
            "features": f,
            "candidates": [{k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()} for r in rows],
            "chosen": g,
            "target": self.pixel(g["monitor"], g["u"], g["v"]) if g else None,
            "calibration": {k: [s["f"] for s in v] for k, v in self.config.data["calibration"].items()},
            "timing": {"fps": round(self.tracker.fps, 1), "process_ms": round(self.tracker.process_ms),
                       "age_ms": self.tracker.age_ms(), "window_ms": self.config.data["behaviour"]["window_ms"]},
        }

    def status(self):
        f = self.features()
        return {
            "simulated": self.tracker.simulated,
            "why": None if f else "No face in view",
            "face": f is not None,
            "features": f,
            "fps": round(self.tracker.fps, 1),
            "camera_error": self.tracker.error,
            "usb_error": self.link.error,
            "gaze": self.model().predict(f) if f else None,
            "samples": {k: len(v) for k, v in self.config.data["calibration"].items()},
            "last_jump": self.last_jump,
        }
