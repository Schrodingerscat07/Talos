"""Contact sheet of what the brain sees, from collected data: check the crate is visible before training.

    python -m talos_brain.peek --data data/round0 --out peek.png
"""
from __future__ import annotations

import argparse

import numpy as np
from PIL import Image, ImageDraw

from .data import load_episodes


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", nargs="+", required=True)
    p.add_argument("--out", default="peek.png")
    p.add_argument("--rows", type=int, default=6)
    p.add_argument("--cols", type=int, default=8)
    args = p.parse_args()
    eps = load_episodes(args.data)[: args.rows]
    tiles = []
    for e in eps:
        idx = np.linspace(0, len(e["label"]) - 1, args.cols).astype(int)
        row = []
        for i in idx:
            im = Image.fromarray(e["images"][i].transpose(1, 2, 0)).resize((160, 120), Image.NEAREST)
            d = ImageDraw.Draw(im)
            f, s, t, _ = e["label"][i]
            d.text((3, 2), f"t{i} f{f:+.1f} t{t:+.1f}", fill=(255, 255, 0))
            row.append(np.asarray(im))
        tiles.append(np.concatenate(row, 1))
    Image.fromarray(np.concatenate(tiles, 0)).save(args.out)
    print(f"wrote {args.out}: {len(eps)} episodes x {args.cols} frames (teacher forward/turn labels overlaid)")


if __name__ == "__main__":
    main()
