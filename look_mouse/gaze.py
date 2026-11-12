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

    def explain(self, f):
        """One row per calibrated screen: what its model makes of this reading.

        "u", "v" (where on that screen, 0..1) and "off" (how far outside it) are present
        only for screens with enough calibration points to place the gaze.
        """
        head = np.asarray(f, float)[:2]
        rows = []
        for i, m in sorted(self.models.items()):
            row = {"monitor": i, "head_distance": float(np.linalg.norm(head - m.centroid))}
            if m.w is not None:
                u, v = m.predict(f)
                row.update(u=u, v=v, off=max(0.0, -u, u - 1.0) + max(0.0, -v, v - 1.0))
            rows.append(row)
        return rows

    def predict(self, f, rows=None):
        """Return {"monitor", "u", "v", "precise"} or None if nothing is calibrated."""
        rows = self.explain(f) if rows is None else rows
        if not rows:
            return None
        if all("u" in r for r in rows):
            # Every screen can place the gaze; pick the one whose own model puts it on-screen.
            best = min(rows, key=lambda r: (r["off"], r["head_distance"]))
        else:
            # Otherwise fall back to whichever screen's average head direction is closest.
            best = min(rows, key=lambda r: r["head_distance"])
        if "u" not in best:
            return {"monitor": best["monitor"], "u": 0.5, "v": 0.5, "precise": False}
        return {"monitor": best["monitor"], "u": _clip(best["u"]), "v": _clip(best["v"]), "precise": True}


def _clip(x):
    return min(0.98, max(0.02, x))
