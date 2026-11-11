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
        self.error = None
        self.simulated = False

    def recent(self, n, max_age=0.7):
        now = time.monotonic()
        return [f for t, f in list(self.samples)[-n:] if now - t <= max_age]

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
                if face and result.facial_transformation_matrixes:
                    self.samples.append((now, features_from(face, result.facial_transformation_matrixes[0])))
                self.error = None
                self.fps = 0.9 * self.fps + 0.1 / max(1e-3, now - last_ts)
                last_ts = now
                n += 1
                if n % 3 == 0:
                    self._preview(cv2, frame, face)
        finally:
            close()

    def _preview(self, cv2, frame, face):
        h, w = frame.shape[:2]
        if face:
            for i in (468, 473, 1):
                cv2.circle(frame, (int(face[i].x * w), int(face[i].y * h)), 4, (0, 255, 0), -1)
        small = cv2.resize(frame, (320, int(320 * h / w)))
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
        self.error = None
        self.simulated = True

    def start(self):
        pass

    def recent(self, n, max_age=0.7):
        return [list(self.f)] * n if self.face else []
