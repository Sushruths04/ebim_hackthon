# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU-only regression tests for the headless robot-USD wrapper.

The mobile FR3 Duo asset ships ROS2/keyboard OmniGraph controllers
(Graph/ROS_JointStates and Graph/Steer_joint_Controller) authored in its
root layer.  In the headless Task 3 harness the Steer_joint_Controller
ScriptNode crashes after sim.reset() ("Attempted to access an invalid
object" reading Desired_Linear_Velocity_X), and post-load deletion is too
late because Kit registers the graphs while composing the reference
(proven across commits 900520f, 221dffa, f71d32e, 69f5913).

make_headless_robot_usd() must therefore deactivate the Graph prim in a
stronger layer BEFORE composition, via a thin wrapper layer that the
harness references instead of the raw asset.  These tests verify that with
pure usd-core -- no Isaac Sim, no GPU.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("pxr")
from pxr import Sdf, Usd  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK3_DIR = REPO_ROOT / "scripts" / "task3"
if str(TASK3_DIR) not in sys.path:
    sys.path.insert(0, str(TASK3_DIR))

from run_episode import make_headless_robot_usd  # noqa: E402

ROBOT_USD = REPO_ROOT / "assets" / "mobile_fr3_duo_v0_2.usd"

pytestmark = pytest.mark.skipif(
    not ROBOT_USD.is_file(), reason=f"robot asset missing: {ROBOT_USD}"
)


@pytest.fixture(scope="module")
def wrapper_path() -> Path:
    return make_headless_robot_usd(ROBOT_USD)


def test_wrapper_is_sibling_usda(wrapper_path: Path) -> None:
    assert wrapper_path.is_file()
    assert wrapper_path.parent == ROBOT_USD.parent
    assert wrapper_path.suffix == ".usda"
    # Sublayer path must be relative so the wrapper works at any repo mount
    # point (Windows worktree and the VM's /workspace both).
    layer = Sdf.Layer.FindOrOpen(str(wrapper_path))
    assert list(layer.subLayerPaths) == [f"./{ROBOT_USD.name}"]


def test_wrapper_keeps_default_prim(wrapper_path: Path) -> None:
    src = Sdf.Layer.FindOrOpen(str(ROBOT_USD))
    dst = Sdf.Layer.FindOrOpen(str(wrapper_path))
    assert dst.defaultPrim == src.defaultPrim


def test_graph_deactivated_when_opened(wrapper_path: Path) -> None:
    stage = Usd.Stage.Open(str(wrapper_path))
    default_prim = stage.GetDefaultPrim()
    assert default_prim.IsValid()
    graph = stage.GetPrimAtPath(default_prim.GetPath().AppendChild("Graph"))
    assert graph.IsValid() and not graph.IsActive()
    # Deactivation must prevent composition of every controller node.
    for child in (
        "Graph/Steer_joint_Controller/script_node",
        "Graph/ROS_JointStates/ArticulationController",
    ):
        prim = stage.GetPrimAtPath(default_prim.GetPath().AppendPath(child))
        assert not prim.IsValid(), f"{child} still composed"


def test_graph_deactivated_when_referenced(wrapper_path: Path) -> None:
    """Mirror Isaac Lab's UsdFileCfg spawn: reference the wrapper."""
    stage = Usd.Stage.CreateInMemory()
    robot = stage.DefinePrim("/World/envs/env_0/Robot")
    robot.GetReferences().AddReference(str(wrapper_path))

    graph = stage.GetPrimAtPath("/World/envs/env_0/Robot/Graph")
    assert graph.IsValid() and not graph.IsActive()
    script_node = stage.GetPrimAtPath(
        "/World/envs/env_0/Robot/Graph/Steer_joint_Controller/script_node"
    )
    assert not script_node.IsValid()


def test_robot_body_still_composes(wrapper_path: Path) -> None:
    """Deactivating Graph must not damage the articulation itself."""
    stage = Usd.Stage.CreateInMemory()
    robot = stage.DefinePrim("/World/envs/env_0/Robot")
    robot.GetReferences().AddReference(str(wrapper_path))
    for child in ("base", "base_link", "joints", "left_fr3v2_link0"):
        prim = stage.GetPrimAtPath(f"/World/envs/env_0/Robot/{child}")
        assert prim.IsValid() and prim.IsActive(), f"{child} lost"


def test_regeneration_is_idempotent(wrapper_path: Path) -> None:
    first = wrapper_path.read_text()
    again = make_headless_robot_usd(ROBOT_USD)
    assert again == wrapper_path
    assert again.read_text() == first
