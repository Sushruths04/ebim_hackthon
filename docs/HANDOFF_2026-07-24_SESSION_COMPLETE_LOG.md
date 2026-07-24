# Task 3 — Complete Session Log (2026-07-24, Claude session)

**Purpose of this document:** a detailed, no-summarizing record of every
change made this session, every GPU run's real result, exact current file
state, and exact next steps — so a fresh agent (or a reviewing agent) can
pick this up with zero ambiguity when this session ends. This supersedes
`docs/HANDOFF_2026-07-24_FULL_PLAN_Claude_to_OpenCode.md` for **current
code state** (that doc's stage-1/stage-4/stage-3 sub-task breakdown is
still valid; its Stage 2 section is now stale — this doc is authoritative
for Stage 2). Read `docs/AGENT_STATE.md` top section too — it has the same
information in a more condensed, chronological form.

Current branch: `task3-current-clean`. Current HEAD as of this writing:
`75c4beb8`. All commits below are on this branch, in this order (oldest
first):

```
95c01faf docs: correct Stage 2 grasp handoff — run4-8 evidence unverified, VM not fresh
86590df6 fix: release base_hold_anchor during approach_spoon drive
438164ab docs: log real stage2_run9 GPU evidence + root cause + fix, run10 pending
8aef9f66 fix: lift arm clear before approach_spoon drive, re-descend after
2062acb0 docs: unify OpenCode self-review with GPU-verified Stage 2 evidence chain
8b1e373f diag: expose approach_spoon x-offset as --approach-offset-x
d21c5d86 docs: persist durable operating plan + RL/PPO decision to AGENT_STATE.md
60580fd1 docs: real root cause of Stage 2 grasp failure — descend misses, gripper closes on empty air
b4c2f629 docs: full detailed plan + handoff for OpenCode, all 4 stages sub-tasked
8547a1b3 docs: point AGENT_STATE.md to the full plan handoff
6fb38561 docs: Stage 1 fresh baseline finding — arm collapses during drag, IK breakdown
f2ed641c docs: correct + deepen Stage 1 root-cause with verified mechanism
3cb9bf00 refactor(stage2): single reach-safe static stance + real grasp verification
45d5ba3d fix(stage2): loosen navigate-to-stance tolerance for the new closer stance
bf90d7e6 fix(stage2): revert stance (real collision limit), reduce descent instead
75c4beb8 fix(stage2): raise PREGRASP_Z back to 0.90 (0.85 was too aggressive)
```

---

## 1. Context — what this session started from

A prior session (OpenCode) had written `docs/HANDOFF_2026-07-24_Stage2_grasp_v3.md`
claiming "7 GPU runs" diagnosed Stage 2's spoon-grasp problem and that a fix
(`approach_spoon` phase, commit `f6558f82`) was ready to test. **On
inspection, that run history had zero corroborating evidence anywhere in
the repo** (no `AGENT_STATE.md` entries, no `result.json` files, no output
directories) — it violated this project's own anti-hallucination rule
(added earlier the same day, commit `b15ea5cb`, for exactly this failure
mode). The lightning.ai VM was also not "fresh" as claimed — it had an
older commit checked out with uncommitted WIP. This session's first work
was correcting that record (commits `95c01faf`, `2062acb0`) and then doing
everything from here on with GPU-verified evidence pasted directly from
logs/result.json, not inferred or remembered.

---

## 2. Environment — exact current working setup

- **SSH:** `s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai` (this string
  changes across Lightning Studio restarts — verify live with `nvidia-smi`
  over SSH before trusting it, don't assume it's still valid in a future
  session).
- **Repo on VM:** `~/EBiM_Challenge` =
  `/teamspace/studios/this_studio/EBiM_Challenge`, branch
  `task3-current-clean`. **Ignore** `/home/zeus/ebim_hackthon` on the same
  VM — a different, older, unused checkout.
- **Container:** `isaac-lab-2-3-2-workshop`, image `isaac-lab-2.3.2:ebim2026`.
  Built once this session (image cache now exists at
  `docker/ebim-challenge/isaac-lab-2.3.2/cache`). Bring-up:
  `bash scripts/task3/lightning_workflow.sh bootstrap` (fast now, layer-
  cached). Stop: `bash scripts/task3/lightning_workflow.sh stop`, or
  `docker start isaac-lab-2-3-2-workshop` to resume an existing (not
  deleted) container.
- **GPU:** 1x NVIDIA L4, 23034 MiB. **Mandatory gate before trusting any
  run** (this project got burned by silent CPU fallback once already):
  `nvidia-smi` on host, `docker exec isaac-lab-2-3-2-workshop nvidia-smi`,
  grep the run log for `llvmpipe`/`No device could be created`/`software
  rasterizer` (any hit = discard the run), confirm `cuda:0` in the Isaac
  Lab boot log, confirm GPU utilization goes nonzero once physics starts.
- **Fast iteration:** `--skip-navigation` flag on both
  `run_stage2_feeding.py` and (implicitly, via direct stance placement)
  `probe_tray_slide.py` drives directly to the work stance instead of the
  full corridor/door route — validated this session to reproduce identical
  failure signatures in roughly half the wall-clock time. Use this for any
  grasp/descend iteration; only re-add full navigation once the grasp
  itself works.
- **VLM (Qwen2-VL-2B-Instruct):** installed in an isolated Python venv **on
  the VM host**, `~/vlm_venv` — deliberately NOT inside the Isaac Lab
  container (avoids clashing with Isaac Sim's pinned torch/CUDA build) and
  NOT on the local machine (per explicit instruction — model weights,
  cache, everything stays on the VM; only text output is ever pulled back).
  - Setup: `python3 -m venv ~/vlm_venv` (needed `sudo apt-get install -y
    python3.12-venv` first), then `pip install torch --index-url
    https://download.pytorch.org/whl/cu121`, then `pip install
    torchvision --index-url https://download.pytorch.org/whl/cu121`
    (needed separately — the first torch install alone left the
    processor's video-processing component broken), then `pip install
    transformers accelerate qwen-vl-utils pillow`.
  - Model weights: `Qwen/Qwen2-VL-2B-Instruct`, downloaded via
    `transformers.Qwen2VLForConditionalGeneration.from_pretrained`, cached
    in the default HF cache on the VM (`~/.cache/huggingface`).
  - Script: `~/vlm_narrate.py` on the VM. Usage:
    `python vlm_narrate.py <frames_dir> <frame1.png> <frame2.png> ...`
    Loads the model onto `cuda:0` (run this only after Isaac Sim has
    exited — sequential GPU use, not concurrent), asks a fixed VQA prompt
    per frame ("is the gripper closed around anything, where is the
    nearest small object relative to the fingers, does anything look
    fallen/out of place"), prints each answer, and writes
    `~/vlm_summaries/<run_name>_vlm_summary.json`.
  - **Validated once** this session against real frames from Stage 1's
    r14 arm-collapse run: correctly distinguished a normal frame ("not out
    of place") from the collapse-moment frame ("tray appears to be out of
    place"). Coarse but directionally useful.
  - **This was set up as a debugging/narration aid, not wired into any
    control loop or automated pass/fail decision.** Nothing currently
    calls it automatically after a run — it's a manual tool
    (`python vlm_narrate.py ...`) a future agent should run when frame-level
    diagnosis is needed and it can't view images directly itself.
  - Research grounding (found via web search this session): this pattern
    (a VLM as a failure-detection/narration layer, not a controller) matches
    published work — [AHA (NVIDIA/UW/MIT)](https://arxiv.org/abs/2410.00371),
    a VLM specifically built to detect and explain robotic manipulation
    failures. Confirms this is an established, sound pattern, not an ad hoc
    invention.

---

## 3. Parallel work discovered this session — `task3_pipeline/`

While working, an **untracked, uncommitted directory** `task3_pipeline/`
appeared in the local working tree (not on the VM, not pushed anywhere —
purely local to this machine). It contains a substantial, well-structured
module: `orchestrator.py`, `memory.py`, `policy.py`, `skills.py`,
`stages.py`, `world.py`, `world_isaac.py`, `config.py`, `outcomes.py`,
`run_task3.py`, plus CPU unit tests — an ambitious "self-correcting
autonomous pipeline" wrapper around the existing primitives, apparently
built by another agent (OpenCode) concurrently in this same repo.

**Its own README claims a CPU-only mock-world result of "median 93.8%,
100% of runs ≥ 70%," but explicitly states `world_isaac.py` (the real
Isaac Sim wiring) is still an unimplemented stub.** This has never been
GPU-tested. Treat that number as a mock-simulation result only — do not
cite it as real progress, and do not confuse it with the GPU-verified
numbers in this document. I have not touched, committed, or interfered
with this directory. Whether/how to reconcile this parallel effort with
the direct low-level script fixes documented here is an open decision for
the user, not something resolved in this session.

---

## 4. Stage 2 (Feeding) — full run-by-run history, this session

### 4.1 Runs 9-14 (approach_spoon era, code since reverted)

| Run | Config | Result | Real evidence |
|---|---|---|---|
| run9 | `f6558f82` baseline, `approach_spoon` phase (drive 8cm closer after pregrasp) | Failed at `approach_spoon` — base didn't move at all | `base_hold_anchor` (set at Phase 1 arrival) was still active during the new drive; `sim_tick()`'s hold-twist overwrote the drive command every tick (`apply_twist` is last-write-wins) — same bug class already fixed once for `navigate_dining` |
| — | Fix applied: `86590df6` — release anchor before drive, re-anchor after | | |
| run10 | Testing the anchor fix, `--skip-navigation` off | Still failed at `approach_spoon` — base moved ~14mm of the needed 110mm, yawed ~0.32 rad | Frames showed the spoon dragged out of view partway through — arm still at pregrasp height (19cm above island) directly over the spoon during the drive |
| — | Fix applied: `8aef9f66` — lift arm to `LIFT_Z` before driving, re-descend after | | |
| run11 | Testing the arm-lift fix | Still failed at `approach_spoon` — base moved ~13mm, yawed ~0.18 rad; spoon NOT knocked away this time (arm-lift helped that specific symptom) | Frames confirmed spoon stayed visible throughout, ruling out arm-dragging as the sole cause |
| run12 | `--skip-navigation`, same code | Reproduced the identical failure signature in ~half the wall-clock time — validated `--skip-navigation` as a fast-iteration tool | |
| run13 | `--skip-navigation --approach-offset-x -0.03` (diagnostic, smaller offset) | `approach_spoon` "passed" trivially (target within default tolerance of start), proceeded to `descend_spoon` — **failed there**, position_error 0.1159m; telemetry showed spoon fell to near-floor z=0.007 (from 0.761) | First real evidence the descend phase itself was broken, independent of approach |
| run14 | `--skip-navigation --approach-offset-x 0.0` (eliminate approach as a variable entirely) | `descend_spoon` failed again (~0.12m error), but this run continued past it into `close_spoon`→`spoon_grasped`→`lift_spoon`→navigation, all reporting `"ok": true`, while `gripper_position_rad: 1.0119` (MORE open than the 0.9 resting-open value) and the spoon's tracked z went into unbounded freefall: -160 → -330 → -608 → -1238 → -2139 across ticks | **This is the actual root discovery**: none of the phase checks from `close_spoon` onward verify an actual hold — the pipeline reports success while manipulating nothing. Process was killed manually once this was confirmed (further ticks provided no new information, spoon already irrecoverably falling) |

**Conclusion from runs 9-14:** the `approach_spoon` maneuver (added in
`f6558f82`) never worked cleanly in 3 separate fix attempts, and even when
bypassed entirely (run14, offset=0.0), the descend/grasp sequence still
failed with the same magnitude of position error — meaning the real
problem was never really about the approach drive at all.

### 4.2 Redesign — single static stance + grasp verification (`3cb9bf00`)

Removed the entire `approach_spoon` / `lift_before_approach` /
`repregrasp_after_approach` maneuver (all of `f6558f82`+`86590df6`+`8aef9f66`'s
Phase 2b code). Replaced `ISLAND_STANCE` with a single closer static value
(`-3.53, -1.62`, was `-3.47, -1.61`), navigated to directly with no
secondary drive. This number was **calibrated against the proven, GPU-
verified 10/10 cup-grasp distance** (0.8255m, computed from
`verify_grasp_lift.py`'s `STANCE=(-3.32,-1.72)` and
`CUP_GRASP_XY=(-4.145,-1.75)`) — the OLD `ISLAND_STANCE` put the spoon
pregrasp target at 0.8325m, only 6.9mm past that proven distance.

Also added a real grasp-verification check (task list item 6, still
"in_progress" as of this doc since further testing is pending) after
`close_spoon`: requires `gripper_position_rad < 0.75` (vs the ~0.9 resting-
open value) AND the spoon's tracked position to stay within 0.02m of the
end-effector over a 0.5s settle window, before any later phase is allowed
to treat the grasp as real. Fails immediately (`"failed_phase":
"grasp_verify"`) if not. This directly targets the run14 false-positive
pattern.

### 4.3 Run 15/16 — the closer stance doesn't work, real collision found

| Run | Config | Result |
|---|---|---|
| run15 | New code (`3cb9bf00`), `--skip-navigation`, `ISLAND_STANCE=(-3.53,-1.62)` | Failed at `navigate_stance_short` (basic navigation to the new stance, before even reaching pregrasp) — base stopped at **x=-3.466**, target was -3.53. Default tolerance (0.03m)/budget (20s). |
| — | Fix attempt: `45d5ba3d` — loosen tolerance to 0.05m, budget to 30s | |
| run16 | Same stance, loosened tolerance/budget | **Stopped at the exact same x=-3.466** — identical to 3 decimal places despite 50% more budget and looser tolerance. No `IK failed` or `PhysX error` log lines during this phase. |

**Root cause, confirmed by elimination, not guessed:** checked
`waypoints_y_then_x` (the route function used here, since start and target
are both south of the door — no door-crossing branch, no island-clear
insertion) — it computes a plain 2-leg path with no hidden waypoint near
-3.466, ruling out a stale-route bug. The repeatable, budget-independent
stop at **exactly the same x regardless of tolerance** means this is a
**real physical stop** (base hull vs. static geometry), not a slow
controller. -3.466 sits ~4mm from the *original* `ISLAND_STANCE` (-3.47),
strongly suggesting that original value was already tuned, likely by trial
and error in an earlier session, to sit right at this same boundary.
**Conclusion: there is no XY slack left to exploit in this direction.**
Moving the base closer to shrink reach is not a viable lever here.

Fix (`bf90d7e6`): reverted `ISLAND_STANCE` to the original `(-3.47, -1.61)`.

### 4.4 Shifting the lever to vertical descent — runs 17/18

Since XY can't move closer, and the earlier "arm cannot descend 18cm at
0.87m reach" language from the very first (otherwise unverified) handoff
turned out to be directionally correct, the remaining lever is the
**vertical descent distance**, which was only tall (19cm, `PREGRASP_Z=0.95`)
to protect the now-deleted base-approach maneuver — it doesn't need to be
that tall anymore.

| Run | Config | Result |
|---|---|---|
| run17 | `PREGRASP_Z` reduced 0.95→**0.85** (`bf90d7e6`) | **`descend_spoon` position_error = 0.0147m** — a huge improvement from the ~0.10-0.12m seen in every prior run. BUT: the spoon was already displaced (from `[-4.342,-1.678,0.761]` to `[-4.609,-1.619,0.817]`) by the time `pregrasp_spoon` itself logged, *before* any descend began — never happened in any prior run. Confirmed visually (frames `rgb_0036.png`-`rgb_0043.png`, pulled and viewed directly): by the descend frame, the spoon has fallen off the table, visible only as a small sliver below the table's front edge. `close_spoon` then failed cleanly (`"ok": false`, `gripper_position_rad: 0.0005` — fully closed, i.e. closed on nothing, spoon already gone). |
| — | Fix attempt: `75c4beb8` — raise `PREGRASP_Z` to **0.90** (compromise) | |
| run18 | `PREGRASP_Z=0.90` | **Position error regressed to 0.1206m** — back to the bad signature, worse than 0.85, not a smooth interpolation. |

**Current honest status (unresolved as of this doc):** 0.85 gives
excellent position convergence but the spoon gets knocked off before/during
descend (contact geometry problem — likely the open gripper's own size/
reach at that height already grazes the spoon or table). 0.90 avoids that
specific contact issue but position convergence regresses sharply and
nonlinearly (12cm error, not a smooth midpoint) — most likely because the
IK solver lands in a different, worse local joint-space solution starting
from a different pregrasp height, not because 0.90 is geometrically
harder to reach in principle. **This has not been resolved.** Three
tuning attempts on this specific pregrasp-height/descend-convergence
relationship without a stable answer is the threshold (per
`superpowers:systematic-debugging`) to stop guessing more values blindly
and either (a) map the relationship with a few more discrete test points
(e.g. 0.86, 0.87, 0.88) to find the actual transition point empirically,
or (b) reconsider the descent trajectory/gripper-timing approach itself
rather than just the height (e.g., keep fingers narrower/not-fully-open
until closer to the final target, or approach at a shallow angle instead
of straight down).

**Current code state (`75c4beb8`, HEAD):** `ISLAND_STANCE = (-3.47, -1.61)`
(reverted to original), `PREGRASP_Z = 0.90` (the worse of the two tested
values — **this is NOT the recommended value to leave as default**; 0.85
had far better position convergence, just a different problem. Whoever
picks this up next should treat `PREGRASP_Z` as still actively being
tuned, not settled).

---

## 5. Stage 1 (Table Setup / tray slide) — full history, this session

### 5.1 Fresh baseline, revealing a worse-than-historical result

Re-ran the historically-best config (`--object-name simple_tray
--descend-ee-z 0.815 --push-distance 0.26 --head-placement a`,
`scripts/task3/probe_tray_slide.py`, matching 2026-07-19's "Round 9") fresh
on the rebuilt environment: `outputs/task3_stage1_tray_slide_r14_claude/`.

**Result: worse than either historical run.** `stroke1_result` overhang
went **negative** (-0.160m, wrong direction) and `stroke2_realign` hit a
0.251m base drift before stroke 2 even started, ending the run. Log showed
repeated `Right arm IK failed: solver reported no solution` warnings
during `stroke1_drag`.

**Precisely recomputed** (angle-wrapped correctly, script-verified — an
earlier eyeballed estimate of ~172° rotation was wrong due to not handling
radian wraparound): base yaw jumped **exactly +78.59°** in one step,
between `stroke1_descend` (tick 15404) and `stroke1_drag` (tick 16404) —
the same 1000-tick window as the 3 logged IK failures — then **stayed
flat** (~-104° to -106°) through every phase afterward. A single abrupt
event, not a slow drift (rules out a Stage-2-style continuous heading-hold
failure).

**Mechanism, traced in source, not guessed:**
`scripts/common/dual_arm_lula.py:258-276` (`_solve_arm`) — when the Lula IK
solver fails (`compute_inverse_kinematics` returns `succeeded=False`), the
code catches it and **returns the previous joint targets unchanged**
(`return dict(previous), False`) — the arm silently freezes at its last
valid pose (base-relative, since joint angles are base-relative) instead
of erroring out or stopping the run. Meanwhile,
`probe_tray_slide.py:913-937` (`stroke1_drag`'s per-tick loop) keeps
advancing the base's own hold-anchor (`hold_anchor_box["value"]`)
independent of arm/IK state. With the gripper still pressed down in
**active surface contact** with the tray at that exact moment (mid-drag,
post-descend), a frozen arm + a still-advancing base is a lever-arm
situation: any base tracking disturbance amplifies into contact torque —
this fits a single sharp 78.6° spin far better than a gradual drift would.

**Why IK fails at all:** the module's own docstring states the tray
contact point sits "~0.86m dead ahead" — essentially the same ~0.85-0.87m
ceiling implicated in Stage 2's descend failures. Confirmed against
Franka's actual published spec (web search this session): **FR3 max reach
is 855mm**, measured from the arm's own shoulder joint. Both `TRAY_STANCE`
(~0.86m) and the original `ISLAND_STANCE` (~0.87m) sit essentially at this
theoretical geometric maximum, with zero margin for grasp offsets, contact
indentation, or orientation constraints.

### 5.2 Precise reach-margin measurement (no GPU needed, code-only)

Computed cleanly using actual code constants (not noisy telemetry):

```
Cup (PROVEN 10/10, verify_grasp_lift.py STANCE + CUP_GRASP_XY): 0.8255m
Spoon pregrasp target (Stage 2, ISLAND_STANCE + spoon_at_island + offsets): 0.8325m  (+6.9mm over proven)
Tray contact target (Stage 1, STANCE[0] + tray_y + CONTACT_X_OFFSET_M): 0.8593m  (+33.8mm over proven)
```

This calibration (against a demonstrably-working 10/10 distance, not an
abstract spec number) is why Stage 1's initial fix targeted "move ~5cm
closer," and Stage 2's initial fix targeted "move ~6-8cm closer" — both
of which turned out to be the *right idea in principle* for Stage 2
(later found to hit a hard collision wall for base-position changes
specifically, not for reducing reach via other means) and are **untested
on GPU yet for Stage 1** (see below).

### 5.3 Code changes made (commit `3cb9bf00`, bundled with Stage 2's stance fix)

1. **`TRAY_STANCE_X_OFFSET_M = -0.05`** — a new local constant in
   `probe_tray_slide.py`, applied as `tray_stance = (STANCE[0] +
   TRAY_STANCE_X_OFFSET_M, initial_tray_pose[1])`. **Deliberately does not
   modify the shared `STANCE` constant itself** (imported from
   `verify_grasp_lift.py`, used by the proven cup pipeline too — changing
   it would risk that already-working script). Lands at 0.8093m, ~1.6cm
   under the proven cup distance.
2. **`_run_push_stroke()` signature changed** — added a new `stance_x:
   float` parameter, used at the `realign_target` computation
   (previously hardcoded to the shared `STANCE[0]`, which would have
   silently pulled the base back to the *old*, farther stance between
   strokes, undoing the fix). Call site updated to pass
   `stance_x=tray_stance[0]`.
3. **Fail-fast at `edge_close`** when `pinch_plausible` is `False` instead
   of continuing through `edge_lift`/`carry` — r9's own (already-existing)
   `result.json` showed the run continuing for ~15000 more ticks with a
   known-implausible pinch, producing misleading `"ok": true` entries on
   every subsequent phase (including three `carry_waypoint` phases where
   the tray's tracked XY position barely moved a few mm despite the base
   traveling over a meter — almost certainly an unheld/slipped tray, not a
   real carry). Note: the final `passed` boolean in this script *did*
   already correctly account for `pinch_plausible` (unlike Stage 2, which
   had no equivalent check before this session) — the bug here was wasted
   compute and misleading intermediate telemetry, not a scoring
   false-positive.

**This is confirmed as a third instance of the same "reports/continues
past an implausible manipulation without stopping" pattern found in Stage
2 (and previously in Stage 4, per the `ebim-r-poc25-overclaim-2026-07-23`
memory) — a recurring architecture gap across at least three of this
project's scripts.**

### 5.4 GPU status: NOT YET RE-TESTED after these changes

**Important:** the Stage 1 code changes above (`3cb9bf00`) have been
pushed and synced to the VM but **have not been GPU-tested since being
made**. All Stage 1 GPU evidence in this document (r14's arm-collapse
finding) predates these fixes. Task list item #4 ("Stage 1: GPU-verify the
stance + verification fix, multi-trial") is still pending — this is
likely the highest-value next action for whoever picks this up, since it's
a clean, never-yet-tested fix on a well-understood root cause, unlike
Stage 2's current unresolved pregrasp-height oscillation.

Also still open: the *actual* trigger for the arm-collapse (why IK failed
during `stroke1_drag` specifically) is understood at the mechanism level
(frozen arm + advancing base + active contact) but the fix
(`TRAY_STANCE_X_OFFSET_M=-0.05`, closer contact point) has not been
verified to actually prevent the IK failures / collapse from recurring.
Test this specifically, not just the overhang number, when re-running.

---

## 6. Task list state (use `TaskList` tool to see live status)

1. **[completed]** Measure real arm-reach margin (FR3 855mm) vs commanded
   contact distances — see §5.2 above.
2. **[completed]** Stage 1: redesign TRAY_STANCE to a reach-safe distance
   — see §5.3 above. Code done, GPU untested (see §5.4).
3. **[completed]** Stage 1: add real grasp/hold-verification check — see
   §5.3 item 3 above (fail-fast at edge_close).
4. **[pending]** Stage 1: GPU-verify the stance + verification fix
   (multi-trial) — **highest-value next action, see §5.4**.
5. **[in_progress]** Stage 2: redesign ISLAND_STANCE to single static
   reach-safe stance — code done and reverted once already (§4.3); current
   stance is back to the original `(-3.47,-1.61)`; the remaining open lever
   is `PREGRASP_Z` (§4.4), not stance position.
6. **[in_progress]** Stage 2: add real grasp-verification check — code
   done (`3cb9bf00`, the `grasp_verify` phase), **not yet GPU-exercised**
   because no run has gotten past `descend_spoon`/`close_spoon` cleanly
   enough to reach it since it was added. Will only prove itself once the
   descend/pregrasp-height issue (§4.4) is resolved.
7. **[pending]** Stage 2: GPU-verify the stance + verification fix —
   blocked on resolving §4.4's open pregrasp-height question first.
8. **[pending]** Update docs/pipeline once Stage 1 and/or Stage 2 pass
   reliably — not yet reached for either stage.

**New task to add, not yet in the tracker:** resolve the `PREGRASP_Z`
nonlinearity (§4.4) — either by testing 2-3 more discrete values between
0.85 and 0.95 to map the actual transition point, or by changing the
descent *strategy* (timing of gripper opening, approach angle) instead of
just the height. This is the single most concrete unresolved item in the
whole session.

---

## 7. Stage 3 / Stage 4 — unchanged this session

No code or GPU work was done on Stage 3 (Bean Recovery / cup transport) or
Stage 4 (Cleanup) this session. Their status and sub-tasks are as
described in `docs/HANDOFF_2026-07-24_FULL_PLAN_Claude_to_OpenCode.md`
§3-5, which is still accurate for those two stages. In short: Stage 4's
root cause was diagnosed in a prior session with a corrective plan never
executed; Stage 3 has a prior "Full E2E Success" claim that was found to
be overclaimed on review and needs real re-verification, not a repeat.

---

## 8. Non-negotiable rules (repeated from the full-plan doc — still binding)

1. Every claim about a GPU run's outcome must be backed by a pasted
   `result.json` line, log excerpt, or a frame actually opened this
   session. Don't state a run's contents from memory.
2. One hypothesis, one code change, one GPU run. If 3 fixes fail on the
   same specific symptom without narrowing the problem, stop and raise an
   architecture question rather than trying a 4th blind fix — **this
   threshold was hit this session on Stage 2's `PREGRASP_Z` question
   (§4.4) and is being surfaced here rather than pushed through.**
3. GPU-verification gate before trusting any run (§2).
4. A phase reporting `"ok": true` is not proof an object was held — this
   gap is now confirmed in Stage 1, Stage 2, and (per prior-session
   memory) Stage 4. Check position/gripper-angle evidence, not just the
   flag.
5. Commit + push after every meaningful result, pass or fail. Check for
   another agent's concurrent uncommitted work (§3) before committing —
   this happened twice this session (once with `AGENT_STATE.md`/
   `PROJECT_JOURNAL.md` doc edits, reconciled; once with the much larger
   `task3_pipeline/` directory, left untouched).
6. Standard physics only — no kinematic attach, no scene/asset edits, no
   teleportation.
7. Stop the GPU/container at natural pause points. Currently: container
   was left **running** at the end of this session (mid-iteration on
   Stage 2); GPU was idle (0%, 0MiB) as of the last check. Stop it if
   pausing for any real length of time:
   `bash scripts/task3/lightning_workflow.sh stop` or
   `docker stop isaac-lab-2-3-2-workshop`.

---

## 9. Recommended next steps, in order

1. **Stage 1**: run the already-committed fix (`3cb9bf00`'s
   `TRAY_STANCE_X_OFFSET_M=-0.05` + fail-fast pinch check) fresh on GPU.
   Given known run-to-run variance in this script (r9/r13/r14 all differed
   with identical params), run at least 2-3 trials, not one, before
   concluding anything. This is clean, untested, well-understood work —
   do this first.
2. **Stage 2**: resolve the `PREGRASP_Z` question (§4.4) — either map 2-3
   more discrete height values, or reconsider the descent trajectory
   itself (e.g., delay full gripper-opening until closer to the final
   target, or approach at a shallow angle rather than straight down —
   note this was tried once very early in the project's history with
   `DESCEND_TILT_RAD` and reverted in favor of top-down; revisiting it
   with current understanding may be worthwhile, but treat it as a fresh
   hypothesis, not a re-run of the old approach).
3. Once either stage's grasp actually works end-to-end: let the new
   `grasp_verify` check (Stage 2) / fail-fast pinch check (Stage 1) prove
   itself for real, then continue to the remaining sub-phases (scoop/feed/
   hold for Stage 2; pinch/lift/carry for Stage 1) with the same
   GIF-first, one-variable-at-a-time discipline.
4. Decide what to do about `task3_pipeline/` (§3) — likely a conversation
   with the user, not something to resolve unilaterally.
