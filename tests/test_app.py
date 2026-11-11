"""End-to-end checks using the simulated tracker and a recording USB link (no hardware)."""
import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from look_mouse.app import App
from look_mouse.config import Config
from look_mouse.hid import FakeLink, LockKeyListener
from look_mouse.server import make_handler
from look_mouse.eye import SimEye, detect_pupil
from look_mouse.tracker import SimTracker, features_from

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

# Pretend desk: each screen spans a range of head yaw / pitch (degrees) and a little eye movement.
DESK = {0: ((-65, -35), (-25, 25)), 1: ((-20, 20), (-11, 11)), 2: ((32, 62), (-11, 11))}
GRID = (0.1, 0.5, 0.9)


def look(monitor, u, v):
    (y0, y1), (p0, p1) = DESK[monitor]
    return [y0 + u * (y1 - y0), p0 + v * (p1 - p0), 0.4 + 0.2 * u, -0.05 + 0.1 * v]


def make_app():
    cfg = Config(path=None)
    tracker, link = SimTracker(), FakeLink()
    return App(cfg, tracker, link, SimEye(tracker)), tracker, link


def calibrate(app, tracker, points=GRID):
    for mon in DESK:
        for v in points:
            for u in points:
                tracker.f = look(mon, u, v)
                assert app.add_sample(mon, u, v)["ok"]


class GazeTests(unittest.TestCase):
    def test_full_calibration_lands_near_target(self):
        app, tracker, _ = make_app()
        calibrate(app, tracker)
        for mon in DESK:
            for u, v in ((0.3, 0.7), (0.8, 0.2), (0.5, 0.5)):
                tracker.f = look(mon, u, v)
                g = app.gaze()
                self.assertEqual(g["monitor"], mon)
                self.assertAlmostEqual(g["u"], u, delta=0.06)
                self.assertAlmostEqual(g["v"], v, delta=0.06)

    def test_one_point_per_screen_picks_screen_centre(self):
        app, tracker, link = make_app()
        calibrate(app, tracker, points=(0.5,))
        tracker.f = look(0, 0.2, 0.8)
        r = app.jump()
        self.assertTrue(r["ok"])
        self.assertEqual(r["monitor"], 0)
        m = app.config.data["monitors"][0]
        self.assertEqual((r["x"], r["y"]), (round(m["x"] + (m["w"] - 1) / 2), round(m["y"] + (m["h"] - 1) / 2)))

    def test_jump_reports_why_it_did_nothing(self):
        app, tracker, link = make_app()
        self.assertEqual(app.jump()["reason"], "Not calibrated yet")
        tracker.face = False
        app.last_trigger = 0
        self.assertEqual(app.jump()["reason"], "No face in view")
        self.assertEqual(link.events, [])


class GlassesTests(unittest.TestCase):
    def test_glasses_camera_supplies_the_eye_direction(self):
        app, tracker, _ = make_app()
        app.config.update({"eye_camera": {"enabled": True}})
        calibrate(app, tracker)
        self.assertEqual(app.config.data["calibration_source"], "glasses")
        tracker.f = look(2, 0.7, 0.3)
        g = app.gaze()
        self.assertEqual(g["monitor"], 2)
        self.assertAlmostEqual(g["u"], 0.7, delta=0.06)

    def test_calibration_made_without_glasses_is_not_reused_with_them(self):
        app, tracker, link = make_app()
        calibrate(app, tracker, points=(0.5,))
        app.config.update({"eye_camera": {"enabled": True}})
        r = app.jump()
        self.assertFalse(r["ok"])
        self.assertIn("Calibrate again", r["reason"])
        self.assertFalse(app.add_sample(0, .5, .5)["ok"])
        app.clear_samples()
        self.assertTrue(app.add_sample(0, .5, .5)["ok"])
        self.assertEqual(link.events, [])

    def test_blink_gives_no_estimate(self):
        class Blink(SimEye):
            def recent(self, n, max_age=0.5): return []
        app, tracker, _ = make_app()
        app.eye = Blink(tracker)
        app.config.update({"eye_camera": {"enabled": True}})
        self.assertIsNone(app.features())
        self.assertIn("pupil", app.why)

    @unittest.skipIf(cv2 is None, "OpenCV not installed")
    def test_pupil_is_found_despite_eyelashes_reflection_and_dark_corner(self):
        rng = np.random.default_rng(1)
        for cx, cy in ((200, 150), (120, 100), (260, 170)):
            img = np.full((240, 320), 150, np.uint8)
            cv2.ellipse(img, (cx + 5, cy), (60, 55), 0, 0, 360, 95, -1)        # iris
            cv2.ellipse(img, (cx, cy), (24, 20), 15, 0, 360, 20, -1)           # pupil
            cv2.circle(img, (cx + 6, cy - 5), 4, 255, -1)                      # reflection of a light
            for i in range(6):                                                  # eyelashes
                cv2.line(img, (60 + i * 35, 10), (70 + i * 35, 45), 25, 2)
            cv2.rectangle(img, (0, 200), (40, 239), 10, -1)                    # dark picture corner
            img = cv2.add(img, rng.integers(0, 12, img.shape, dtype=np.uint8))
            p = detect_pupil(img)
            self.assertIsNotNone(p)
            self.assertAlmostEqual(p["x"] * 320, cx, delta=3)
            self.assertAlmostEqual(p["y"] * 240, cy, delta=3)

    @unittest.skipIf(cv2 is None, "OpenCV not installed")
    def test_closed_eye_has_no_pupil(self):
        img = np.full((240, 320), 150, np.uint8)
        cv2.line(img, (60, 120), (260, 125), 30, 4)
        self.assertIsNone(detect_pupil(img))


class PointerTests(unittest.TestCase):
    def test_desktop_mode_spans_all_screens(self):
        app, _, link = make_app()
        app.send_to(0, 0, 0)   # top-left of the left portrait screen = left edge of the desktop
        app.send_to(2, 1, 1)   # bottom-right of the right screen = right edge of the desktop
        self.assertEqual(link.events[0], ("abs", 0.0, 0.0))
        kind, fx, fy = link.events[1]
        self.assertEqual((kind, fx), ("abs", 1.0))
        self.assertAlmostEqual(fy, (1079 + 420) / 1919, places=3)

    def test_primary_mode_steps_across_to_other_screens(self):
        app, _, link = make_app()
        app.config.update({"pointer": {"mode": "primary", "rel_px_per_count": 2.0}})
        app.send_to(1, 0.5, 0.5)
        self.assertEqual(len(link.events), 1)          # on the primary screen: one absolute jump
        link.events.clear()
        r = app.send_to(0, 0.5, 0.5)                    # left screen: jump to the edge, then step
        (kind, fx, fy), (rel, dx, dy) = link.events
        self.assertEqual((kind, rel), ("abs", "rel"))
        anchor_x = round(fx * 1919)
        self.assertAlmostEqual(anchor_x + dx * 2.0, r["x"], delta=2)
        self.assertEqual(dy, 0)


class TriggerTests(unittest.TestCase):
    def test_lock_key_triggers_once_and_is_switched_back_off(self):
        app, _, link = make_app()
        fired = []
        listener = LockKeyListener(link, app.config, lambda: fired.append(1))
        listener.started_at -= 10
        listener.handle(0x04)   # Scroll Lock turned on by the user
        listener.handle(0x00)   # ... and off again by our own key tap
        self.assertEqual(len(fired), 1)
        self.assertEqual(link.events, [("key", 0x47)])

    def test_lock_already_on_at_startup_does_not_trigger(self):
        app, _, link = make_app()
        fired = []
        LockKeyListener(link, app.config, lambda: fired.append(1)).handle(0x04)
        self.assertEqual(fired, [])
        self.assertEqual(link.events, [("key", 0x47)])


class FeatureTests(unittest.TestCase):
    def test_features_follow_head_and_eyes(self):
        class P:
            def __init__(self, x, y): self.x, self.y = x, y
        lm = {33: P(.30, .5), 133: P(.40, .5), 468: P(.36, .49), 362: P(.60, .5), 263: P(.70, .5), 473: P(.66, .49)}
        facing = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, -50], [0, 0, 0, 1]]
        yaw, pitch, eh, ev = features_from(lm, facing)
        self.assertAlmostEqual(yaw, 0)
        self.assertAlmostEqual(pitch, 0)
        self.assertAlmostEqual(eh, 0.6)
        self.assertLess(ev, 0)
        turned = [[0.866, 0, 0.5, 0], [0, 1, 0, 0], [-0.5, 0, 0.866, -50], [0, 0, 0, 1]]
        self.assertAlmostEqual(features_from(lm, turned)[0], 30, delta=0.1)


class ServerTests(unittest.TestCase):
    def test_calibrate_and_jump_over_http(self):
        app, tracker, link = make_app()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}"

        def post(path, body):
            req = urllib.request.Request(base + path, json.dumps(body).encode(), method="POST")
            return json.load(urllib.request.urlopen(req))

        self.assertIn(b"Look Mouse", urllib.request.urlopen(base + "/").read())
        for mon in DESK:
            post("/api/sim", {"f": look(mon, .5, .5)})
            self.assertTrue(post("/api/calibrate/sample", {"monitor": mon, "u": .5, "v": .5})["ok"])
        post("/api/sim", {"f": look(2, .5, .5)})
        self.assertEqual(post("/api/jump", {})["monitor"], 2)
        status = json.load(urllib.request.urlopen(base + "/api/status"))
        self.assertEqual(status["samples"], {"0": 1, "1": 1, "2": 1})
        self.assertEqual(post("/api/config", {"behaviour": {"window": 5}})["behaviour"]["window"], 5)
        srv.shutdown()


if __name__ == "__main__":
    unittest.main()
