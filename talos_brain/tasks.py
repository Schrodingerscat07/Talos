"""Client-side task/reward providers.

The engine currently always returns reward 0, so the reward signal is computed here from the
*privileged* transition fields. That is legitimate: privileged data may define the teacher signal,
but it is never passed to the policy. Every task declares exactly what it uses so runs are auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass
class ExploreTask:
    """Reward for visiting new floor cells, penalty for pushing into walls.

    Learnable from the ego camera alone: the agent must see open space and avoid obstacles.
    A good first task because it needs no new engine features.
    """
    cell_cm: float = 100.0
    new_cell_reward: float = 1.0
    blocked_penalty: float = 0.1
    step_penalty: float = 0.005
    name: str = "explore_v1"
    uses_privileged: tuple = ("position_cm",)
    _visited: set = field(default_factory=set, repr=False)

    def _cell(self, transition: dict) -> tuple[int, int]:
        x, y, _ = transition["privileged"]["position_cm"]
        return (math.floor(x / self.cell_cm), math.floor(y / self.cell_cm))

    def reset(self, transition: dict) -> None:
        self._visited = {self._cell(transition)}

    def reward(self, transition: dict) -> tuple[float, bool, dict]:
        cell = self._cell(transition)
        r = -self.step_penalty
        new = cell not in self._visited
        if new:
            self._visited.add(cell)
            r += self.new_cell_reward
        blocked = transition["observation"]["contacts"]["blocked"]
        if blocked:
            r -= self.blocked_penalty
        return r, False, {"cells_visited": len(self._visited), "new_cell": new, "blocked": blocked}


@dataclass
class GoalTask:
    """Reach a fixed goal point. Shaped by distance progress, terminates on arrival.

    Without a visible goal marker in the world, the policy can only learn this by memorising the
    layout for a given seed -- useful as a memory test (Phase 4), not as a generalisation test.
    """
    goal_cm: tuple[float, float] = (500.0, 300.0)
    radius_cm: float = 75.0
    success_reward: float = 10.0
    progress_scale: float = 0.01
    name: str = "goal_v1"
    uses_privileged: tuple = ("position_cm",)
    _last: float = 0.0

    def _dist(self, transition: dict) -> float:
        x, y, _ = transition["privileged"]["position_cm"]
        return math.hypot(x - self.goal_cm[0], y - self.goal_cm[1])

    def reset(self, transition: dict) -> None:
        self._last = self._dist(transition)

    def reward(self, transition: dict) -> tuple[float, bool, dict]:
        d = self._dist(transition)
        r = (self._last - d) * self.progress_scale
        self._last = d
        done = d < self.radius_cm
        if done:
            r += self.success_reward
        return r, done, {"distance_cm": d, "success": done}


@dataclass
class ReachCrateTask:
    """Walk to the seeded obstacle/crate. Visible in the ego camera, so it is learnable from vision.

    Works on the built-in room and home worlds (they report obstacle_position_cm). JSON layouts and
    authored maps report null and this task refuses them. v0 caveat: the engine only moves the crate
    sideways (room: y in [-200,200] at x=220), so this is an easy first task, not a generalisation test.
    A properly randomised target needs an engine change (Phase 2B).
    """
    reach_cm: float = 130.0          # centre-to-centre horizontal distance that counts as arrival
    success_reward: float = 10.0
    progress_scale: float = 0.01
    step_penalty: float = 0.005
    name: str = "reach_crate_v0"
    uses_privileged: tuple = ("position_cm", "obstacle_position_cm")
    _last: float = 0.0

    def _dist(self, transition: dict) -> float:
        target = transition["privileged"].get("obstacle_position_cm")
        if target is None:
            raise ValueError("reach_crate needs a world with a seeded obstacle (room/home), got null")
        x, y, _ = transition["privileged"]["position_cm"]
        return math.hypot(x - target[0], y - target[1])

    def reset(self, transition: dict) -> None:
        self._last = self._dist(transition)

    def reward(self, transition: dict) -> tuple[float, bool, dict]:
        d = self._dist(transition)
        r = (self._last - d) * self.progress_scale - self.step_penalty
        self._last = d
        done = d < self.reach_cm
        if done:
            r += self.success_reward
        return r, done, {"distance_cm": d, "success": done}


# Target boxes of configs/manny_two_targets.json (centre x, y in cm): index 0 = Terracotta, 1 = Blue.
TARGETS_CM = ((330.0, -240.0), (330.0, 240.0))
TARGET_NAMES = ("terracotta", "blue")


def resolve_targets(layout=None):
    """Target (x, y) pairs for a named layout in configs/two_layouts.json; None = the original TARGETS_CM."""
    if not layout:
        return TARGETS_CM
    import json
    from pathlib import Path
    table = json.loads((Path(__file__).resolve().parents[1] / "configs" / "two_layouts.json").read_text())
    if layout not in table:
        raise SystemExit(f"unknown layout {layout}; choose from {sorted(table)}")
    return (tuple(table[layout]["terracotta"]), tuple(table[layout]["blue"]))


@dataclass
class TwoTargetTask:
    """Go to the box named by an instruction. The instruction is a one-hot the brain sees (appended to proprioception).

    Each episode's target is chosen client-side from the seed (even = terracotta, odd = blue), so the world can stay
    static. Reaching the OTHER box ends the episode as a failure and is reported as `reached_wrong`.
    Needs configs/manny_two_targets.json (or any world with boxes at TARGETS_CM). Uses privileged positions for
    reward only; the policy never sees them.
    """
    reach_cm: float = 130.0
    success_reward: float = 10.0
    wrong_penalty: float = 1.0
    progress_scale: float = 0.01
    step_penalty: float = 0.005
    targets_cm: tuple = TARGETS_CM
    name: str = "two_target_v1"
    uses_privileged: tuple = ("position_cm",)
    target_index: int = 0
    _last: float = 0.0

    @property
    def instruction(self):
        import numpy as np
        v = np.zeros(2, dtype=np.float32); v[self.target_index] = 1.0
        return v

    def configure(self, seed: int) -> None:
        self.target_index = int(seed) % 2

    def _dist(self, transition: dict, index: int) -> float:
        x, y, _ = transition["privileged"]["position_cm"]
        tx, ty = self.targets_cm[index]
        return math.hypot(x - tx, y - ty)

    def reset(self, transition: dict) -> None:
        self._last = self._dist(transition, self.target_index)

    def reward(self, transition: dict) -> tuple[float, bool, dict]:
        d = self._dist(transition, self.target_index)
        other = self._dist(transition, 1 - self.target_index)
        r = (self._last - d) * self.progress_scale - self.step_penalty
        self._last = d
        if d < self.reach_cm:
            return r + self.success_reward, True, {"distance_cm": d, "success": True, "reached_wrong": False}
        if other < self.reach_cm:
            return r - self.wrong_penalty, True, {"distance_cm": d, "success": False, "reached_wrong": True}
        return r, False, {"distance_cm": d, "success": False, "reached_wrong": False}


TRAIN_SEEDS = list(range(0, 1000))       # training layouts
EVAL_SEEDS = list(range(100000, 100050))  # held out: never used in training

TASKS = {"explore": ExploreTask, "goal": GoalTask, "reach": ReachCrateTask, "two": TwoTargetTask}
