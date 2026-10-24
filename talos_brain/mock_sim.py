"""MOCK simulator for debugging the learning code without Unreal. NOT simulation evidence.

Matches the erl/1.0 Client interface (reset/step/spec) and transition shape, with a tiny numpy
raycaster: a walled room plus one seeded box obstacle. Use it to check that PPO runs, losses fall
and reward rises before spending hours of Unreal time. Results here never satisfy a Talos gate.
"""
from __future__ import annotations

import base64
import io
import math
import uuid

import numpy as np
from PIL import Image

W, H = 160, 120
FOV = math.radians(90)


class MockClient:
    def __init__(self, room=(-600, -600, 600, 600), max_steps=500, speed=150, turn_rate=90, look_rate=60):
        self.room, self.max_steps = room, max_steps
        self.speed, self.turn_rate, self.look_rate = speed, turn_rate, look_rate
        self.uncertain = False

    def spec(self):
        return {"max_steps": self.max_steps, "backend": "mock_numpy_raycaster"}

    # --- geometry -------------------------------------------------------
    def _boxes(self):
        x0, y0, x1, y1 = self.room
        ox, oy = self.obstacle
        return [(ox - 50, oy - 50, ox + 50, oy + 50)], (x0, y0, x1, y1)  # 100 cm cube like the room's

    def _free(self, x, y, r=35):
        (bx0, by0, bx1, by1), = self._boxes()[0]
        x0, y0, x1, y1 = self.room
        if not (x0 + r < x < x1 - r and y0 + r < y < y1 - r):
            return False
        return not (bx0 - r < x < bx1 + r and by0 - r < y < by1 + r)

    def _render(self):
        x0, y0, x1, y1 = self.room
        (bx0, by0, bx1, by1), = self._boxes()[0]
        angles = self.yaw + np.linspace(-FOV / 2, FOV / 2, W)
        dx, dy = np.cos(angles), np.sin(angles)
        eps = 1e-9
        # walls
        tx = np.where(dx > 0, (x1 - self.x) / (dx + eps), (x0 - self.x) / (dx - eps))
        ty = np.where(dy > 0, (y1 - self.y) / (dy + eps), (y0 - self.y) / (dy - eps))
        dist = np.minimum(tx, ty)
        color = np.where((tx < ty)[:, None], [[180, 170, 150]], [[150, 160, 180]]).astype(float)
        # box (slab method)
        with np.errstate(divide="ignore", invalid="ignore"):
            t1x, t2x = (bx0 - self.x) / dx, (bx1 - self.x) / dx
            t1y, t2y = (by0 - self.y) / dy, (by1 - self.y) / dy
        tmin = np.maximum(np.minimum(t1x, t2x), np.minimum(t1y, t2y))
        tmax = np.minimum(np.maximum(t1x, t2x), np.maximum(t1y, t2y))
        hit = (tmax >= np.maximum(tmin, 0)) & (tmin > 0) & (tmin < dist)
        dist = np.where(hit, tmin, dist)
        color = np.where(hit[:, None], [[200, 60, 50]], color)
        dist = dist * np.cos(angles - self.yaw)
        wall_h = np.clip(30000 / np.maximum(dist, 1), 0, H * 3)
        horizon = H / 2 + math.tan(self.pitch) * H
        rows = np.arange(H)[:, None]
        top, bottom = horizon - wall_h / 2, horizon + wall_h / 2
        img = np.where(rows < horizon, 1, 0)[..., None] * np.array([110, 140, 190]) + \
              np.where(rows >= horizon, 1, 0)[..., None] * np.array([90, 85, 80])
        shade = np.clip(1.2 - dist / 2500, 0.3, 1)[None, :, None]
        wall = (rows >= top[None, :]) & (rows <= bottom[None, :])
        img = np.where(wall[..., None], color[None, :, :] * shade, img).astype(np.uint8)
        buf = io.BytesIO()
        Image.fromarray(img).save(buf, format="PNG")
        return {"encoding": "png_base64", "width": W, "height": H, "data": base64.b64encode(buf.getvalue()).decode()}

    def _transition(self, velocity, blocked):
        return {
            "protocol": "erl/1.0", "episode_id": self.episode, "step_index": self.index,
            "sim_time_s": round(self.index * 0.1, 6), "reward": 0, "terminated": False,
            "truncated": self.index >= self.max_steps,
            "observation": {
                "rgb": self._render(),
                "proprioception": {
                    "heading_deg": (math.degrees(self.yaw) + 180) % 360 - 180,
                    "look_pitch_deg": math.degrees(self.pitch),
                    "local_velocity_cm_s": velocity,
                },
                "contacts": {"blocked": blocked},
            },
            "privileged": {"position_cm": [self.x, self.y, 89.0], "obstacle_position_cm": [*self.obstacle, 50.0], "seed": self.seed},
        }

    # --- erl/1.0-like API ----------------------------------------------
    def reset(self, seed=0):
        rng = np.random.default_rng(seed)
        self.seed, self.episode, self.index, self.done = seed, str(uuid.uuid4()), 0, False
        self.x, self.y, self.yaw, self.pitch = 0.0, 0.0, 0.0, 0.0
        self.obstacle = (220.0, float(rng.uniform(-200, 200)))  # same rule as the engine's room reset
        return self._transition([0.0, 0.0, 0.0], False)

    def step(self, action):
        if self.index >= self.max_steps:
            raise RuntimeError("Reset required before stepping")
        f, s = action.forward, action.strafe
        n = math.hypot(f, s)
        if n > 1:
            f, s = f / n, s / n
        self.yaw += math.radians(action.turn * self.turn_rate * 0.1)
        self.pitch = max(-math.radians(70), min(math.radians(70), self.pitch + math.radians(action.look * self.look_rate * 0.1)))
        dx = (f * math.cos(self.yaw) - s * math.sin(self.yaw)) * self.speed * 0.1
        dy = (f * math.sin(self.yaw) + s * math.cos(self.yaw)) * self.speed * 0.1
        blocked = False
        nx, ny = self.x + dx, self.y + dy
        if self._free(nx, ny):
            self.x, self.y = nx, ny
            vel = [f * self.speed, s * self.speed, 0.0]
        else:
            blocked = (dx, dy) != (0, 0)
            vel = [0.0, 0.0, 0.0]
        self.index += 1
        self.done = self.index >= self.max_steps
        return self._transition(vel, blocked)
