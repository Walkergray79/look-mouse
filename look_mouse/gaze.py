"""Turns head/eye features into "which screen, and where on it".

A feature vector is [head yaw, head pitch, eye horizontal, eye vertical].
Each screen gets its own small linear model fitted from its calibration samples,
because screens sit at different angles and their desktop coordinates say nothing
about where they physically are.
"""
import numpy as np

MIN_MODEL_POINTS = 4   # fewer samples than this: the screen is known only by its average direction
RIDGE = 0.3


class MonitorModel:
    def __init__(self, samples, use_eyes):
        self.cols = [0, 1, 2, 3] if use_eyes else [0, 1]
        full = np.array([s["f"] for s in samples], float)
        self.centroid = full[:, :2].mean(axis=0)
        self.w = None
        if len(samples) >= MIN_MODEL_POINTS:
            feats = full[:, self.cols]
            target = np.array([[s["u"], s["v"]] for s in samples], float)
            self.mu = feats.mean(axis=0)
            self.sd = feats.std(axis=0)
            self.sd[self.sd < 1e-6] = 1.0
            a = np.hstack([np.ones((len(samples), 1)), (feats - self.mu) / self.sd])
            reg = RIDGE * np.eye(a.shape[1])
            reg[0, 0] = 0.0
            self.w = np.linalg.solve(a.T @ a + reg, a.T @ target)

    def predict(self, f):
        x = (np.asarray(f, float)[self.cols] - self.mu) / self.sd
        u, v = np.concatenate([[1.0], x]) @ self.w
        return float(u), float(v)


class GazeModel:
    def __init__(self, calibration, use_eyes=True):
        self.models = {int(k): MonitorModel(v, use_eyes) for k, v in calibration.items() if v}

    def predict(self, f):
        """Return {"monitor", "u", "v", "precise"} or None if nothing is calibrated."""
        if not self.models:
            return None
        head = np.asarray(f, float)[:2]
        dist = {i: float(np.linalg.norm(head - m.centroid)) for i, m in self.models.items()}

        if all(m.w is not None for m in self.models.values()):
            # Every screen can place the gaze; pick the one whose own model puts it on-screen.
            best = None
            for i, m in self.models.items():
                u, v = m.predict(f)
                off = max(0.0, -u, u - 1.0) + max(0.0, -v, v - 1.0)
                if best is None or (off, dist[i]) < best[:2]:
                    best = (off, dist[i], i, u, v)
            _, _, i, u, v = best
            return {"monitor": i, "u": _clip(u), "v": _clip(v), "precise": True}

        # Otherwise fall back to whichever screen's average head direction is closest.
        i = min(dist, key=dist.get)
        m = self.models[i]
        if m.w is None:
            return {"monitor": i, "u": 0.5, "v": 0.5, "precise": False}
        u, v = m.predict(f)
        return {"monitor": i, "u": _clip(u), "v": _clip(v), "precise": True}


def _clip(x):
    return min(0.98, max(0.02, x))
