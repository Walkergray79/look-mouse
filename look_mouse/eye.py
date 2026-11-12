"""Optional glasses-mounted camera pointed at one eye.

Because the camera is fixed to your head, where the pupil sits in its picture says
which way the eye is turned within the head, far more finely than the desk camera can
see from a distance. The desk camera still supplies the head direction; the two are
combined in app.py.

Any camera OpenCV can open works: a small USB camera (give its number, e.g. "1") or a
wireless one that streams MJPEG (give its address, e.g. "http://192.168.1.50:81/stream").
"""
import collections
import math
import threading
import time


def detect_pupil(gray, offset=25, min_frac=0.002, max_frac=0.25):
    """Find the pupil in a greyscale eye image: the largest round, very dark blob.

    offset: how much brighter than the darkest part of the picture still counts as pupil.
    Returns {"x", "y" (0..1 across the picture), "ellipse", "confidence"} or None.
    """
    import cv2
    import numpy as np

    h, w = gray.shape[:2]
    blur = cv2.GaussianBlur(gray, (7, 7), 0)
    darkest = float(np.percentile(blur, 0.5))
    _, mask = cv2.threshold(blur, darkest + offset, 255, cv2.THRESH_BINARY_INV)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))   # drops eyelashes
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    best = None
    for c in contours:
        hull = cv2.convexHull(c)            # fills in the bright reflection of any light
        area = cv2.contourArea(hull)
        if len(hull) < 5 or not (min_frac * w * h <= area <= max_frac * w * h):
            continue
        x, y, bw, bh = cv2.boundingRect(hull)
        if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
            continue                        # dark picture corners, not a pupil
        roundness = 4 * math.pi * area / (cv2.arcLength(hull, True) ** 2)
        if roundness < 0.6:
            continue
        if best is None or area * roundness > best[0]:
            best = (area * roundness, hull, roundness)
    if best is None:
        return None
    ellipse = cv2.fitEllipse(best[1])
    (cx, cy) = ellipse[0]
    return {"x": cx / w, "y": cy / h, "ellipse": ellipse, "confidence": round(best[2], 3)}


class EyeTracker(threading.Thread):
    def __init__(self, config):
        super().__init__(daemon=True)
        self.config = config
        self.samples = collections.deque(maxlen=60)   # (time, [x, y])
        self.jpeg = None
        self.fps = 0.0
        self.process_ms = 0.0
        self.error = None
        self.preview_until = 0.0

    def settings(self):
        return self.config.data["eye_camera"]

    def recent(self, seconds):
        """Pupil positions from the last `seconds`; if none, the newest one if it is still fresh."""
        now = time.monotonic()
        samples = list(self.samples)
        hits = [p for t, p in samples if now - t <= seconds]
        if not hits and samples and now - samples[-1][0] <= 0.5:
            hits = [samples[-1][1]]
        return hits

    def age_ms(self):
        return round((time.monotonic() - self.samples[-1][0]) * 1000) if self.samples else None

    def want_preview(self):
        """Called while the diagnostics view is open. Without it, no picture is drawn or encoded."""
        self.preview_until = time.monotonic() + 1.5

    def run(self):
        while True:
            if not self.settings()["enabled"]:
                self.error = self.jpeg = None
                time.sleep(0.5)
                continue
            try:
                self._loop()
            except Exception as e:
                self.error = f"{type(e).__name__}: {e}"
                time.sleep(3.0)

    def _loop(self):
        import cv2
        source = str(self.settings()["source"]).strip()
        if not source:
            raise RuntimeError("no glasses camera chosen yet")
        cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
        if not cap.isOpened():
            raise RuntimeError(f"could not open glasses camera '{source}'")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # always work on the newest picture, never a queued one
        try:
            last = time.monotonic()
            n = 0
            while True:
                s = self.settings()
                if not s["enabled"] or str(s["source"]).strip() != source:
                    return
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("glasses camera stopped sending pictures")
                if s["flip"]:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                began = time.monotonic()
                pupil = detect_pupil(gray, s["threshold"])
                now = time.monotonic()
                if pupil:
                    self.samples.append((now, [pupil["x"], pupil["y"]]))
                self.error = None
                self.process_ms = 0.9 * self.process_ms + 0.1 * (now - began) * 1000
                self.fps = 0.9 * self.fps + 0.1 / max(1e-3, now - last)
                last = now
                n += 1
                # The picture is only drawn and encoded while the diagnostics view is open.
                if now < self.preview_until:
                    if n % 2 == 0:
                        self._preview(cv2, frame, pupil)
                elif self.jpeg is not None:
                    self.jpeg = None
        finally:
            cap.release()

    def _preview(self, cv2, frame, pupil):
        """Eye picture with the pupil outlined and an arrow from the picture's centre to the pupil."""
        h, w = frame.shape[:2]
        cv2.drawMarker(frame, (w // 2, h // 2), (255, 255, 255), cv2.MARKER_CROSS, 14, 1)
        if pupil:
            cv2.ellipse(frame, pupil["ellipse"], (0, 255, 0), 2)
            cv2.arrowedLine(frame, (w // 2, h // 2), (int(pupil["x"] * w), int(pupil["y"] * h)), (0, 255, 0), 2, tipLength=0.15)
        ok, buf = cv2.imencode(".jpg", cv2.resize(frame, (320, int(320 * h / w))), [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            self.jpeg = buf.tobytes()


class SimEye:
    """Simulation: the pupil position comes from the pretend head's eye sliders."""

    def __init__(self, tracker):
        self.tracker = tracker
        self.jpeg = None
        self.fps = 0.0
        self.process_ms = 0.0
        self.error = None

    def start(self):
        pass

    def want_preview(self):
        pass

    def age_ms(self):
        return 0 if self.tracker.face else None

    def recent(self, seconds):
        return [[self.tracker.f[2], self.tracker.f[3]]] if self.tracker.face else []
