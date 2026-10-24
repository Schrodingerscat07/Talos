"""Recurrent PPO baseline (Phase 3). Resumable, checkpointed, with recorded run conditions.

Debug the learning loop on the mock first:
    python -m talos_brain.train_ppo --backend mock --envs 4 --total-steps 200000 --out runs_brain/mock1
Then on real Unreal instances (launched with scripts/launch.ps1, rendered, not NullRHI):
    python -m talos_brain.train_ppo --backend talos --instances w1,w2,w3,w4 --total-steps 1000000 --out runs_brain/explore1
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
import torch

from .env import TalosEnv, VecEnv
from .model import Brain
from .tasks import TASKS, TRAIN_SEEDS, EVAL_SEEDS


def make_envs(args):
    clients = []
    if args.backend == "mock":
        from .mock_sim import MockClient
        clients = [MockClient(max_steps=args.max_steps) for _ in range(args.envs)]
    else:
        from erl.manage import client_for
        clients = [client_for(name.strip()) for name in args.instances.split(",")]
    # Each instance gets a disjoint slice of the training seeds.
    n = len(clients)
    return VecEnv([TalosEnv(c, TASKS[args.task](), TRAIN_SEEDS[i::n], max_episode_steps=args.max_episode_steps)
                   for i, c in enumerate(clients)])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["mock", "talos"], default="mock")
    p.add_argument("--instances", default="trial")
    p.add_argument("--envs", type=int, default=4, help="mock only")
    p.add_argument("--max-steps", type=int, default=500, help="mock only; Talos uses its profile horizon")
    p.add_argument("--task", choices=list(TASKS), default="reach")
    p.add_argument("--max-episode-steps", type=int, default=150)
    p.add_argument("--init-from", help="start from a behaviour-cloned brain.pt (fine-tuning)")
    p.add_argument("--total-steps", type=int, default=200_000)
    p.add_argument("--rollout", type=int, default=128)
    p.add_argument("--seq-len", type=int, default=16)
    p.add_argument("--epochs", type=int, default=4)
    p.add_argument("--minibatches", type=int, default=4)
    p.add_argument("--lr", type=float, default=2.5e-4)
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument("--lam", type=float, default=0.95)
    p.add_argument("--clip", type=float, default=0.2)
    p.add_argument("--ent", type=float, default=0.005)
    p.add_argument("--vf", type=float, default=0.5)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", default="runs_brain/run")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = p.parse_args()
    assert args.rollout % args.seq_len == 0

    torch.manual_seed(args.seed); np.random.seed(args.seed)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    dev = torch.device(args.device)
    envs = make_envs(args)
    N, T = len(envs.envs), args.rollout
    brain = Brain().to(dev)
    if args.init_from and not (out / "checkpoint.pt").exists():
        brain.load_state_dict(torch.load(args.init_from, map_location=dev, weights_only=False)["model"])
    opt = torch.optim.Adam(brain.parameters(), lr=args.lr, eps=1e-5)
    step = 0
    ckpt = out / "checkpoint.pt"
    if ckpt.exists():
        state = torch.load(ckpt, map_location=dev, weights_only=False)
        brain.load_state_dict(state["model"]); opt.load_state_dict(state["opt"]); step = state["step"]
        print(f"resumed at step {step}")
    else:
        (out / "conditions.json").write_text(json.dumps({
            "created": datetime.now(timezone.utc).isoformat(), "args": vars(args),
            "task": args.task, "task_reward_uses_privileged": list(TASKS[args.task].uses_privileged),
            "policy_inputs": ["ego_rgb_downscaled", "heading", "look_pitch", "local_velocity", "blocked"],
            "pretraining": args.init_from, "start_pose": "scripted pre-roll randomisation", "demonstrations": None, "train_seeds": [TRAIN_SEEDS[0], TRAIN_SEEDS[-1]],
            "eval_seeds": [EVAL_SEEDS[0], EVAL_SEEDS[-1]], "backend": args.backend,
        }, indent=2))

    log = (out / "metrics.jsonl").open("a")
    img, pro = envs.reset()
    starts = np.ones(N, dtype=np.float32)
    h = brain.initial_state(N, dev)
    recent = []
    t0 = time.time()

    while step < args.total_steps:
        # ---------------- collect rollout ----------------
        buf = {k: [] for k in ("img", "pro", "start", "act", "logp", "val", "rew", "done")}
        h_roll = h.clone()
        brain.eval()
        for _ in range(T):
            with torch.no_grad():
                ti = torch.as_tensor(img, device=dev)[None]
                tp = torch.as_tensor(pro, device=dev)[None]
                ts = torch.as_tensor(starts, device=dev)[None]
                dist, v, h = brain(ti, tp, h, ts)
                a = dist.sample()[0]
                logp = dist.log_prob(a[None]).sum(-1)[0]
            buf["img"].append(img); buf["pro"].append(pro); buf["start"].append(starts.copy())
            buf["act"].append(a.cpu().numpy()); buf["logp"].append(logp.cpu().numpy()); buf["val"].append(v[0].cpu().numpy())
            img, pro, r, d, infos = envs.step(a.cpu().numpy())
            buf["rew"].append(r); buf["done"].append(d)
            starts = d.copy()
            for info in infos:
                if "episode" in info:
                    recent.append(info["episode"]["return"])
            step += N
        with torch.no_grad():
            _, last_v, _ = brain(torch.as_tensor(img, device=dev)[None], torch.as_tensor(pro, device=dev)[None],
                                 h, torch.as_tensor(starts, device=dev)[None])
        B = {k: np.asarray(v) for k, v in buf.items()}
        # ---------------- GAE ----------------
        adv = np.zeros((T, N), dtype=np.float32); gae = 0
        nxt = last_v[0].cpu().numpy()
        for t in reversed(range(T)):
            nonterm = 1.0 - B["done"][t]
            delta = B["rew"][t] + args.gamma * nxt * nonterm - B["val"][t]
            gae = delta + args.gamma * args.lam * nonterm * gae
            adv[t] = gae; nxt = B["val"][t]
        ret = adv + B["val"]

        # ---------------- PPO update on sequences ----------------
        # Recompute hidden states at each sequence start with the pre-update net.
        brain.train()
        S = T // args.seq_len
        with torch.no_grad():
            hs, hh = [], h_roll
            for s in range(S):
                sl = slice(s * args.seq_len, (s + 1) * args.seq_len)
                hs.append(hh)
                _, _, hh = brain(torch.as_tensor(B["img"][sl], device=dev), torch.as_tensor(B["pro"][sl], device=dev),
                                 hh, torch.as_tensor(B["start"][sl], device=dev))
        chunks = [(s, n) for s in range(S) for n in range(N)]
        tens = {k: torch.as_tensor(B[k], device=dev) for k in ("img", "pro", "start", "act", "logp")}
        tadv, tret = torch.as_tensor(adv, device=dev), torch.as_tensor(ret, device=dev)
        for _ in range(args.epochs):
            np.random.shuffle(chunks)
            for mb in np.array_split(np.array(chunks), args.minibatches):
                if len(mb) == 0:
                    continue
                sidx, nidx = mb[:, 0], mb[:, 1]
                tidx = (sidx[:, None] * args.seq_len + np.arange(args.seq_len)[None]).T  # [L, M]
                ti_ = torch.as_tensor(tidx, device=dev)
                ni_ = torch.as_tensor(np.ascontiguousarray(np.broadcast_to(nidx, tidx.shape)), device=dev)
                g = lambda x: x[ti_, ni_]
                h0 = torch.cat([hs[s][:, n:n + 1] for s, n in mb], 1)
                dist, v, _ = brain(g(tens["img"]), g(tens["pro"]), h0, g(tens["start"]))
                logp = dist.log_prob(g(tens["act"])).sum(-1)
                a_ = g(tadv); a_ = (a_ - a_.mean()) / (a_.std() + 1e-8)
                ratio = (logp - g(tens["logp"])).exp()
                pg = -torch.min(ratio * a_, ratio.clamp(1 - args.clip, 1 + args.clip) * a_).mean()
                vl = 0.5 * (v - g(tret)).pow(2).mean()
                ent = dist.entropy().sum(-1).mean()
                loss = pg + args.vf * vl - args.ent * ent
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(brain.parameters(), 0.5); opt.step()

        row = {"step": step, "mean_return_last20": float(np.mean(recent[-20:])) if recent else None,
               "episodes": len(recent), "policy_loss": pg.item(), "value_loss": vl.item(), "entropy": ent.item(),
               "steps_per_s": step / max(time.time() - t0, 1e-6)}
        log.write(json.dumps(row) + "\n"); log.flush()
        print(row)
        torch.save({"model": brain.state_dict(), "opt": opt.state_dict(), "step": step, "kind": "ppo", "image_hw": brain.image_hw}, ckpt)


if __name__ == "__main__":
    main()
