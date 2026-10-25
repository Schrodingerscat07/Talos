"""Observation-only environment wrapper around the Talos erl/1.0 client.

The brain sees ONLY: ego RGB (downscaled), proprioception, contact flag.
Tasks and the teacher may read privileged data; the brain never does.
"""
from __future__ import annotations

import base64
import io
import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

from erl.client import Action

PROPRIO_DIM = 7          # sin/cos heading, pitch, 3x velocity, blocked
IMAGE_HW = (60, 80)      # 160x120 camera downscaled 2x: 4x less compute, the crate stays visible


def decode_rgb(rgb: dict | None, hw=IMAGE_HW) -> np.ndarray:
    """PNG base64 -> uint8 [3, H, W]. NullRHI (None) gives zeros; never train vision on that."""
    if rgb is None:
        return np.zeros((3, *hw), dtype=np.uint8)
    image = Image.open(io.BytesIO(base64.b64decode(rgb["data"]))).convert("RGB")
    if image.size != (hw[1], hw[0]):
        image = image.resize((hw[1], hw[0]), Image.BILINEAR)
    return np.asarray(image, dtype=np.uint8).transpose(2, 0, 1).copy()


def encode_observation(observation: dict, hw=IMAGE_HW) -> tuple[np.ndarray, np.ndarray]:
    """Policy observation dict -> (image uint8 [3,H,W], proprio float32 [7])."""
    p = observation["proprioception"]
    h = math.radians(p["heading_deg"])
    vx, vy, vz = p["local_velocity_cm_s"]
    proprio = np.array([
        math.sin(h), math.cos(h), p["look_pitch_deg"] / 70.0,
        vx / 150.0, vy / 150.0, vz / 150.0,
        1.0 if observation["contacts"]["blocked"] else 0.0,
    ], dtype=np.float32)
    return decode_rgb(observation["rgb"], hw), proprio


def preroll_actions(seed: int, max_turn_steps=40, max_move_steps=10) -> list[Action]:
    """Scripted start-pose randomisation run before the brain takes control (recorded as assistance).

    The engine always spawns at the same pose; without this, 'walk forward' solves the task.
    Turn up to 360 deg, shuffle position up to ~1.5 m, turn again. Deterministic per seed.
    """
    rng = np.random.default_rng(seed + 7919)
    out = []
    for _ in range(int(rng.integers(0, max_turn_steps // 2))):
        out.append(Action(turn=1.0))
    for _ in range(int(rng.integers(0, max_move_steps))):
        out.append(Action(forward=float(rng.uniform(-1, 1)), strafe=float(rng.uniform(-1, 1))))
    sign = 1.0 if rng.random() < 0.5 else -1.0
    for _ in range(int(rng.integers(0, max_turn_steps // 2))):
        out.append(Action(turn=sign))
    return out


class TalosEnv:
    """One Unreal instance + one task. Gym-like reset/step returning arrays.

    `last_transition` keeps the full transition for the task/teacher/recorder; policies get arrays only.
    """

    def __init__(self, client, task, seeds: list[int], randomize_start=True, max_episode_steps=150,
                 hw=IMAGE_HW, on_transition=None):
        self.client, self.task, self.seeds = client, task, list(seeds)
        self.randomize_start, self.max_episode_steps, self.hw = randomize_start, max_episode_steps, hw
        self.on_transition = on_transition  # optional callback(transition, action) e.g. a Recorder
        self._episode = 0
        self.episode_return = 0.0
        self.episode_length = 0
        self.last_transition = None
        self.seed = None

    def _emit(self, t, action=None):
        self.last_transition = t
        if self.on_transition:
            self.on_transition(t, action)

    def reset(self):
        self.seed = self.seeds[self._episode % len(self.seeds)]
        self._episode += 1
        if hasattr(self.task, "configure"):
            self.task.configure(self.seed)
        t = self.client.reset(seed=self.seed)
        self._emit(t)
        if self.randomize_start:
            for a in preroll_actions(self.seed):
                t = self.client.step(a)
                self._emit(t, a)
        self.task.reset(t)
        self.episode_return, self.episode_length = 0.0, 0
        return self._observe(t)

    def _observe(self, t):
        img, pro = encode_observation(t["observation"], self.hw)
        instruction = getattr(self.task, "instruction", None)
        if instruction is not None:      # tasks with a goal instruction show it to the policy as extra body input
            pro = np.concatenate([pro, instruction]).astype(np.float32)
        return img, pro

    def step(self, action_vec):
        a = np.clip(np.asarray(action_vec, dtype=float), -1, 1)
        act = Action(forward=float(a[0]), strafe=float(a[1]), turn=float(a[2]), look=float(a[3]))
        t = self.client.step(act)
        self._emit(t, act)
        reward, task_done, info = self.task.reward(t)
        self.episode_return += reward
        self.episode_length += 1
        capped = self.episode_length >= self.max_episode_steps
        done = task_done or t["terminated"] or t["truncated"] or capped
        info.update(truncated=(t["truncated"] or capped) and not task_done)
        if done:
            info["episode"] = {"return": self.episode_return, "length": self.episode_length, "seed": self.seed}
        return self._observe(t), reward, done, info


class VecEnv:
    """Steps several Unreal instances concurrently. Each step is an HTTP wait, so threads suffice."""

    def __init__(self, envs: list[TalosEnv]):
        self.envs = envs
        self.pool = ThreadPoolExecutor(max_workers=len(envs))

    def reset(self):
        obs = list(self.pool.map(lambda e: e.reset(), self.envs))
        return np.stack([o[0] for o in obs]), np.stack([o[1] for o in obs])

    def step(self, actions: np.ndarray):
        def one(args):
            env, a = args
            obs, r, done, info = env.step(a)
            if done:  # auto-reset; the returned obs is the first of the next episode
                obs = env.reset()
            return obs, r, done, info
        out = list(self.pool.map(one, zip(self.envs, actions)))
        images = np.stack([o[0][0] for o in out])
        proprio = np.stack([o[0][1] for o in out])
        rewards = np.array([o[1] for o in out], dtype=np.float32)
        dones = np.array([o[2] for o in out], dtype=np.float32)
        return images, proprio, rewards, dones, [o[3] for o in out]
