# 3-day prototype runbook

**Goal for the demo:** a learned brain that sees only the first-person camera and its body sense. From a random start pose in a room it has never been tested in, it searches for the crate and walks to it. It is compared against random actions, a hand-written walk-forward rule, and the "cheating" teacher.

**Method: imitation learning (behaviour cloning + DAgger).** A scripted teacher that knows the crate's true position drives the avatar and labels every camera frame with the right action. The brain learns to copy those actions from pixels alone. This needs thousands of steps, not the millions RL needs, so it fits in 3 days on one laptop. PPO fine-tuning is optional.

**What has been proven so far:** the full pipeline (collect, train, evaluate, record) was run on the *mock* simulator in the cloud. With the scikit-learn fallback brain:

| Policy | Mock success, 50 held-out seeds |
| --- | --- |
| random | 20% |
| walk-forward rule | 26% |
| fallback brain (camera + body only) | 100% |
| same brain, camera blacked out | 30% |
| teacher (privileged) | 100% |

The PyTorch CNN+GRU brain could not be run there (no PyTorch available). Run `python -m talos_brain.smoke` first on your machine. None of this is Unreal evidence yet.

---

## Day 1: get data flowing (Sun)

```powershell
pip install torch numpy pillow scikit-learn
python -m unittest discover -s tests          # expect 33 passing
python -m talos_brain.smoke                   # PyTorch path end to end on the mock, a few minutes
```

1. **Human gates.** Your team records the Phase 1 / 2A pass decision (AGENTS.md requires a human, not an AI).
2. **Launch two rendered Manny instances.** Use `-Offscreen` (renders images). Do **not** use `-Headless` (NullRHI, no camera).
   ```powershell
   .\scripts\launch.ps1 -Profile configs/manny_brain.json -Instance w1 -Port 8781 -Offscreen
   .\scripts\launch.ps1 -Profile configs/manny_brain.json -Instance w2 -Port 8782 -Offscreen
   python -m erl.cli wait --instance w1 --wait-seconds 420
   python -m erl.cli wait --instance w2 --wait-seconds 420
   ```
   `manny_brain.json` is `manny_room.json` with a 300-step horizon (the original's is 24).
3. **Benchmark** (10 min): `python -m talos_brain.benchmark --instances w1,w2 --steps 200 --out bench.json`
4. **Teacher sanity check:** `python -m talos_brain.evaluate --backend talos --instances w1 --policies teacher,forward --episodes 10`
   Teacher should be close to 100%. If not, stop and fix that first: heading convention, reach distance, crate position.
5. **Collect round 0** (about 45–60 min with 2 instances):
   `python -m talos_brain.collect --instances w1,w2 --episodes 400 --out data/round0`
6. **Look at what the brain sees:** `python -m talos_brain.peek --data data/round0 --out peek.png`
   The crate must be clearly visible. If it is too dark, raise `render.eye_exposure` in the profile and recollect.
7. **Train both brains:**
   ```powershell
   python -m talos_brain.train_sk --data data/round0 --out runs_brain/sk0/sk.pkl
   python -m talos_brain.train_bc --data data/round0 --out runs_brain/bc0 --epochs 15
   python -m talos_brain.evaluate --backend talos --instances w1 --policies brain,sk --checkpoint runs_brain/bc0/brain.pt --episodes 20
   ```
   (`--checkpoint` applies to one learned policy at a time; run sk separately with its .pkl.)
8. **Overnight: DAgger round 1.** The brain drives most episodes and the teacher labels what it should have done:
   `python -m talos_brain.collect --instances w1,w2 --episodes 400 --seed-offset 400 --student runs_brain/bc0/brain.pt --beta 0.3 --out data/round1`

## Day 2: make it good (Mon)

```powershell
python -m talos_brain.train_bc --data data/round0 data/round1 --out runs_brain/bc1 --init runs_brain/bc0/brain.pt --epochs 10
python -m talos_brain.evaluate --backend talos --instances w1 --policies brain --checkpoint runs_brain/bc1/brain.pt --episodes 30
```
- If success is still well below the teacher, run round 2 (`--seed-offset 800 --student runs_brain/bc1/brain.pt`) and retrain. Each round usually closes much of the gap.
- **Ablation for credibility:** `python -m talos_brain.evaluate --backend talos --instances w1 --policies brain --checkpoint runs_brain/bc1/brain.pt --episodes 30 --blind`. With the camera blacked out it should drop to about the walk-forward baseline, which shows the brain uses vision.
- Optional overnight: PPO fine-tuning from the cloned brain:
  `python -m talos_brain.train_ppo --backend talos --instances w1,w2 --init-from runs_brain/bc1/brain.pt --total-steps 100000 --out runs_brain/ppo1`
  Only keep it if it beats bc1 on the held-out evaluation.

## Day 3: freeze and present (Tue)

1. Freeze the best checkpoint and do not retrain after this point.
2. **Final table**, 50 held-out seeds:
   ```powershell
   python -m talos_brain.evaluate --backend talos --instances w1 --policies random,forward,teacher,brain --checkpoint <best> --episodes 50 --out final_eval.json
   ```
3. **Recorded demos:** pick successes *and* one failure. Honest demos are more convincing.
   ```powershell
   python -m talos_brain.demo --instances w1 --policy brain --checkpoint <best> --episodes 6
   .\scripts\view.ps1 -Run runs/brain_demo/<run>
   ```
   The replay shows the ego camera (what the brain sees) next to the third-person view.
4. Slides: task, what the brain sees, the teacher-student method, results table, demo replays, limits.

## Fallbacks
- PyTorch trouble on Windows: present the scikit-learn brain (`--policy sk --checkpoint runs_brain/sk0/sk.pkl`). It is reactive, with no memory.
- Unreal unstable: a single instance still works, just twice as slow. Halve the episode counts.
- Last resort: show the mock pipeline, clearly labelled as mock.

## What you can honestly claim
"A learned visuomotor policy, trained by imitating a privileged scripted teacher, finds and reaches a crate from randomised start poses in held-out trials, using only first-person RGB and proprioception: X% success vs Y% for a walk-forward rule."

Also state:
- Start poses come from a scripted pre-roll.
- The reward and teacher use privileged positions.
- There is one room and one crate.
- Movement is the supplied kinematic controller.

Do not claim intelligence, learned locomotion or generalisation to other worlds.
