# Handoff — Stage 2 navigate_dining base-stall FIXED, 2026-07-24

Read this before touching Stage 2. It supersedes the blocker section of
`docs/HANDOFF_2026-07-23_Stage2_v2.md` (that doc's environment/SSH info is
still valid — only the `navigate_dining` blocker section is stale now).

## STEP 0 — GPU gate (MANDATORY, do this before any other action)

A prior session's runs may have executed **without a real GPU attached** —
this was discovered after the fact and is suspected to have produced
misleading physics/timing results. Isaac Sim silently falling back to a
software (CPU) Vulkan renderer is a known failure mode in this exact repo
(see `docs/AGENT_STATE.md` / memory `ebim-task3-strategy`: Modal's GPU
containers exposed CUDA but not Vulkan, and Kit fell back to `llvmpipe`
software rendering with degraded/wrong behavior instead of erroring out
loudly). **Do not trust any run's result.json/timing/physics behavior
unless you have confirmed a real GPU was engaged for that specific run.**

Before launching ANY Isaac Sim process, run and paste the raw output of all
three checks:

```bash
# 1. Host sees the GPU at all
nvidia-smi

# 2. The container was actually started with GPU access
docker exec isaac-lab-2-3-2-workshop nvidia-smi

# 3. While a sim run is active, confirm GPU utilization is actually nonzero
#    (run this in a second terminal a few seconds after launching a script)
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv -l 2
```

If any of these fail, or `nvidia-smi` inside the container errors, or GPU
utilization stays at 0% during a run: **STOP. Do not proceed to a physics
run.** Fix the GPU wiring first (`docker/docker-compose.yaml` has the GPU
reservation block; `scripts/task3/bootstrap_new_studio.sh` already checks
`nvidia-smi` before it will bootstrap at all — if you bypassed that script
and ran raw `docker` commands instead, that's the likely cause). Also grep
the Isaac Sim boot log for the software-fallback signature before trusting
any run:

```bash
grep -i "llvmpipe\|No device could be created\|software rasterizer" /tmp/stage2_run.log
```

Any hit there means the run was not physically real — discard its results
entirely, do not reason about them, do not report them to the user.

## Anti-hallucination rules for this session (non-negotiable)

1. **Never report a PASS/FAIL, a number, or a phase result from memory or
   inference.** Every claim about what happened in a run must be backed by
   a pasted excerpt of `result.json`, the run log, or a specific frame
   file you actually opened. If you didn't read the file this turn, you
   don't get to state its contents.
2. **One hypothesis, one code change, one run.** Do not stack multiple
   fixes into a single trial — if it fails you won't know which change
   mattered (this is exactly how the previous 5 failed attempts on this
   same bug wasted a full session — see "Process note" below).
3. **GIF/frame evidence before tuning.** Per `docs/HANDOFF_2026-07-23_Stage2_v2.md`
   and this repo's established practice: read `outputs/.../stage2.gif` or
   sampled frames around the relevant phase transition before deciding
   what's actually wrong. Do not guess from the phase name alone.
4. **If you're not >80% sure a code change is safe or correct, say so and
   stop rather than applying it speculatively.** Do not paper over an
   unexplained result with a plausible-sounding narrative.
5. **Standard physics only** — no kinematic attach, no scene/asset edits,
   no teleportation, no shortcuts to make a gate pass. This is a hard
   competition-legality rule the whole project has followed throughout.
6. Update `docs/AGENT_STATE.md` and commit after every meaningful result
   (pass or fail) — git is the shared memory across agents on this repo;
   an unpushed result does not exist for the next session.

## Root cause (found by CPU code-reading, not by GPU trial-and-error)

`scripts/task3/run_stage2_feeding.py` has a local `base_hold_anchor` used to
keep the base stationary while the arm manipulates (set at line ~562, right
after arriving at `ISLAND_STANCE`). `sim_tick()` (line ~386-403) checks this
anchor on **every** tick and, if it's not `None`, calls
`adapter.apply_twist(hold_vx, hold_vy, hold_heading=True)` to pull the base
back toward it.

`drive_to()` (line ~432) computes a navigation twist and calls
`adapter.apply_twist(vx, vy)`, then immediately calls `sim_tick()`.
`apply_twist` (`task3_autonomy/skills.py:264`) is **last-write-wins** — it
directly computes wheel targets from whatever `vx, vy, wz` it was just
called with. So the sequence every tick during `navigate_dining` was:

1. `drive_to` sets wheels toward the dining waypoint.
2. `sim_tick()` immediately overwrites those wheel targets with a PD
   controller (`position_kp=4.0`) pulling the base back to the **island**
   position, because `base_hold_anchor` was never cleared.

Net effect: the base was fighting a phantom "return to island" controller
every single tick, regardless of what the nav skill commanded. This fully
explains the symptom log ("0.000 rpm wheels despite motor current" — the
wheels *were* being driven, just toward the wrong target) and why all 5
prior fixes failed identically in every direction (arm tuck, gap alignment,
drive-north, drive-south, arm-release) — **none of them touched
`base_hold_anchor`**, so the invisible anchor pull was still active under
every one of those trials.

This is a regression of the exact bug class already root-caused once before
in this repo, in a sibling script: see `docs/AGENT_STATE.md`, "Day 3 Step 1
Round 2" fix3 — "`hold_anchor` was never cleared after manipulation, so
`sim_tick()`'s anchor-hold twist silently overrode every `NavigateTo`
command." `probe_tray_slide.py` was fixed for this; `run_stage2_feeding.py`
apparently never got the equivalent fix when the anchor pattern was copied
into it.

## The fix (applied, CPU-verified, NOT YET GPU-verified)

One line, at the top of Phase 5 in `run_stage2_feeding.py`, immediately
before the `route_via_door(...)` call and the `navigate_dining` `drive_to`
loop:

```python
base_hold_anchor = None
```

This releases the island anchor before free navigation starts. The anchor
is correctly re-established afterward (line ~788, unchanged:
`base_hold_anchor = (adapter.pose().x, adapter.pose().y)`, right after the
dining-route loop completes) so the base still holds position during the
subsequent feed phases — that part of the pattern was already correct, only
the *release* before navigation was missing.

**CPU verification done this session:**
- `python -m py_compile scripts/task3/run_stage2_feeding.py` — clean.
- `ruff check scripts/task3/run_stage2_feeding.py` — clean.
- `pytest scripts/tests -q` — 220 passed, 3 failed. The 3 failures are in
  `test_scene_robot_room_rmpflow.py` (`franka_urdf_path` attribute error),
  **unrelated to this change and pre-existing on clean HEAD** — do not
  re-diagnose them as caused by this fix.

**No GPU run has been done yet.** This fix has not been physically verified
in Isaac Sim. Do not report Stage 2 as passing `navigate_dining` until a GPU
run confirms it.

## Next steps, in order

### 1. GPU-verify the fix (first priority)

Compute venue is **Lightning AI only** — GCP is hard-banned (no budget
left; see `docs/AGENT_STATE.md` gpu-cost-discipline notes). Use the
Lightning Studio setup documented in `docs/HANDOFF_2026-07-23_Stage2_v2.md`
("Current environment" section) for SSH/container/run commands — that part
is still accurate. Run with `--skip-navigation` first for a fast iteration
cycle (~12-15 min), matching this repo's established practice, then a full
run once `navigate_dining` is confirmed passing.

Expect one of two outcomes:
- **`navigate_dining` now passes** (base actually reaches the doorway
  waypoint and `DINING_TARGET`). Good — proceed to step 2.
- **It still fails, but differently.** If the base now visibly moves (frame
  diffs during `navigate_dining` should jump from ~7.6 back toward the
  ~28 seen during real navigation, per the original diagnosis in the
  problem report) but stops short or hits the wall, that is a *different*,
  new bug (e.g. genuine geometry/gap-alignment issue) — the previously
  attempted gap-alignment fix (`TASK3_GAP_EAST_EDGE` westward waypoint,
  currently uncommitted in `task3_autonomy/navigation.py`, see `git diff`)
  may become relevant again now that it can actually be tested without the
  anchor fighting it. Diagnose GIF-first before changing anything further
  — this repo's established practice (one hypothesis per run, no stacked
  changes).

### 2. Once navigate_dining passes: feed/hold phases are untested territory

Nobody has gotten this far yet. Expect new issues in `head_found`,
`insertion`/feed positioning, and the hold gate — treat each as its own
GIF-first diagnosis, not a guess-and-bundle. (Carried over from the v2
handoff, still accurate.)

### 3. Separately: the scoop (0 beans every run) still needs its own fix

Lower priority than navigate_dining since the script doesn't hard-fail on
it, but it must pass eventually for a real Stage 2 pass. `--scoop-pitch-deg`
(default 30.0) is the first lever to sweep. Do not conflate this with the
grasp-firmness caveat from the v2 handoff (gripper reads 0.887-1.0 rad on
`close_spoon` instead of 0.0 closed) — they may or may not share a root
cause.

## Process note for whoever picks this up next

Five fix attempts were made before this one, all targeting the arm/geometry
(tuck, gap alignment, drive N, drive S, arm-release) and all failed
identically in every direction — that pattern (uniform failure regardless
of the variable changed) was itself the clue that the bug was NOT where
those fixes were looking. Per this repo's own systematic-debugging
practice: after 2-3 fixes fail without narrowing the problem, stop
varying parameters and re-read the actual control-flow code path instead of
trying another parameter. That's what found this one — a `git grep
base_hold_anchor` plus reading `drive_to`/`sim_tick`/`apply_twist` in
sequence, no GPU run required.

See also `docs/HANDOFF_2026-07-23_Stage2_v2.md` for environment/SSH setup
(still valid) and `docs/AGENT_STATE.md` for the full project history.
