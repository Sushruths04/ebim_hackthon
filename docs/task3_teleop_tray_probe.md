# Task 3 tray teleoperation probe

This is a feasibility probe only. The final submission must use the autonomous
FSM; the teleop output is for measuring geometry and selecting scripted
waypoints.

## Launch

Run this on the Isaac Sim/Isaac Lab VM from the repository root:

```bash
python scripts/scenes/scene_robot_room_keyboard.py \
  --task task3 --head-placement A --keyboard-control \
  --record-teleop --episode-name tray_probe_01 \
  --record-dir outputs/task3_teleop --record-every-steps 10
```

For the validated remote WebRTC path, use public mode and enter exactly
`34.61.210.0` (no port, protocol, or spaces) in the Windows Isaac Sim WebRTC
client:

```bash
PUBLIC_IP=34.61.210.0 /workspace/isaaclab/isaaclab.sh -p \
  scripts/scenes/scene_robot_room_keyboard.py \
  --task task3 --head-placement A --keyboard-control --livestream \
  --record-teleop --episode-name tray_probe_01 \
  --record-dir outputs/task3_teleop --record-every-steps 10
```

Connect only while the process is running and the log says that the streaming
server has started. The keyboard listener is global, so the Isaac viewport
does not need focus; keep the WebRTC client visible for visual feedback.

The command refuses to overwrite an existing episode directory. Omit
`--episode-name` for an automatically timestamped directory. Add
`--max-seconds 1800` for a 30-minute bounded session.

The recorder writes `metadata.json`, `teleop.jsonl`, and `summary.json`. This
is an inspection/waypoint format, not a verified LeRobot training dataset.

## Keyboard map

The Isaac Sim window or the global keyboard listener must be active. Release a
key to stop its motion; use small taps rather than long holds near contact.

| Keys | Action |
|---|---|
| `W/S` | Left hand X + / - |
| `A/D` | Left hand Y + / - |
| `E/Q` | Left hand Z + / - |
| `Z/X` | Left wrist roll + / - |
| `T/G` | Left wrist pitch + / - |
| `C/V` | Left wrist yaw + / - |
| `F` | Toggle left gripper |
| `O/L` | Right hand X + / - |
| `K/;` | Right hand Y + / - |
| `P/I` | Right hand Z + / - |
| `N/M` | Right wrist roll + / - |
| `U/J` | Right wrist pitch + / - |
| `,/.` | Right wrist yaw + / - |
| `'` | Toggle right gripper |
| `R` | Reset both arm targets |
| `Shift+H/N` | Base forward / backward |
| `Shift+B/M` | Base left / right |
| `Shift+G/J` | Base rotate CCW / CW |
| `Esc` | Stop the listener and exit |
| `1`–`5` | Add a probe phase marker to the recording |

When `Shift` is held, overlapping arm keys are suppressed. Base movement is
therefore deliberate and cannot accidentally move an arm at the same time.

## Tray probe sequence

1. Start with both grippers open and tap `1`.
2. Use `Shift` plus the base keys to approach the counter. Keep the wrists
   above the tray and move slowly.
3. Use the appropriate arm translation keys to contact the tray's broad side.
   Tap `2` once the tray has a 6–8 cm overhang.
4. Move the hand just below and just above the overhanging 13 mm edge. Close
   the gripper with `F` or `'`, then tap `3`.
5. Raise the wrist in small `E`/`Q` or `P`/`I` taps, depending on the arm and
   its local Z direction. Tap `4` when the tray is visibly lifted. Hold for
   several seconds; a successful probe must keep the tray attached rather than
   merely create a transient upward motion.
6. Tap `5`, open the gripper, and exit with `Esc`.

If the tray cannot be pinched after the overhang is established, stop the
probe and use the per-object 4/5 fallback. Do not modify the scene or use a
kinematic attach for the submission without organizer approval.
