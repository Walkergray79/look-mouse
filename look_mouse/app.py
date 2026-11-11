"""The core: estimate where the user is looking, and jump the cursor there on a trigger."""
import statistics
import threading
import time

from .gaze import GazeModel
from .hid import Pointer


class App:
    def __init__(self, config, tracker, link, eye=None):
        self.config = config
        self.tracker = tracker
        self.eye = eye
        self.link = link
        self.why = None   # why there is currently no estimate
        self.pointer = Pointer(link, config)
        self.lock = threading.Lock()
        self.last_jump = None
        self.last_trigger = 0.0
        self._model = None
        self._model_key = None

    # ---- estimating ------------------------------------------------------------

    def eye_source(self):
        """Where the eye direction comes from: the glasses camera, or the desk camera's view of the eyes."""
        return "glasses" if self.eye and self.config.data["eye_camera"]["enabled"] else "webcam"

    def features(self):
        window = self.config.data["behaviour"]["window"]
        frames = self.tracker.recent(window)
        if not frames:
            self.why = "No face in view"
            return None
        f = [statistics.median(col) for col in zip(*frames)]
        if self.eye_source() == "glasses":
            # Head direction from the desk camera, eye direction from the glasses camera.
            pupils = self.eye.recent(window)
            if not pupils:
                self.why = "Glasses camera can't see your pupil"
                return None
            f[2], f[3] = (statistics.median(col) for col in zip(*pupils))
        return f

    def calibration_matches(self):
        made_with = self.config.data["calibration_source"]
        return not self.config.data["calibration"] or made_with in (None, self.eye_source())

    def model(self):
        data = self.config.data
        key = (repr(data["calibration"]), data["behaviour"]["use_eyes"])
        if key != self._model_key:
            self._model = GazeModel(data["calibration"], data["behaviour"]["use_eyes"])
            self._model_key = key
        return self._model

    def gaze(self, f=None):
        f = f or self.features()
        if f is None:
            return None
        if not self.calibration_matches():
            self.why = ("Calibrate again: the saved calibration was made "
                        + ("with" if self.eye_source() == "webcam" else "without") + " the glasses camera")
            return None
        g = self.model().predict(f)
        if g is None or g["monitor"] >= len(self.config.data["monitors"]):
            self.why = "Not calibrated yet"
            return None
        return g

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
            g = self.gaze()
            if g is None:
                result["reason"] = self.why
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
            return {"ok": False, "reason": self.why}
        if not self.calibration_matches():
            return {"ok": False, "reason": "Clear all calibration first: it was made "
                    + ("with" if self.eye_source() == "webcam" else "without") + " the glasses camera"}
        cal = dict(self.config.data["calibration"])
        cal[str(monitor)] = cal.get(str(monitor), []) + [{"f": [round(x, 5) for x in f], "u": u, "v": v}]
        self.config.update({"calibration": cal, "calibration_source": self.eye_source()})
        return {"ok": True, "count": len(cal[str(monitor)])}

    def clear_samples(self, monitor=None):
        cal = {} if monitor is None else {k: v for k, v in self.config.data["calibration"].items()
                                         if k != str(monitor)}
        self.config.update({"calibration": cal, **({} if cal else {"calibration_source": None})})
        return {"ok": True}

    def status(self):
        f = self.features()
        g = self.gaze(f) if f else None
        eye_cfg = self.config.data["eye_camera"]
        return {
            "why": None if g else self.why,
            "eye": {"enabled": eye_cfg["enabled"], "error": self.eye.error if self.eye else None,
                    "pupil": bool(self.eye and eye_cfg["enabled"] and self.eye.recent(3)),
                    "fps": round(self.eye.fps, 1) if self.eye else 0},
            "simulated": self.tracker.simulated,
            "face": f is not None,
            "features": f,
            "fps": round(self.tracker.fps, 1),
            "camera_error": self.tracker.error,
            "usb_error": self.link.error,
            "gaze": g,
            "samples": {k: len(v) for k, v in self.config.data["calibration"].items()},
            "last_jump": self.last_jump,
        }
