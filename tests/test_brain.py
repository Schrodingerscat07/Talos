"""Client-side tests for talos_brain. Mock-backed: they check code, not live simulation."""
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

from erl.client import Action, Client
from talos_brain.env import IMAGE_HW, PROPRIO_DIM, TalosEnv, VecEnv, encode_observation, preroll_actions
from talos_brain.evaluate import run_policy, summarise
from talos_brain.expert import CrateTeacher
from talos_brain.mock_sim import MockClient
from talos_brain.tasks import EVAL_SEEDS, TRAIN_SEEDS, ExploreTask, GoalTask, ReachCrateTask

ROOT = Path(__file__).resolve().parents[1]


def fake_transition(x=0.0, y=0.0, blocked=False, obstacle=(220.0, 0.0, 60.0)):
    return {"observation": {"rgb": None, "proprioception": {"heading_deg": 0, "look_pitch_deg": 0, "local_velocity_cm_s": [0, 0, 0]},
                            "contacts": {"blocked": blocked}},
            "privileged": {"position_cm": [x, y, 89.0], "obstacle_position_cm": None if obstacle is None else list(obstacle), "seed": 1}}


class Tasks(unittest.TestCase):
    def test_explore_rewards_new_cells_once(self):
        t = ExploreTask(); t.reset(fake_transition(0, 0))
        r1, _, i1 = t.reward(fake_transition(150, 0))
        r2, _, _ = t.reward(fake_transition(150, 0))
        self.assertTrue(i1["new_cell"]); self.assertGreater(r1, 0.9); self.assertLess(r2, 0)

    def test_explore_penalises_blocking(self):
        t = ExploreTask(); t.reset(fake_transition())
        r, _, info = t.reward(fake_transition(blocked=True))
        self.assertTrue(info["blocked"]); self.assertLess(r, -0.1 + 1e-9)

    def test_goal_terminates_on_arrival(self):
        t = GoalTask(goal_cm=(100, 0)); t.reset(fake_transition())
        _, done, info = t.reward(fake_transition(60, 0))
        self.assertTrue(done and info["success"])

    def test_reach_progress_and_success(self):
        t = ReachCrateTask(); t.reset(fake_transition(0, 0))
        r, done, _ = t.reward(fake_transition(50, 0))
        self.assertGreater(r, 0); self.assertFalse(done)
        r, done, info = t.reward(fake_transition(120, 0))
        self.assertTrue(done and info["success"]); self.assertGreater(r, 10)

    def test_reach_refuses_worlds_without_obstacle(self):
        with self.assertRaises(ValueError):
            ReachCrateTask().reset(fake_transition(obstacle=None))

    def test_seed_splits_disjoint(self):
        self.assertFalse(set(TRAIN_SEEDS) & set(EVAL_SEEDS))


class ObservationPrivacy(unittest.TestCase):
    def test_policy_input_ignores_privileged_fields(self):
        a = fake_transition(0, 0); b = fake_transition(999, -999, obstacle=(1, 2, 3))
        ia, pa = encode_observation(a["observation"]); ib, pb = encode_observation(b["observation"])
        self.assertTrue(np.array_equal(ia, ib) and np.array_equal(pa, pb))
        self.assertEqual(pa.shape, (PROPRIO_DIM,))

    def test_mock_transitions_pass_real_client_validation(self):
        c = MockClient(max_steps=5)
        Client.validate_transition(c.reset(3))
        for _ in range(5):
            Client.validate_transition(c.step(Action(forward=1, turn=0.5)))
        self.assertTrue(c.done)


class Wrappers(unittest.TestCase):
    def test_env_shapes_and_episode_end(self):
        env = TalosEnv(MockClient(max_steps=200), ExploreTask(), [7], max_episode_steps=6)
        img, pro = env.reset()
        self.assertEqual(img.shape, (3, *IMAGE_HW)); self.assertEqual(img.dtype, np.uint8)
        for i in range(6):
            (img, pro), r, done, info = env.step(np.array([1, 0, 0, 0.0]))
        self.assertTrue(done and info["truncated"]); self.assertEqual(info["episode"]["length"], 6)

    def test_vecenv_autoresets(self):
        v = VecEnv([TalosEnv(MockClient(), ExploreTask(), [s], max_episode_steps=3) for s in (1, 2)])
        img, pro = v.reset()
        self.assertEqual(img.shape, (2, 3, *IMAGE_HW))
        dones = []
        for _ in range(3):
            img, pro, r, d, infos = v.step(np.zeros((2, 4)))
            dones.append(d)
        self.assertTrue(np.all(dones[-1] == 1))
        img, pro, r, d, infos = v.step(np.zeros((2, 4)))  # stepping after auto-reset must work
        self.assertTrue(np.all(d == 0))

    def test_mock_collision_blocks(self):
        c = MockClient(); c.reset(0)
        blocked = [c.step(Action(forward=1))["observation"]["contacts"]["blocked"] for _ in range(80)]
        self.assertTrue(any(blocked))

    def test_mock_reach_is_achievable(self):
        c = MockClient(); t = ReachCrateTask(); tr = c.reset(5); t.reset(tr)
        ox, oy, _ = tr["privileged"]["obstacle_position_cm"]
        yaw = math.degrees(math.atan2(oy, ox))  # privileged steering, test-only
        for _ in range(int(abs(yaw) / 9) + 1):
            tr = c.step(Action(turn=max(-1, min(1, yaw / 9)))); yaw -= max(-9, min(9, yaw))
        done = False
        for _ in range(60):
            tr = c.step(Action(forward=1)); _, done, _ = t.reward(tr)
            if done: break
        self.assertTrue(done)


class Prototype(unittest.TestCase):
    def test_preroll_is_deterministic_and_varied(self):
        self.assertEqual(preroll_actions(5), preroll_actions(5))
        self.assertGreater(len({len(preroll_actions(s)) for s in range(20)}), 5)

    def test_teacher_solves_reach_and_baseline_does_not(self):
        seeds = EVAL_SEEDS[:15]
        teacher = summarise(run_policy(MockClient(), CrateTeacher(), "reach", seeds))
        self.assertEqual(teacher["success_rate"], 1.0)
        from talos_brain.policies import ForwardPolicy
        forward = summarise(run_policy(MockClient(), ForwardPolicy(), "reach", seeds))
        self.assertLess(forward["success_rate"], 0.6)

    def test_collect_train_sk_and_drive(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for args in (["talos_brain.collect", "--backend", "mock", "--episodes", "60", "--out", f"{d}/r0"],
                         ["talos_brain.train_sk", "--data", f"{d}/r0", "--out", f"{d}/sk/sk.pkl", "--max-iter", "40"]):
                out = subprocess.run([sys.executable, "-m", *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
                self.assertEqual(out.returncode, 0, out.stderr)
            from talos_brain.policies import SkPolicy
            student = summarise(run_policy(MockClient(), SkPolicy(f"{d}/sk/sk.pkl"), "reach", EVAL_SEEDS[:10]))
            self.assertGreaterEqual(student["success_rate"], 0.7)


class Cli(unittest.TestCase):
    def test_evaluate_and_benchmark_run_on_mock(self):
        out = subprocess.run([sys.executable, "-m", "talos_brain.evaluate", "--backend", "mock", "--task", "reach",
                              "--policies", "random,forward,teacher", "--episodes", "2"], cwd=ROOT, capture_output=True, text=True, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr)
        bench = ROOT / "tests" / "_bench_tmp.json"
        out = subprocess.run([sys.executable, "-m", "talos_brain.benchmark", "--backend", "mock", "--mock-count", "2",
                              "--steps", "20", "--warmup", "2", "--out", str(bench)], cwd=ROOT, capture_output=True, text=True, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr)
        report = json.loads(bench.read_text()); bench.unlink()
        self.assertEqual([r["instances"] for r in report["results"]], [1, 2])


if __name__ == "__main__":
    unittest.main()
