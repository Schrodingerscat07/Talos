"""Record brain-driven episodes with the existing Talos recorder -> runs/brain_demo/<run>/report.html.

    python -m talos_brain.demo --backend talos --instances w1 --policy brain --checkpoint runs_brain/bc1/brain.pt --episodes 5
Open each report with scripts/view.ps1 -Run <run dir>. Frames before the brain takes control are the
scripted start-pose pre-roll; the manifest says so. Use held-out seeds so the demo is honest.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path

from erl.config import ROOT
from erl.recorder import Recorder

from .evaluate import run_policy, summarise
from .policies import make_policy
from .tasks import EVAL_SEEDS, resolve_targets


def provenance(policy, checkpoint, instance, backend):
    base = {}
    if backend == "talos":
        try:
            from erl.cli import runtime_provenance
            base = runtime_provenance(instance)
        except Exception as exc:  # provenance must never silently claim more than it has
            base = {"provenance_error": str(exc)}
    sha = hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest() if checkpoint else None
    return {**base, "policy": policy.name, "learning": not policy.privileged, "privileged_policy": policy.privileged,
            "checkpoint": checkpoint, "checkpoint_sha256": sha,
            "assistance": ["scripted start-pose pre-roll before step control passes to the policy",
                           "reward computed client-side from privileged position (not a policy input)"]}


class EpisodeRecorder:
    """Starts a new Recorder at every reset (step 0), as the recorder requires one per episode."""

    def __init__(self, root, spec, prov):
        self.root, self.spec, self.prov, self.rec, self.paths = root, spec, prov, None, []

    def __call__(self, transition, action):
        if transition["step_index"] == 0:
            self.close()
            self.rec = Recorder(self.root, self.spec, transition["privileged"]["seed"], copy.deepcopy(self.prov))
            self.paths.append(self.rec.path)
        self.rec.append(transition, action)

    def close(self, error=None):
        if self.rec:
            self.rec.close(error); self.rec = None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["mock", "talos"], default="talos")
    p.add_argument("--instances", default="trial")
    p.add_argument("--policy", default="brain", help="brain | sk | teacher | forward | random")
    p.add_argument("--checkpoint")
    p.add_argument("--task", default="reach")
    p.add_argument("--episodes", type=int, default=5)
    p.add_argument("--layout", help="two-target layout name (must match the running world)")
    p.add_argument("--first-seed-index", type=int, default=0, help="index into the held-out EVAL_SEEDS")
    p.add_argument("--runs", default=str(ROOT / "runs" / "brain_demo"))
    args = p.parse_args()
    if args.backend == "mock":
        from .mock_sim import MockClient; client = MockClient()
    else:
        from erl.manage import client_for; client = client_for(args.instances.split(",")[0])
    targets = resolve_targets(args.layout) if args.task == "two" else None
    policy = make_policy(args.policy, args.checkpoint, args.task, targets)
    recorder = EpisodeRecorder(Path(args.runs), client.spec(), provenance(policy, args.checkpoint, args.instances, args.backend))
    seeds = EVAL_SEEDS[args.first_seed_index:args.first_seed_index + args.episodes]
    try:
        rows = run_policy(client, policy, args.task, seeds, on_transition=recorder,
                          task_kwargs={"targets_cm": targets} if targets else None)
    except BaseException as exc:
        recorder.close(str(exc)); raise
    recorder.close()
    print(summarise(rows))
    for path, row in zip(recorder.paths, rows):
        print(f"seed {row['seed']}: {'SUCCESS' if row['success'] else 'miss'} in {row['steps']} steps -> {path / 'report.html'}")


if __name__ == "__main__":
    main()
