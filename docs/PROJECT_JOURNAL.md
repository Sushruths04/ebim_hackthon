# Project Journal

## 2026-07-17 — Phase 1 harness diagnosis

Goal: make the first recorded idle Task 3 episode complete on the verified
RTX PRO 6000 VM.

Work completed: reproduced the episode runner on real GPU hardware; corrected
the mobile FR3 gripper actuator patterns; added a regression assertion; and
diagnosed the `RigidPrim` CUDA crash as malformed nested rigid-body hierarchies
in imported room props. The nested-body normalization removes that CUDA/PhysX
failure. Focused CPU tests passed 106/106.

Current evidence: the remaining block is the robot USD's legacy steering
OmniGraph (`Steer_joint_Controller`), which reads an invalid
`Desired_Linear_Velocity_X` input during reset and leaves the Kit process
stalled. The next session should repair or disable that unused keyboard graph,
then rerun the recorded idle episode.
