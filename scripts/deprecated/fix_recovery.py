# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Fix: make rotate_spot recovery unconditional (not gated on transport_to_dining)."""

path = "/workspace/EBiM_Challenge/_worktrees/task3-tray-fix/scripts/task3/fixed_grasp_lift.py"
with open(path) as f:
    c = f.read()

old = "if not ok and args.transport_to_dining:"
new = "if not ok:"
assert old in c, "Could not find the transport_to_dining gate"
c = c.replace(old, new)

old2 = "budget_s=50.0 if args.transport_to_dining else 20.0"
new2 = "budget_s=50.0"
assert old2 in c, "Could not find the budget line"
c = c.replace(old2, new2)

with open(path, "w") as f:
    f.write(c)
print("FIXED: rotate_spot recovery now unconditional", flush=True)
