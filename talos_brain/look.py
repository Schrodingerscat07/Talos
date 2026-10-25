"""Spin the avatar on the spot and save what its camera sees: check a new world looks right before training.

    python -m talos_brain.look --instances w1 --out look.png
Full 160x120 frames, one every 4 steps (~36 degrees), covering a full turn.
"""
from __future__ import annotations

import argparse

import numpy as np
from PIL import Image, ImageDraw

from erl.client import Action

from .env import decode_rgb


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["mock", "talos"], default="talos")
    p.add_argument("--instances", default="trial")
    p.add_argument("--out", default="look.png")
    p.add_argument("--steps", type=int, default=40, help="turn steps (about 9 degrees each)")
    p.add_argument("--every", type=int, default=4)
    args = p.parse_args()
    if args.backend == "mock":
        from .mock_sim import MockClient; client = MockClient()
    else:
        from erl.manage import client_for; client = client_for(args.instances.split(",")[0])
    t = client.reset(seed=0)
    frames = [(0, t)]
    for i in range(1, args.steps + 1):
        t = client.step(Action(turn=1.0))
        if i % args.every == 0:
            frames.append((i, t))
    tiles = []
    for i, tr in frames:
        im = Image.fromarray(decode_rgb(tr["observation"]["rgb"], hw=(120, 160)).transpose(1, 2, 0))
        ImageDraw.Draw(im).text((3, 2), f"step {i} heading {tr['observation']['proprioception']['heading_deg']:.0f}", fill=(255, 255, 0))
        tiles.append(np.asarray(im))
    cols = 5
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.concatenate(tiles[r:r + cols], 1) for r in range(0, len(tiles), cols)]
    Image.fromarray(np.concatenate(rows, 0)).save(args.out)
    print(f"wrote {args.out}: {len(frames)} frames over {args.steps} turn steps")


if __name__ == "__main__":
    main()
