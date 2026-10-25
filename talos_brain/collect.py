"""Collect teacher-labelled episodes for imitation learning.

Round 0 (teacher drives, with noise so the data includes recoveries from mistakes):
    python -m talos_brain.collect --backend talos --instances w1,w2 --episodes 400 --out data/round0
DAgger round (the student drives part of the time, the teacher still labels every frame):
    python -m talos_brain.collect --backend talos --instances w1,w2 --episodes 200 --out data/round1 \
        --student runs_brain/bc0/brain.pt --student-kind brain --beta 0.3 --seed-offset 400

Each episode is one compressed .npz: images [T,3,60,80] uint8, proprio [T,7], label [T,4] (teacher),
executed [T,4] (what actually ran). collection.json records the conditions.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time

import numpy as np

from .env import IMAGE_HW, TalosEnv
from .expert import TEACHERS, make_teacher
from .policies import make_policy
from .tasks import TASKS, TRAIN_SEEDS, resolve_targets


TARGETS = None   # set from --layout in main(); used by workers


def make_clients(args):
    if args.backend == "mock":
        from .mock_sim import MockClient
        return [MockClient() for _ in range(args.mock_count)]
    from erl.manage import client_for
    return [client_for(n.strip()) for n in args.instances.split(",")]


def run_worker(i, client, seeds, args, out, lock, stats):
    teacher = make_teacher(args.task, TARGETS)
    student = make_policy(args.student_kind, args.student) if args.student else None
    rng = np.random.default_rng(10_000 + i + args.seed_offset)
    env = TalosEnv(client, TASKS[args.task](**({"targets_cm": TARGETS} if args.task == "two" else {})), seeds, max_episode_steps=args.max_episode_steps)
    for _ in range(len(seeds)):
        img, pro = env.reset()
        teacher.reset()
        if student: student.reset()
        use_student = student is not None and rng.random() > args.beta   # per-episode mixing
        imgs, pros, labels, execd = [], [], [], []
        done, info = False, {}
        while not done:
            label = teacher.act(img, pro, env.last_transition)
            if use_student:
                action = student.act(img, pro)
            else:
                action = label.copy()
                if rng.random() < args.noise_prob:     # DART-style noise: teaches recovery
                    action = action + rng.normal(0, args.noise_std, 4)
            action = np.clip(action, -1, 1)
            imgs.append(img); pros.append(pro); labels.append(label); execd.append(action)
            (img, pro), _, done, info = env.step(action)
        name = f"ep_{env.seed:07d}.npz"
        np.savez_compressed(out / name, images=np.stack(imgs), proprio=np.stack(pros),
                            label=np.stack(labels).astype(np.float32), executed=np.stack(execd).astype(np.float32),
                            success=bool(info.get("success")), seed=env.seed, driver="student" if use_student else "teacher")
        with lock:
            stats["episodes"] += 1; stats["frames"] += len(imgs); stats["success"] += int(bool(info.get("success")))
            if stats["episodes"] % 10 == 0:
                rate = stats["frames"] / (time.time() - stats["t0"])
                print(f"{stats['episodes']} episodes, {stats['frames']} frames, teacher/student success "
                      f"{stats['success'] / stats['episodes']:.2f}, {rate:.1f} frames/s", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["talos", "mock"], default="talos")
    p.add_argument("--instances", default="trial")
    p.add_argument("--mock-count", type=int, default=2)
    p.add_argument("--task", default="reach", choices=list(TASKS))
    p.add_argument("--episodes", type=int, default=400)
    p.add_argument("--max-episode-steps", type=int, default=150)
    p.add_argument("--seed-offset", type=int, default=0, help="start index into TRAIN_SEEDS; use a new range per round")
    p.add_argument("--noise-prob", type=float, default=0.3)
    p.add_argument("--noise-std", type=float, default=0.5)
    p.add_argument("--student", help="checkpoint for DAgger rounds")
    p.add_argument("--student-kind", default="brain", choices=["brain", "sk"])
    p.add_argument("--beta", type=float, default=0.3, help="probability an episode is driven by the teacher")
    p.add_argument("--layout", help="two-target world layout name from configs/two_layouts.json (must match the running world)")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    global TARGETS
    TARGETS = resolve_targets(args.layout) if args.task == "two" else None
    if args.task not in TEACHERS:
        raise SystemExit(f"no teacher for task {args.task}; choose one of {list(TEACHERS)}")
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    clients = make_clients(args)
    seeds = TRAIN_SEEDS[args.seed_offset:args.seed_offset + args.episodes]
    if len(seeds) < args.episodes:
        raise SystemExit("not enough training seeds left; lower --seed-offset/--episodes")
    (out / "collection.json").write_text(json.dumps({
        "created": datetime.now(timezone.utc).isoformat(), "args": vars(args), "image_hw": IMAGE_HW,
        "teacher": TEACHERS[args.task].name, "task": args.task, "layout": args.layout, "targets_cm": TARGETS, "teacher_uses_privileged": ["position_cm", "obstacle_position_cm (reach) or fixed target positions (two)"],
        "start_pose": "scripted pre-roll randomisation (talos_brain.env.preroll_actions)",
        "seeds": [seeds[0], seeds[-1]], "note": "Demonstrations from a privileged scripted teacher; record in any claim.",
    }, indent=2))
    lock, stats = threading.Lock(), {"episodes": 0, "frames": 0, "success": 0, "t0": time.time()}
    n = len(clients)
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(run_worker, i, c, seeds[i::n], args, out, lock, stats) for i, c in enumerate(clients)]
        for f in futures:
            f.result()
    print(f"done: {stats['episodes']} episodes, {stats['frames']} frames in {time.time() - stats['t0']:.0f}s -> {out}")


if __name__ == "__main__":
    main()
