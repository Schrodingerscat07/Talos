"""The teacher: a privileged scripted controller that knows where the crate is.

It is used ONLY to label training data (imitation learning) and as an upper-bound baseline.
Its behaviour is deliberately 'observable-consistent': when the crate is outside the camera's view
it always searches by turning the same way, because the student cannot see which way is shorter.
(If the teacher turned the short way, the student would average +1 and -1 into 0 and freeze.)
"""
from __future__ import annotations

import math

import numpy as np


def wrap180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


class CrateTeacher:
    privileged = True
    name = "teacher_search_right_then_approach_v1"

    def __init__(self, visible_half_deg=38.0, turn_deg_per_step=9.0, search_turn=1.0):
        # Camera FOV is 90 deg; 38 keeps a margin so the crate is clearly in frame when steering starts.
        self.visible_half_deg = visible_half_deg
        self.turn_deg_per_step = turn_deg_per_step
        self.search_turn = search_turn

    def reset(self):
        pass

    def act(self, img, pro, transition) -> np.ndarray:
        priv = transition["privileged"]
        target = priv["obstacle_position_cm"]
        x, y, _ = priv["position_cm"]
        heading = transition["observation"]["proprioception"]["heading_deg"]
        bearing = math.degrees(math.atan2(target[1] - y, target[0] - x))
        err = wrap180(bearing - heading)
        if abs(err) > self.visible_half_deg:
            return np.array([0.0, 0.0, self.search_turn, 0.0])          # search: turn in place
        turn = float(np.clip(err / self.turn_deg_per_step, -1, 1))
        forward = 1.0 if abs(err) < 15 else 0.5
        return np.array([forward, 0.0, turn, 0.0])
