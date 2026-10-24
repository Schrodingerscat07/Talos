"""Compare policies on held-out seeds (rooms and start poses never used in training).

    python -m talos_brain.evaluate --backend talos --instances w1 --task reach \
        --policies random,forward,teacher,brain --checkpoint runs_brain/bc1/brain.pt --episodes 30 --out eval.json
`teacher` cheats (reads the crate position); it is the upper bound, not a competitor.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

import numpy as np

from .env import TalosEnv
from .policies import make_policy
from .tasks import EVAL_SEEDS, TASKS


def run_policy(client, policy, task_name, seeds, max_episode_steps=150, on_transition=None):
    env = TalosEnv(client, TASKS[task_name](), seeds, max_episode_steps=max_episode_steps, on_transition=on_transition)
    rows = []
    for _ in seeds:
        img, pro = env.reset(); policy.reset(); done = False
        while not done:
            (img, pro), r, done, info = env.step(policy.act(img, pro, env.last_transition))
        rows.append({"seed": env.seed, "return": info["episode"]["return"], "steps": info["episode"]["length"],
                     "success": bool(info.get("success")), "final_distance_cm": info.get("distance_cm")})
    return rows


def summarise(rows):
    succ = [r for r in rows if r["success"]]
    return {"episodes": len(rows), "success_rate": round(len(succ) / len(rows), 3),
            "mean_steps_when_successful": round(float(np.mean([r["steps"] for r in succ])), 1) if succ else None,
            "mean_return": round(float(np.mean([r["return"] for r in rows])), 2)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["mock", "talos"], default="mock")
    p.add_argument("--instances", default="trial")
    p.add_argument("--task", choices=list(TASKS), default="reach")
    p.add_argument("--policies", default="random,forward,teacher")
    p.add_argument("--checkpoint", help="brain .pt (brain) or sk .pkl (sk)")
    p.add_argument("--episodes", type=int, default=20)
    p.add_argument("--max-episode-steps", type=int, default=150)
    p.add_argument("--blind", action="store_true", help="ablation: black out the camera for learned policies")
    p.add_argument("--out")
    args = p.parse_args()
    if args.backend == "mock":
        from .mock_sim import MockClient; client = MockClient()
    else:
        from erl.manage import client_for; client = client_for(args.instances.split(",")[0])
    seeds = EVAL_SEEDS[:args.episodes]
    report = {"created": datetime.now(timezone.utc).isoformat(), "backend": args.backend, "task": args.task,
              "eval_seeds": [seeds[0], seeds[-1]], "checkpoint": args.checkpoint, "blind": args.blind, "results": {}}
    for name in args.policies.split(","):
        policy = make_policy(name, args.checkpoint)
        if args.blind and not policy.privileged:
            inner_act = policy.act
            policy.act = lambda img, pro, t=None, f=inner_act: f(np.zeros_like(img), pro, t)
            name = name + "_blind"
        rows = run_policy(client, policy, args.task, seeds, args.max_episode_steps)
        report["results"][name] = summarise(rows) | {"privileged": policy.privileged, "episodes_detail": rows}
        s = report["results"][name]
        print(f"{name:10s} success {s['success_rate']:.0%}  steps {s['mean_steps_when_successful']}  return {s['mean_return']}"
              + ("   (privileged upper bound)" if policy.privileged else ""), flush=True)
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
