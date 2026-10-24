# talos_brain: the first brain for Talos

**For the 3-day prototype, follow [PROTOTYPE.md](PROTOTYPE.md).**

A learned brain that controls the avatar using only the policy observation. It is trained first by imitating a privileged teacher (behaviour cloning + DAgger), and optionally fine-tuned with recurrent PPO. It does not claim intelligence.

```
ego RGB (60x80) ──► CNN "eyes" ─┐
heading/pitch/velocity/blocked ─► MLP "body sense" ─┴─► GRU "short-term memory" ─► 4 actions (+ value)
teacher (knows crate position) ──► action labels for training only        (the brain never sees privileged data)
```

| File | Role |
| --- | --- |
| `env.py` | Wraps `erl.client.Client`: downscales the image, builds the 7-dim body vector, keeps privileged data out of the brain's inputs. Scripted start-pose randomisation (`preroll_actions`). `VecEnv` steps several instances in parallel. |
| `tasks.py` | Rewards computed client-side: `reach` (walk to the seeded crate; room/home worlds), `explore`, `goal`. Frozen train/test seed split. |
| `expert.py` | The privileged teacher: search by turning right until the crate is in view, then steer to it. |
| `policies.py` | random, walk-forward rule, teacher, scikit-learn brain, PyTorch brain behind one interface. |
| `collect.py` | Teacher-labelled episodes (with noise) and DAgger rounds where the student drives. |
| `train_bc.py` | Behaviour cloning of the CNN+GRU brain on whole episodes. |
| `train_sk.py` | Fallback reactive brain (scikit-learn MLP), no PyTorch needed. |
| `train_ppo.py` | Recurrent PPO, optionally starting from a cloned brain (`--init-from`). |
| `evaluate.py` | Success rate and steps on held-out seeds for any set of policies. |
| `demo.py` | Records brain-driven episodes with the Talos recorder, producing `report.html` replays. |
| `peek.py` | Contact sheet of what the brain sees, from collected data. |
| `benchmark.py` | Steps/s and latency for 1..N concurrent instances. |
| `smoke.py` | Runs the whole PyTorch path on the mock in a few minutes. Run it first. |
| `mock_sim.py` | **Mock** numpy raycaster with the same API, for debugging code only. Not simulation evidence. |

Launch instances with `-Offscreen` (rendered). `-Headless` is NullRHI: it has no camera, so the brain is blind.

Tests: `python -m unittest discover -s tests` (includes `tests/test_brain.py`; mock-backed, no PyTorch needed).
