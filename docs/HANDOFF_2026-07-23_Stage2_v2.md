# Handoff — Stage 2 continuation, 2026-07-23 late session

Read this before touching Stage 2. It supersedes `HANDOFF_2026-07-23_Stage2.md`
(that one's SSH/studio info is dead — the studio it names was decommissioned).

## What changed since the old handoff

Three real bugs were found and fixed, and are already pushed to
`task3-current-clean`:

1. **`a9d5da58`** — removed a broken `.codex-publish` gitlink that made
   `git submodule update --init --recursive` fail on every fresh clone.
2. **`b16760ed`** — added `scripts/task3/bootstrap_new_studio.sh`, a one-shot
   script that takes a brand-new Lightning Studio to a running, correctly
   provisioned container. Use this, not a raw `docker build`, if you ever
   need a new studio.
3. **`b01ed8bb`** — `run_stage2_feeding.py`'s `navigate_dining` phase was
   driving a straight line from the island stance to `DINING_TARGET`. The
   kitchen/dining partition only has a doorway gap at x in (-4.74, -3.54)
   (`task3_autonomy/navigation.py`); neither the skip-navigation shortcut nor
   `CORRIDOR_STOP=(-3.18, -1.6)` passes through it, so the base drove into
   the wall and timed out on every single run, including all of last
   session's. Fixed by wiring in `route_via_door()` — the same proven helper
   `verify_grasp_lift.py` and `probe_tray_slide.py` already use for this
   exact crossing.

**Do not re-diagnose the SimulationApp `OSError: [Errno 22]` crash from last
session.** It was not an environment bug. It was caused by
`sys.stdout = os.fdopen(sys.stdout.fileno(), "w", 1)` in that session's own
`test_minimal.py`/`test_minimal2.py` diagnostic scripts, which broke Kit's
internal stdout writer. Those scripts have been deleted (they were untracked
scratch files). A container built via `bootstrap_new_studio.sh` boots
`SimulationApp()` cleanly in ~26s — verified.

## Current environment (live, verified working)

- Lightning Studio SSH: `ssh s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai`
  (if `Permission denied (publickey)`, the SSH key needs regenerating — see
  "SSH key" below)
- Repo on studio: `/teamspace/studios/this_studio/EBiM_Challenge`
  (bind-mounted live into the container — edits and `git pull` on the host
  are visible inside the container immediately, no rebuild needed for code
  changes)
- Container: `isaac-lab-2-3-2-workshop`, built via
  `docker compose --profile isaac-lab-2.3.2` (see `docker/docker-compose.yaml`)
- GPU: NVIDIA L4, 23 GB, verified free
- `docker login nvcr.io` already done on this account
- `python` inside the container resolves correctly to
  `/workspace/isaaclab/_isaac_sim/python.sh` (Python 3.11.13) — no need for
  `python3` workarounds

### SSH key (only if the connection is refused)

Lightning generates a fresh keypair per "Add new machine" flow, tied to a
session token — it is NOT the same key across studios by default. If SSH
fails:
1. On the Lightning dashboard, open this studio's SSH setup page and copy
   its `iwr ... | iex` (Windows) or `curl ... | bash` (Linux/Mac) one-liner.
2. Either run it directly, or (safer, and how this session did it) fetch the
   script first and inspect it before running — it only downloads a keypair
   from `lightning.ai/setup/ssh-gen`/`ssh-public` into `~/.ssh/lightning_rsa*`
   and appends a `Host ssh.lightning.ai` block to `~/.ssh/config`.
3. Verify both `lightning_rsa` and `lightning_rsa.pub` are non-empty before
   trusting it — last session's first attempt silently produced an empty
   `.pub` file and wasted time on a misdiagnosed "environment" problem.

## What's proven this session (`outputs/task3_stage2_feeding/`, `--skip-navigation`)

Two full runs, both with `--record-video`. GIF from the second run and full
phase timeline: https://claude.ai/code/artifact/da2116e9-efd3-42e3-9116-79c71904a787

| phase | status | note |
|---|---|---|
| descend_spoon | **PASS** | 6.9 cm error (was 8–12 cm before the 46° tilt fix) |
| close_spoon / spoon_grasped | soft-pass | pipeline's own gate passes, but gripper reads 0.887–1.0 rad vs 0.9 open / 0.0 closed — **not a firm grasp, unverified** |
| scoop_enter / scoop_result | **FAIL** | `ok: false`, 0 beans on spoon both runs — script continues anyway (non-terminal) |
| lift_spoon | PASS | |
| navigate_dining (fixed routing) | **FAIL — current terminal blocker** | `route_via_door()` now correctly computes the doorway waypoint `(-3.454, -0.37)`, but the base never reaches it within the 45 s budget |

## Next steps, in order

### 1. Diagnose the navigate_dining stall before changing anything (don't guess)

Do not jump straight to a fix. First confirm what kind of failure this is by
reading `outputs/task3_stage2_feeding/frames/` or `stage2.gif` from a fresh
run around the `lift_spoon` → `navigate_dining_waypoint` transition:

- If the base position is essentially frozen the whole 45 s (a real
  contact-stall): the leading hypothesis is that the right arm is still
  extended out holding the spoon (post-grasp/scoop pose) when it enters the
  narrow lane between the island (north face y=-1.22) and partition (south
  face y=0.10) — the same class of bug already root-caused for Stage 4
  transport in `docs/AGENT_STATE.md` ("ROOT CAUSE of the transport nav stall
  + fix", 2026-07-19). Candidate fix: retract/tuck the right arm toward
  something like the existing `TRANSIT_ARM_POSE` (already imported in
  `run_stage2_feeding.py` from `task3_autonomy.skills`) before the
  `navigate_dining` phase, keeping the spoon held but compact.
- If the base is moving but slowly (not stalled, just short of the
  waypoint): the fix is smaller — raise `budget_s` on that `drive_to` call
  (currently 45.0) or `max_speed` (currently 0.35), not a tuck.

Confirm which one it is from evidence before writing a fix. This matches
this repo's established practice — GIF-first diagnosis, one hypothesis per
run, do not stack multiple changes into one trial.

### 2. Once navigate_dining passes, the feed/hold phases are untested territory

Nobody has gotten this far yet. Expect new issues in `head_found`,
`insertion`/feed positioning, and the hold gate — treat each as its own
GIF-first diagnosis, not a guess-and-bundle.

### 3. Separately: the scoop (0 beans every run) needs its own fix

Lower priority than navigate_dining since the script doesn't hard-fail on
it, but it must pass eventually for a real Stage 2 pass. `--scoop-pitch-deg`
(default 30.0) is already an exposed CLI param — that's the first lever to
sweep once transit is fixed. Do not conflate this with the grasp-firmness
caveat above; they may or may not share a root cause.

## How to run and monitor (proven this session)

```bash
ssh s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai
cd /teamspace/studios/this_studio/EBiM_Challenge
git pull origin task3-current-clean

# launch (survives SSH disconnect)
screen -dmS stage2 bash -c "docker exec isaac-lab-2-3-2-workshop bash -lc \
  \"cd /workspace/EBiM_Challenge && rm -rf outputs/task3_stage2_feeding && \
  python -u -B scripts/task3/run_stage2_feeding.py --record-video --fast-exit --skip-navigation\" \
  > /tmp/stage2_run.log 2>&1"

# monitor
grep -a STAGE2 /tmp/stage2_run.log | tail -20
screen -list   # confirm still running

# pull results once done
docker cp isaac-lab-2-3-2-workshop:/workspace/EBiM_Challenge/outputs/task3_stage2_feeding/result.json /tmp/
docker cp isaac-lab-2-3-2-workshop:/workspace/EBiM_Challenge/outputs/task3_stage2_feeding/stage2.gif /tmp/
```

`--skip-navigation` runs take ~12–15 wall-minutes and fail fast if something
regresses — use it for iteration. Only drop it for a final validation pass.

## Cost discipline

Lightning bills the studio while it's running, independent of what the
container is doing. One `--skip-navigation` trial is ~12–15 min. Don't leave
the studio running idle between trials if you're stepping away for a while.
Always `--record-video`; always read `result.json` + the GIF before deciding
the next change; one hypothesis per run.
