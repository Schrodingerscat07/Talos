"""Day-1 first command: exercises the whole PyTorch path on the mock in a few minutes.

    python -m talos_brain.smoke
Collect -> train_bc (2 epochs) -> evaluate brain -> DAgger collect with the brain -> 2 PPO updates.
If this passes, the code works on your machine; it says nothing about learning quality or Unreal.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time


def run(*args):
    t = time.time()
    print("$ python -m", " ".join(args), flush=True)
    subprocess.run([sys.executable, "-m", *args], check=True)
    print(f"  ok ({time.time() - t:.0f}s)\n", flush=True)


def main():
    import torch  # fail early with a clear message
    print("torch", torch.__version__, "cuda" if torch.cuda.is_available() else "cpu", "\n")
    with tempfile.TemporaryDirectory() as d:
        run("talos_brain.collect", "--backend", "mock", "--episodes", "24", "--out", f"{d}/r0")
        run("talos_brain.train_bc", "--data", f"{d}/r0", "--out", f"{d}/bc", "--epochs", "2", "--batch-size", "8")
        run("talos_brain.evaluate", "--backend", "mock", "--policies", "brain", "--checkpoint", f"{d}/bc/brain.pt", "--episodes", "3")
        run("talos_brain.collect", "--backend", "mock", "--episodes", "6", "--out", f"{d}/r1", "--seed-offset", "24",
            "--student", f"{d}/bc/brain.pt", "--student-kind", "brain", "--beta", "0.0")
        run("talos_brain.train_bc", "--data", f"{d}/r0", f"{d}/r1", "--out", f"{d}/bc1", "--epochs", "1", "--init", f"{d}/bc/brain.pt")
        run("talos_brain.train_ppo", "--backend", "mock", "--envs", "2", "--total-steps", "64", "--rollout", "32",
            "--seq-len", "16", "--init-from", f"{d}/bc1/brain.pt", "--out", f"{d}/ppo")
    print("SMOKE PASSED: the PyTorch pipeline runs end to end on the mock.")


if __name__ == "__main__":
    main()
