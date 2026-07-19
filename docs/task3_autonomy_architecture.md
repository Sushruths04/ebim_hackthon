# Task 3 autonomy architecture

## Decision

We do not need to train a reinforcement-learning algorithm to submit Task 3.
The competition requirement is full autonomy, not a learned policy. A bounded
scripted controller is the fastest and most inspectable point-scoring model for
this scene.

## Runtime controller

```text
episode runner (seed, placement, logging, video)
        ↓
stage-chain FSM (1 → 2 → 3 → 4, safety aborts)
        ↓
stage FSM (timeouts, retries, postconditions)
        ↓
skills (navigate, reach/IK, grasp, lift, place, release, scoop, pour)
        ↓
Isaac adapter (PhysX/Fabric reads + joint/base targets)
        ↓
grader + proof exporter
```

The controller is closed-loop: it re-reads live PhysX/Fabric state rather than
assuming that a command succeeded. Each skill has a timeout, retry budget,
collision/watchdog abort, and a measured completion predicate. The tray carry
path must therefore be proved with physical contact and lift evidence; the
kinematic adapter is useful for grading/FSM regression but is not the physical
submission proof.

## Where agents and MCP fit

Agents or MCP tools are useful outside the real-time control loop for launching
an episode, selecting a seed matrix, collecting result files, and producing a
human-review report. LangChain is optional for the same orchestration layer.
They should not be allowed to invent Cartesian targets or directly replace the
safety-bounded skill controller during scoring. This keeps latency,
reproducibility, and safety behavior deterministic.

## Where RL fits

RL is a stretch track after a scripted baseline passes. The FSM can generate
demonstrations for behavior cloning or provide a curriculum/reward baseline,
but training is not required for the final model. If a learned policy is later
added, it should propose bounded skill parameters while the FSM, workspace
limits, watchdog, and postcondition checks remain the authority.
