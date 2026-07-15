# Task 3 Start Guide For Lightning AI

This document is the practical starting point for building an EBiM Task 3
submission in a Lightning AI Studio.

## What Task 3 Requires

Task 3 is an assisted-living, kitchen-to-dining service cycle on the Mobile FR3
Duo. A full-autonomy solution must complete four stages:

1. Move the plate, cup, bowl-with-beans, and spoon from the kitchen to three
   assigned dining seats.
2. Scoop beans, present the spoon at the assigned head for at least three
   seconds, then return the beans to the bowl. One arm should steady the bowl.
3. Transfer beans to the recycling bin.
4. Return all four utensils to the marked sink region.

Official scoring assigns up to four points per stage (16 total). Ranking uses
highest stage completed, then total score, then completion time. Head/face
contact force and watchdog interventions are safety gates. See the official
competition rules before interpreting any local metric.

## Current Repository Reality

The repository is a developer preview, not a finished Task 3 benchmark. It
currently contains:

* `assets/robot_room.usd`: the kitchen and dining room asset.
* `scripts/scenes/scene_robot_room_keyboard.py`: Task 3 room composition,
  random head placement, 300 bean spawning, and an Isaac Lab keyboard/dual-arm
  IK control path.
* `scripts/config/task3_teleop/`: Lula kinematics configuration for the two
  arms.
* `scripts/common/`: mobile-base, teleoperation, and target-control helpers.

It does **not** currently provide an official Task 3 evaluator, an autonomous
baseline, a released demonstration dataset, or a complete MuJoCo Task 3
environment. The `STATUS.md` matrix also still classifies Task 3 as under active
development. Treat local runs as integration and policy-development tests;
confirm all evaluation assumptions with organizer releases.

## Recommended Lightning Studio Configuration

Create a dedicated Linux GPU Studio for this project. Use the Studio's default
single Conda environment; Lightning persists packages and files in the Studio,
so creating a separate virtual environment is unnecessary. Do initial cloning
and dependency checks on a CPU instance if desired, then switch to an NVIDIA
GPU before invoking Isaac Sim.

The EBiM runtime requires Docker Compose, an NVIDIA GPU runtime visible to
Docker, Git LFS, NVIDIA NGC credentials for the Isaac images, and enough
persistent storage for Isaac shader/cache data. The upstream compose stack was
written for Linux + X11. In a browser-based Studio, begin with headless smoke
runs. Do not assume desktop GUI or keyboard capture will work remotely; add
WebRTC streaming or a video/frame recorder only after the headless simulation
is stable.

From the repository root in the Studio:

```bash
chmod +x scripts/task3/prepare_lightning_studio.sh
./scripts/task3/prepare_lightning_studio.sh --cpu-setup
```

This CPU command syncs Git LFS and submodules without starting any Isaac work.
After switching the same Studio to an NVIDIA GPU, run the script again without
arguments. That command checks the GPU/container runtime, creates the EBiM
cache layout, and prints the exact NGC authentication, build, and Task 3
smoke-run commands. It intentionally does not build images or start paid GPU
work on its own.

## Verified T4 Static Asset View

The Tesla T4 Studio used for this project has 15 GB VRAM and about 16 GB host
RAM. That is below NVIDIA's 32 GB host-memory minimum for a supported full
Isaac Sim workflow, so do not use it for the full dynamic Task 3 integration
run, teleoperation, or training. It is sufficient to load the static room and
save an off-screen image for asset inspection.

After the Isaac Sim 5.1 compose container is running, use this command from
the Studio's repository directory:

```bash
docker exec isaac-sim-5-1-0-workshop bash -lc \
  'cd /workspace/EBiM_Challenge && python -B scripts/task3/capture_static_view.py'
```

The image is written to `outputs/task3_static_view/rgb_0000.png` in the
repository. The capture builds the benchmark's Task 3 Stage 4 room, removes
the dynamic coffee beans, and uses an off-screen RGB camera. It performs no
robot control, simulation episode, or training.

At the time of verification, the room also reported two missing optional
payload files: `assets/ikea_knock_box.glb` and `assets/ikea_scale.glb`. The
static room and the Task 3 objects still loaded, but those two props will not
be visible until their asset files are supplied.

## Development Order

1. **Freeze the environment contract.** Record the benchmark commit, Isaac
   image digest, GPU/driver, seed, head placement, and room/robot USD hashes for
   every run.
2. **Make a deterministic scene harness.** Launch the scene headlessly with a
   selected `--head-placement` value and fixed random seed. Add an episode reset
   that records object poses, bean count, and target seats.
3. **Build observations.** Start with privileged USD/physics poses for a
   planning baseline. Define a narrow perception interface that can later be
   backed by RGB-D/segmentation without changing task logic.
4. **Build a safety-first state machine.** Model the four official stages and
   use explicit preconditions, postconditions, timeouts, retry budgets, and an
   emergency stop. Do not train an end-to-end policy before the scene reset,
   grasp, and safety checks are repeatable.
5. **Add skills in order of risk.** Base navigation and plate transport;
   bimanual bowl stabilization plus spoon trajectory; bean recovery; cleanup.
   Each skill needs a standalone reset-and-verify test.
6. **Add visual evidence.** Produce a camera recording or a fixed-rate frame
   sequence per episode with overlays for current stage, object targets, and
   safety events. A remote GUI is useful for debugging, but recordings are more
   reproducible for iteration and review.
7. **Implement a shadow evaluator.** Keep it separate from the controller and
   only encode criteria that are published. Version every assumption so it can
   be replaced when the official Task 3 scorer is released.
8. **Package the submission early.** The competition requires a public
   repository with a Dockerfile and a README explaining execution. Keep weights
   and datasets external only when the README includes an exact integration path.

## First Engineering Milestone

The first useful milestone is not a full meal-service run. It is a headless,
seeded episode that loads the official room, controls the FR3 Duo without
falling, records a camera stream, and completes a collision-safe table-setup
transport. That validates the asset, actuator loop, navigation, grasping, and
observability layers required by every later stage.

## Sources

* EBiM Task 3 rules: <https://ebim-benchmark.github.io/competition.html#tasks>
* Repository status matrix: <https://github.com/EBiM-Benchmark/benchmark/blob/main/STATUS.md>
* Upstream runtime guide: <https://github.com/EBiM-Benchmark/benchmark/blob/main/docs/developer_setup.md>
* Lightning Studio environment guidance: <https://lightning.ai/docs/platform/build/ai-studio/modify-environment>
