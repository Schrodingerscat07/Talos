"""Fallback brain: a small scikit-learn MLP trained on the same teacher data. No PyTorch, no memory.

    python -m talos_brain.train_sk --data data/round0 data/round1 --out runs_brain/sk0/sk.pkl
It is reactive (sees one frame at a time). It exists so a working prototype does not depend on a
PyTorch install, and to check quickly that the data is learnable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pickle
import time

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import load_episodes, split_by_seed
from .policies import sk_features


def to_xy(episodes):
    X = np.stack([sk_features(i, p) for e in episodes for i, p in zip(e["images"], e["proprio"])])
    Y = np.concatenate([e["label"] for e in episodes])
    return X, Y


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--hidden", default="256,128")
    p.add_argument("--max-iter", type=int, default=60)
    args = p.parse_args()
    t0 = time.time()
    train, val = split_by_seed(load_episodes(args.data))
    Xt, Yt = to_xy(train); Xv, Yv = to_xy(val)
    model = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=tuple(int(h) for h in args.hidden.split(",")),
                                                         max_iter=args.max_iter, early_stopping=True, random_state=0))
    model.fit(Xt, Yt)
    val_mse = float(np.mean((model.predict(Xv) - Yv) ** 2))
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump({"model": model, "kind": "mlp", "features": "thumb20x15+proprio"}, f)
    info = {"train_frames": len(Xt), "val_frames": len(Xv), "val_mse": round(val_mse, 4),
            "baseline_val_mse_predict_mean": round(float(np.mean((Yt.mean(0) - Yv) ** 2)), 4),
            "seconds": round(time.time() - t0, 1), "data": args.data}
    (out.parent / "sk_train.json").write_text(json.dumps(info, indent=2))
    print(info)


if __name__ == "__main__":
    main()
