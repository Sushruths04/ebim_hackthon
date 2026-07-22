# Task 3 Run Outputs — Data Inventory (HuggingFace backup)

> The heavy run artifacts (GIFs, frames, result.json) are **NOT** in git — they
> live in a private HuggingFace dataset. This file is the map so you can find
> and re-download them later.

## Where the data lives

- **HuggingFace dataset (private):**
  https://huggingface.co/datasets/sush0401/ebim-task3-outputs
  - Download later with: `hf download sush0401/ebim-task3-outputs --repo-type dataset --local-dir ./outputs`
- **Local copy (until you delete the old folders):**
  `EBiM-benchmark-codex/outputs/` (~5.8 GB) and inside `ebim/.git` history.
- Upload was kicked off 2026-07-22; the small proven proofs went first, the
  bulk (grasp-opt sweeps) uploads in the background and is resumable.

## The proofs that matter (upload-first, high value)

| Folder | Size | What it is | Verdict |
|---|---|---|---|
| `task3_grasp_reliability_official_20260718/` | 244 K | The official **10/10 cup grasp-lift** reliability gate | ✅ `pass_rate 1.0, gate_passed true` — the proven grasp |
| `task3_north_stance_nav_r1/` | 187 M | **Navigation** gate proof | ✅ `passed true, position_error 2.98 cm` |
| `task3_stage4_grasp_POC/` | 30 M | This session's **r-poc1** Stage-4 grasp attempt (constants-fix test) | ❌ `passed false, failed_phase hold` (grasp not caged; see runbook) |
| `task3_grasp_effort_calibration/` | 89 M | Close-effort scale calibration runs | reference |

## The bulk (large, lower value — failed-run tuning sweeps)

| Folder | Size | What it is |
|---|---|---|
| `grasp_opt/` | 959 M | Bayesian grasp-optimization trial sweep |
| `grasp_opt_invalid_pre_timeout_fix/` | 893 M | Earlier (invalid) grasp-opt sweep, pre timeout-fix |
| `task3_transport_cup_r9 … r32/` (~15 dirs, ~90 M each) | ~1.4 G | The full-nav cup grasp/transport tuning series (all failed at `hold`; the story is in `docs/AGENT_STATE.md`) |
| `task3_cup_east_*_pickup_r1/`, `task3_transport_bowl2_r1/`, etc. | ~0.5 G | Assorted per-object / per-stance pickup attempts |

**Total: ~5.8 GB.** Most of it is failed-run diagnostic GIFs/frames — kept for
the record, but only the four "proofs that matter" above are worth re-examining.

## How to check what actually landed on HF

```
hf repo-files sush0401/ebim-task3-outputs --repo-type dataset | head
```

If the bulk upload was interrupted, just re-run the same upload command — it
skips files already present:
```
hf upload sush0401/ebim-task3-outputs "<local outputs path>" . --repo-type dataset
```
