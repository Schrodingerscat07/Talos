"""Stage 0 speed benchmark: how many simulator steps per second can training actually get?

Launch the instances first (rendered, same profile for all), then:
    python -m talos_brain.benchmark --instances w1,w2,w3,w4 --steps 300 --out bench.json
It measures 1, 2, ... N instances stepped concurrently (the way VecEnv steps them), so you can see
where adding instances stops helping. The first `--warmup` steps per instance are excluded.
Use `--backend mock` only to check the script itself; mock numbers say nothing about Unreal.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import platform
import time

import numpy as np

from erl.client import Action


def run_one(client, steps: int, warmup: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    client.reset(seed=seed)
    latencies = []
    for i in range(warmup + steps):
        if client.done:
            client.reset(seed=seed)
        a = rng.uniform(-1, 1, 4)
        t = time.perf_counter()
        client.step(Action(forward=a[0], strafe=a[1], turn=a[2], look=a[3]))
        if i >= warmup:
            latencies.append(time.perf_counter() - t)
    return latencies


def measure(clients, steps, warmup):
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(clients)) as pool:
        lat = list(pool.map(lambda ic: run_one(ic[1], steps, warmup, 1000 + ic[0]), enumerate(clients)))
    wall = time.perf_counter() - t0
    flat = np.concatenate(lat)
    # Throughput over the measured part only: total measured steps / summed measured time of the slowest worker.
    slowest = max(sum(x) for x in lat)
    return {
        "instances": len(clients),
        "steps_per_s_total": round(len(flat) / slowest, 2),
        "steps_per_s_per_instance": round(len(flat) / slowest / len(clients), 2),
        "latency_s": {"median": round(float(np.median(flat)), 4), "p95": round(float(np.percentile(flat, 95)), 4),
                      "max": round(float(flat.max()), 4)},
        "wall_s_including_warmup": round(wall, 1),
        "hours_per_million_steps": round(1e6 / (len(flat) / slowest) / 3600, 1),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["talos", "mock"], default="talos")
    p.add_argument("--instances", default="trial", help="comma-separated instance names (talos)")
    p.add_argument("--mock-count", type=int, default=4)
    p.add_argument("--steps", type=int, default=300)
    p.add_argument("--warmup", type=int, default=20)
    p.add_argument("--out", default="bench.json")
    args = p.parse_args()
    if args.backend == "mock":
        from .mock_sim import MockClient
        clients = [MockClient() for _ in range(args.mock_count)]
        spec = clients[0].spec()
    else:
        from erl.manage import client_for
        clients = [client_for(n.strip()) for n in args.instances.split(",")]
        spec = clients[0].spec()
    rows = []
    for n in range(1, len(clients) + 1):
        row = measure(clients[:n], args.steps, args.warmup)
        rows.append(row)
        print(row)
    report = {"created": datetime.now(timezone.utc).isoformat(), "backend": args.backend,
              "host": platform.platform(), "processor": platform.processor(),
              "spec_excerpt": {k: spec.get(k) for k in ("max_steps", "backend", "render_mode", "world", "avatar") if k in spec},
              "steps_measured_per_instance": args.steps, "results": rows,
              "note": "Record the render mode and profile; NullRHI numbers do not apply to RGB training."}
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
