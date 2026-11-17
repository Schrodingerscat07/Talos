"""Train the CNN + GRU brain to imitate the teacher (behaviour cloning on whole episodes).

    python -m talos_brain.train_bc --data data/round0 --out runs_brain/bc0 --epochs 15
    python -m talos_brain.train_bc --data data/round0 data/round1 --out runs_brain/bc1 --init runs_brain/bc0/brain.pt
Writes brain.pt (best validation loss), bc_metrics.jsonl and conditions.json.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
import torch

from .data import load_episodes, split_by_seed
from .env import IMAGE_HW
from .model import Brain


def batches(episodes, batch_size, rng=None):
    order = np.arange(len(episodes)) if rng is None else rng.permutation(len(episodes))
    for i in range(0, len(order), batch_size):
        eps = [episodes[j] for j in order[i:i + batch_size]]
        T, N = max(len(e["label"]) for e in eps), len(eps)
        img = np.zeros((T, N, *eps[0]["images"].shape[1:]), dtype=np.uint8)
        pro = np.zeros((T, N, eps[0]["proprio"].shape[1]), dtype=np.float32)
        lab = np.zeros((T, N, 4), dtype=np.float32)
        mask = np.zeros((T, N), dtype=np.float32)
        for n, e in enumerate(eps):
            L = len(e["label"])
            img[:L, n], pro[:L, n], lab[:L, n], mask[:L, n] = e["images"], e["proprio"], e["label"], 1
        starts = np.zeros((T, N), dtype=np.float32); starts[0] = 1
        yield img, pro, lab, mask, starts


def run_epoch(brain, episodes, dev, batch_size, opt=None, rng=None):
    total, count = 0.0, 0.0
    brain.train(opt is not None)
    for img, pro, lab, mask, starts in batches(episodes, batch_size, rng):
        t = lambda a: torch.as_tensor(a, device=dev)
        with torch.set_grad_enabled(opt is not None):
            dist, _, _ = brain(t(img), t(pro), brain.initial_state(img.shape[1], dev), t(starts))
            per = ((dist.mean - t(lab)) ** 2).mean(-1)          # [T, N]
            loss = (per * t(mask)).sum() / t(mask).sum()
            if opt is not None:
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(brain.parameters(), 1.0); opt.step()
        total += float(loss.item() * mask.sum()); count += float(mask.sum())
    return float(total / count)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--init", help="start from an earlier brain.pt (e.g. after a DAgger round)")
    p.add_argument("--epochs", type=int, default=15)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--threads", type=int, default=0, help="torch CPU threads (0 = default)")
    args = p.parse_args()
    if args.threads: torch.set_num_threads(args.threads)
    torch.manual_seed(0)
    dev = torch.device(args.device)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    train, val = split_by_seed(load_episodes(args.data))
    hw = tuple(train[0]["images"].shape[2:])
    pdim = int(train[0]["proprio"].shape[1])
    brain = Brain(image_hw=hw, proprio_dim=pdim).to(dev)
    if args.init:
        brain.load_state_dict(torch.load(args.init, map_location=dev, weights_only=False)["model"])
    opt = torch.optim.Adam(brain.parameters(), lr=args.lr)
    frames = sum(len(e["label"]) for e in train)
    (out / "conditions.json").write_text(json.dumps({
        "created": datetime.now(timezone.utc).isoformat(), "method": "behaviour cloning (MSE on action mean), whole-episode BPTT",
        "args": vars(args), "train_episodes": len(train), "val_episodes": len(val), "train_frames": frames,
        "image_hw": hw, "demonstrations": "privileged scripted teacher (see collection.json in each data dir)",
        "policy_inputs": ["ego_rgb", "heading", "look_pitch", "local_velocity", "blocked"],
    }, indent=2))
    print(f"train {len(train)} episodes / {frames} frames, val {len(val)} episodes, image {hw}, device {dev}")
    rng, best, log = np.random.default_rng(0), float("inf"), (out / "bc_metrics.jsonl").open("w")
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        tr = run_epoch(brain, train, dev, args.batch_size, opt, rng)
        va = run_epoch(brain, val, dev, args.batch_size)
        row = {"epoch": epoch, "train_mse": round(tr, 5), "val_mse": round(va, 5), "seconds": round(time.time() - t0, 1)}
        log.write(json.dumps(row) + "\n"); log.flush(); print(row, flush=True)
        if va < best:
            best = va
            torch.save({"model": brain.state_dict(), "kind": "bc", "image_hw": hw, "proprio_dim": pdim, "epoch": epoch, "val_mse": va}, out / "brain.pt")
    print(f"best val_mse {best:.5f} -> {out / 'brain.pt'}")


if __name__ == "__main__":
    main()
