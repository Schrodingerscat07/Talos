"""Every policy has reset() and act(img, pro, transition) -> 4 actions.

Only the teacher reads `transition` (privileged). Learned policies get img/pro arrays only.
"""
from __future__ import annotations

import pickle

import numpy as np

from .expert import make_teacher


class RandomPolicy:
    name, privileged = "random", False
    def __init__(self, seed=0): self.rng = np.random.default_rng(seed)
    def reset(self): pass
    def act(self, img, pro, transition=None): return self.rng.uniform(-1, 1, 4)


class ForwardPolicy:
    """Hand-written rule using only the contact sensor: walk forward, turn while blocked."""
    name, privileged = "forward_rule", False
    def reset(self): self.turning = 0
    def act(self, img, pro, transition=None):
        if pro[6] > 0.5:
            self.turning = 8
        if self.turning:
            self.turning -= 1
            return np.array([0, 0, 1, 0.0])
        return np.array([1, 0, 0, 0.0])


def sk_features(img: np.ndarray, pro: np.ndarray) -> np.ndarray:
    """Tiny hand-made input for the scikit-learn fallback brain: 20x15 colour thumbnail + body sense."""
    c, h, w = img.shape
    thumb = img.reshape(c, 15, h // 15, 20, w // 20).mean(axis=(2, 4)) / 255.0
    return np.concatenate([thumb.ravel(), pro]).astype(np.float32)


class SkPolicy:
    """Reactive fallback brain (no memory) trained by train_sk.py."""
    privileged = False
    def __init__(self, path):
        with open(path, "rb") as f:
            blob = pickle.load(f)
        self.model, self.name = blob["model"], "sk_" + blob.get("kind", "mlp")
    def reset(self): pass
    def act(self, img, pro, transition=None):
        return np.clip(self.model.predict(sk_features(img, pro)[None])[0], -1, 1)


class TorchPolicy:
    """The CNN + GRU brain, run step by step with its memory carried across steps."""
    privileged = False
    def __init__(self, path, device="cpu"):
        import torch
        from .model import Brain
        state = torch.load(path, map_location=device, weights_only=False)
        self.torch, self.dev = torch, device
        self.brain = Brain(image_hw=tuple(state.get("image_hw", (60, 80))), proprio_dim=state.get("proprio_dim", 7)).to(device)
        self.brain.load_state_dict(state["model"]); self.brain.eval()
        self.name = "brain_" + state.get("kind", "ppo")
    def reset(self):
        self.h, self.start = self.brain.initial_state(1, self.dev), 1.0
    def act(self, img, pro, transition=None):
        t = self.torch
        with t.no_grad():
            dist, _, self.h = self.brain(t.as_tensor(img, device=self.dev)[None, None],
                                         t.as_tensor(pro, device=self.dev)[None, None], self.h,
                                         t.tensor([[self.start]], device=self.dev))
        self.start = 0.0
        return dist.mean[0, 0].cpu().numpy()


def make_policy(name: str, checkpoint: str | None = None, task: str = "reach", targets=None):
    if name == "random": return RandomPolicy()
    if name in ("forward", "scripted"): return ForwardPolicy()
    if name == "teacher": return make_teacher(task, targets)
    if name == "sk": return SkPolicy(checkpoint)
    if name in ("brain", "trained"): return TorchPolicy(checkpoint)
    raise ValueError(f"unknown policy {name}")
