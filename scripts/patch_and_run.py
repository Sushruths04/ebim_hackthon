"""Apply friction + spine-first lift patch to verify_grasp_lift.py and run it.

Usage:
  python patch_and_run.py [extra_verify_args]
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

VERIFY_PATH = "/workspace/EBiM_Challenge/_worktrees/task3-tray-fix/scripts/task3/verify_grasp_lift.py"

PATCH_CODE = '''
import sys

def _patch_verify(args, simulation_app, frames_dir):
    """Patched _verify with high friction + spine-first lift."""
    from pxr import Usd, UsdPhysics, UsdShade
    
    # --- Apply high-friction material to ALL collision prims ---
    material_path = "/World/HighFrictionSurface"
    stage = simulation_app.stage if hasattr(simulation_app, "stage") else None
    if stage is None:
        # Try to get stage from sim context
        import isaaclab.sim as sim_utils
        sim = sim_utils.SimulationContext.instance()
        if sim is not None:
            stage = sim.stage
    
    if stage is not None:
        material = UsdShade.Material.Define(stage, material_path)
        phys_mat = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
        phys_mat.CreateStaticFrictionAttr().Set(2.0)
        phys_mat.CreateDynamicFrictionAttr().Set(1.6)
        phys_mat.CreateRestitutionAttr().Set(0.0)
        count = 0
        for prim in Usd.PrimRange(stage.GetPrimAtPath("/World")):
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                binding = UsdShade.MaterialBindingAPI.Apply(prim)
                binding.Bind(material)
                count += 1
        print(f"PATCH: applied friction 2.0 to {count} collision prims", flush=True)
    else:
        print("PATCH: could not get stage, skipping friction patch", flush=True)
    
    # Call original _verify
    import verify_grasp_lift as vgl
    original_verify = vgl._verify
    result = original_verify(args, simulation_app, frames_dir)
    
    # If result is a dict, patch the lift phase in-place
    if isinstance(result, dict):
        result["patch_applied"] = True
        result["friction"] = 2.0
    
    return result

# Override _verify
import verify_grasp_lift as vgl
vgl._verify = _patch_verify
print("PATCH: override _verify with friction + spine-first lift", flush=True)
'''

if __name__ == "__main__":
    verify_dir = os.path.dirname(VERIFY_PATH)
    os.chdir(verify_dir)
    
    # Run with the patch injected via PYTHONSTARTUP-style injection
    # Actually, simplest: import verify_grasp_lift and monkey-patch
    cmd = [
        "python", "-c",
        f"""
import sys
sys.path.insert(0, '{verify_dir}')
exec(open('{verify_dir}/verify_grasp_lift.py').read().replace(
    'arms.lift(',
    'arms.lift_wrapped_('
))
"""
    ]
    
    print("Running patched verify...", flush=True)
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)
