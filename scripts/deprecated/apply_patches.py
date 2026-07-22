# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Apply patches to a copy of verify_grasp_lift.py for spine-first lift + friction."""

path = "/workspace/EBiM_Challenge/_worktrees/task3-tray-fix/scripts/task3/fixed_grasp_lift.py"

with open(path) as f:
    content = f.read()

# 1) Change default args in parse_args()
content = content.replace(
    'default=None, help="Optional fraction',
    'default=1.0, help="Optional fraction',
)
content = content.replace(
    'default=1.5, help="Total close-and-force-settle',
    'default=4.0, help="Total close-and-force-settle',
)
content = content.replace(
    'default=1.0, help="Duration of the linear',
    'default=2.0, help="Duration of the linear',
)
content = content.replace(
    'default=0.0, help=("Vertical offset for the live cup-rim target',
    'default=-0.03, help=("Vertical offset for the live cup-rim target',
)

# 2) Add friction patch right after sim = SimulationContext(...)
old_sim = "    sim = SimulationContext("
for i in range(10):
    old_sim_line = None
    lines = content.split("\n")
    for j, line in enumerate(lines):
        if old_sim in line:
            old_sim_line = j + 1  # include next lines for the constructor args
            break
    if old_sim_line:
        break

friction_code = """
    # --- HIGH-FRICTION SURFACE PATCH ---
    from pxr import Usd, UsdPhysics, UsdShade
    try:
        _mat = UsdShade.Material.Define(sim.stage, "/World/HighFrictionSurface")
        _pm = UsdPhysics.MaterialAPI.Apply(_mat.GetPrim())
        _pm.CreateStaticFrictionAttr().Set(2.0)
        _pm.CreateDynamicFrictionAttr().Set(1.6)
        _pm.CreateRestitutionAttr().Set(0.0)
        _cnt = 0
        for _prim in Usd.PrimRange(sim.stage.GetPrimAtPath("/World")):
            if _prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdShade.MaterialBindingAPI.Apply(_prim).Bind(_mat)
                _cnt += 1
        print(f"FRICTION_PATCH: applied friction 2.0 to {_cnt} prims", flush=True)
    except Exception as _e:
        print(f"FRICTION_PATCH failed: {_e}", flush=True)

"""

# Find where the 3-line constructor ends and insert the friction patch
lines = content.split("\n")
insert_idx = None
for i, line in enumerate(lines):
    if old_sim in line:
        # Find the line with ) that closes the constructor call
        paren_count = 0
        for j, c in enumerate(line):
            if c == "(":
                paren_count += 1
            elif c == ")":
                paren_count -= 1
        if paren_count > 0:
            for k in range(i + 1, min(i + 30, len(lines))):
                for c in lines[k]:
                    if c == "(":
                        paren_count += 1
                    elif c == ")":
                        paren_count -= 1
                if paren_count <= 0:
                    insert_idx = k + 1
                    break
        else:
            insert_idx = i + 1
        break

if insert_idx is not None:
    lines.insert(insert_idx, friction_code)
    content = "\n".join(lines)
    print(f"FRICTION_PATCH: inserted at line {insert_idx}", flush=True)
else:
    print("FRICTION_PATCH: could not find insert point", flush=True)

# 3) Replace the lift section
old_lift_start = "    right_pose = arms.ee_world_poses()[1]"
old_lift_end = '    log_phase("lift", lift_ok)'

new_lift = """    right_pose = arms.ee_world_poses()[1]
    # SPINE-FIRST LIFT: keep arm joints fixed relative to base, raise spine to lift
    start_spine = arms.measured_spine_position()
    spine_rise = 0.12
    target_spine = min(0.57, start_spine + spine_rise)
    rel_pose = arms.arm_pose_relative("right")
    spine_ramp_ticks = max(1, int(4.0 / sim.cfg.dt))
    spine_timeout_ticks = int(8.0 / sim.cfg.dt)
    lift_ok = False
    cup_rise = 0.0
    for _tick in range(spine_timeout_ticks):
        _alpha = min(1.0, (_tick + 1) / spine_ramp_ticks)
        arms.spine = start_spine + (target_spine - start_spine) * _alpha
        try:
            arms.set_arm_target_relative("right", rel_pose.position, rel_pose.orientation_wxyz)
        except ValueError:
            pass
        arms.command()
        sim_tick()
        if _tick + 1 >= spine_ramp_ticks:
            _cur = cup_position()
            cup_rise = _cur[2] - cup_start[2]
            if cup_rise >= args.min_lift_m:
                lift_ok = True
                break
    if not lift_ok:
        _cur = cup_position()
        cup_rise = _cur[2] - cup_start[2]
        print(f"SPINE_LIFT: cup rose only {cup_rise:.3f}m, arm extended lift", flush=True)
        _remaining = max(0.0, 0.08 - cup_rise)
        if _remaining > 0.01:
            _pp = arms.ee_world_poses()[1]
            for _t in range(int(3.0 / sim.cfg.dt)):
                _a = min(1.0, (_t + 1) / max(1, int(2.0 / sim.cfg.dt)))
                _tz = _pp[0][2] + _remaining * _a
                arms.set_arm_target("right", (_pp[0][0], _pp[0][1], _tz), _pp[1])
                arms.command()
                sim_tick()
            _cur = cup_position()
            cup_rise = _cur[2] - cup_start[2]
            lift_ok = cup_rise >= args.min_lift_m
    log_phase("lift", lift_ok, spine_rise=round(spine_rise, 3), cup_rise=round(cup_rise, 3))"""

# Find the lift section boundaries
lift_start_idx = None
lift_end_idx = None

lines = content.split("\n")
for i, line in enumerate(lines):
    if old_lift_start in line:
        lift_start_idx = i
    if lift_start_idx is not None and 'log_phase("lift"' in line:
        lift_end_idx = i
        break

if lift_start_idx is not None and lift_end_idx is not None:
    old_lift_section = "\n".join(lines[lift_start_idx : lift_end_idx + 1])
    content = content.replace(old_lift_section, new_lift)
    print(f"LIFT_REPLACED: lines {lift_start_idx}-{lift_end_idx}", flush=True)
else:
    print(
        f"LIFT_NOT_FOUND: start={lift_start_idx}, end={lift_end_idx}",
        flush=True,
    )

with open(path, "w") as f:
    f.write(content)

print("PATCHES_APPLIED: fixed_grasp_lift.py ready", flush=True)
