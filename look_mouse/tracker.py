"""Camera capture and face tracking.

Produces a feature vector per frame: [head yaw, head pitch, eye horizontal, eye vertical].
Yaw and pitch are in degrees. The eye values say where the irises sit within the eye
openings, in units of eye width. Signs and offsets don't matter: calibration absorbs them.
"""
import collections
import math
import os
import threading
import time

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "models", "face_landmarker.task")

# MediaPipe face-mesh landmark numbers: (image-left corner, image-right corner, iris centre)
EYES = ((33, 133, 468), (362, 263, 473))


def features_from(landmarks, matrix):
    """landmarks: sequence with .x/.y in image fractions. matrix: 4x4 face-to-camera transform."""
    fx, fy, fz = matrix[0][2], matrix[1][2], matrix[2][2]   # direction the face points
    yaw = math.degrees(math.atan2(fx, fz))
    pitch = math.degrees(math.atan2(fy, math.hypot(fx, fz)))
    eh = ev = 0.0
    for a, b, p in EYES:
        ax, ay = landmarks[a].x, landmarks[a].y
        dx, dy = landmarks[b].x - ax, landmarks[b].y - ay
        px, py = landmarks[p].x - ax, landmarks[p].y - ay
        d2 = dx * dx + dy * dy or 1e-9
        eh += (px * dx + py * dy) / d2 / 2      # along the eye: 0 = one corner, 1 = the other
        ev += (dx * py - dy * px) / d2 / 2      # across the eye: above / below the corner line
    return [yaw, pitch, eh, ev]


class Tracker(threading.Thread):
    def __init__(self, config):
        super().__init__(daemon=True)
        self.config = config
        self.samples = collections.deque(maxlen=60)   # (time, features)
        self.jpeg = None
        self.fps = 0.0
        self.process_ms = 0.0
        self.error = None
        self.simulated = False
        self.preview_until = 0.0

    def recent(self, seconds):
        """Readings from the last `seconds`; if there are none, the newest one if it is still fresh."""
        now = time.monotonic()
        samples = list(self.samples)
        hits = [f for t, f in samples if now - t <= seconds]
        if not hits and samples and now - samples[-1][0] <= 0.7:
            hits = [samples[-1][1]]
        return hits

    def age_ms(self):
        return round((time.monotonic() - self.samples[-1][0]) * 1000) if self.samples else None

    def want_preview(self):
        """Called while someone is watching the diagnostics view. Without it, no picture is drawn or encoded."""
        self.preview_until = time.monotonic() + 1.5

    def run(self):
        while True:
            try:
                self._loop()
            except Exception as e:  # camera unplugged, model missing, ...
                self.error = f"{type(e).__name__}: {e}"
                time.sleep(3.0)

    def _open_camera(self):
        import cv2
        cam = self.config.data["camera"]
        size = (cam["width"], cam["height"])
        if cam["source"] in ("auto", "picamera"):
            try:
                from picamera2 import Picamera2
                pc = Picamera2()
                pc.configure(pc.create_video_configuration(main={"size": size, "format": "RGB888"}))
                pc.start()
                return pc.capture_array, pc.close   # despite the name, arrays arrive in BGR order
            except Exception:
                if cam["source"] == "picamera":
                    raise
        cap = cv2.VideoCapture(cam["index"])
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # always work on the newest picture, never a queued one
        if not cap.isOpened():
            raise RuntimeError("no camera found")

        def read():
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("camera stopped sending frames")
            return frame
        return read, cap.release

    def _loop(self):
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(f"face model missing at {MODEL_PATH} (run install.sh)")
        landmarker = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO, num_faces=1,
            output_facial_transformation_matrixes=True))
        read, close = self._open_camera()
        try:
            t0 = last_ts = time.monotonic()
            stamp = 0
            n = 0
            while True:
                frame = read()
                if self.config.data["camera"]["flip"]:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                now = time.monotonic()
                stamp = max(stamp + 1, int((now - t0) * 1000))
                image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                 data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = landmarker.detect_for_video(image, stamp)
                face = result.face_landmarks[0] if result.face_landmarks else None
                matrix = result.facial_transformation_matrixes[0] if face and result.facial_transformation_matrixes else None
                done = time.monotonic()
                if matrix is not None:
                    self.samples.append((done, features_from(face, matrix)))
                self.error = None
                self.process_ms = 0.9 * self.process_ms + 0.1 * (done - now) * 1000
                self.fps = 0.9 * self.fps + 0.1 / max(1e-3, now - last_ts)
                last_ts = now
                n += 1
                # The picture is only drawn and encoded while the diagnostics view is open.
                if done < self.preview_until:
                    if n % 2 == 0:
                        self._preview(cv2, frame, face, matrix)
                elif self.jpeg is not None:
                    self.jpeg = None
        finally:
            close()

    def _preview(self, cv2, frame, face, matrix):
        """Camera picture with the measured directions drawn on: head in orange, eyes in green."""
        h, w = frame.shape[:2]
        if matrix is not None:
            def pt(i):
                return int(face[i].x * w), int(face[i].y * h)
            thick = max(2, w // 300)
            for a, b, p in EYES:
                (ax, ay), (bx, by), (ix, iy) = pt(a), pt(b), pt(p)
                cx, cy = (ax + bx) // 2, (ay + by) // 2
                cv2.circle(frame, (ix, iy), thick + 1, (0, 255, 0), -1)
                # iris offset from the middle of the eye opening, exaggerated so it can be seen
                cv2.arrowedLine(frame, (cx, cy), (cx + (ix - cx) * 8, cy + (iy - cy) * 8), (0, 255, 0), thick, tipLength=0.25)
            face_width = abs(face[454].x - face[234].x) * w
            nx, ny = pt(1)
            # the direction the face points; the matrix has y upwards, pictures have y downwards
            cv2.arrowedLine(frame, (nx, ny), (int(nx + matrix[0][2] * face_width * 1.2), int(ny - matrix[1][2] * face_width * 1.2)),
                            (0, 160, 255), thick + 1, tipLength=0.2)
        small = cv2.resize(frame, (400, int(400 * h / w)))
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            self.jpeg = buf.tobytes()


class SimTracker:
    """No camera: the "head direction" is set from the web interface. For development and tests."""

    def __init__(self):
        self.f = [0.0, 0.0, 0.5, 0.0]
        self.face = True
        self.jpeg = None
        self.fps = 0.0
        self.process_ms = 0.0
        self.error = None
        self.simulated = True

    def start(self):
        pass

    def want_preview(self):
        pass

    def age_ms(self):
        return 0 if self.face else None

    def recent(self, seconds):
        return [list(self.f)] if self.face else []
