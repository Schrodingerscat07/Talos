"""Load collected episodes (one or more round directories)."""
from __future__ import annotations

from pathlib import Path

import numpy as np


def load_episodes(dirs: list[str]) -> list[dict]:
    episodes = []
    for d in dirs:
        for f in sorted(Path(d).glob("ep_*.npz")):
            with np.load(f) as z:
                episodes.append({k: z[k] for k in ("images", "proprio", "label")} | {"seed": int(z["seed"]), "file": str(f)})
    if not episodes:
        raise SystemExit(f"no episodes found in {dirs}")
    return episodes


def split_by_seed(episodes, val_fraction=0.1, seed=0):
    """Validation split by episode (never by frame), so neighbouring frames don't leak."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(episodes))
    n_val = max(1, int(len(episodes) * val_fraction))
    return [episodes[i] for i in idx[n_val:]], [episodes[i] for i in idx[:n_val]]
