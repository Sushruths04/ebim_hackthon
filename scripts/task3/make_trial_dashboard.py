# ruff: noqa: E501
"""Build a self-contained HTML dashboard from physical tray trial JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs", nargs="+", type=Path, help="Trial result.json files"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/task3_trial_dashboard.html"),
    )
    return parser.parse_args()


def _phase_value(trial: dict[str, Any], phase: str, key: str) -> Any:
    for item in trial.get("phases", []):
        if item.get("phase") == phase:
            return item.get(key)
    return None


def _summary(trial: dict[str, Any]) -> dict[str, Any]:
    push = _phase_value(trial, "push_result", "north_overhang_m")
    edge = _phase_value(trial, "edge_close", "gripper_rad")
    lift = _phase_value(trial, "edge_lift", "lift_m")
    return {
        "name": Path(trial["_source"]).parent.name,
        "passed": bool(trial.get("passed")),
        "failed_phase": trial.get("failed_phase"),
        "overhang_m": push,
        "gripper_rad": edge,
        "lift_m": lift,
        "wall_time_s": trial.get("wall_time_seconds"),
        "phases": trial.get("phases", []),
    }


def build_dashboard(trials: list[dict[str, Any]]) -> str:
    data = [_summary(trial) for trial in trials]
    data_json = json.dumps(data, separators=(",", ":"))
    title = "Task 3 physical tray trials"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font:15px system-ui,sans-serif;background:#10151c;color:#e8eef5;margin:0;padding:24px}}
h1{{margin:0 0 6px}} .muted{{color:#9eacbb}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:18px 0}}
.card{{background:#18212c;border:1px solid #2b3949;border-radius:10px;padding:14px}} .big{{font-size:25px;font-weight:700}}
select{{background:#18212c;color:#fff;border:1px solid #506276;border-radius:6px;padding:8px;font-size:15px}}
table{{border-collapse:collapse;width:100%;background:#18212c}} th,td{{padding:8px;border-bottom:1px solid #2b3949;text-align:left;font-size:13px}}
.ok{{color:#62e6a4}} .bad{{color:#ff8f8f}} .bar{{height:14px;background:#293849;border-radius:7px;overflow:hidden;margin:5px 0 14px}} .fill{{height:100%;background:#5aa9ff}}
code{{color:#c9dcf3}} .phase{{display:flex;gap:8px;align-items:center;margin:5px 0}} .dot{{width:9px;height:9px;border-radius:50%;background:#62e6a4}} .fail .dot{{background:#ff6d6d}}
</style></head><body>
<h1>{title}</h1><div class="muted">Self-contained review of exported physics-contact evidence. No scene or physics values are changed.</div>
<p><label>Trial: <select id="pick"></select></label></p><div id="view"></div>
<script>
const trials={data_json}; const pick=document.getElementById('pick'), view=document.getElementById('view');
trials.forEach((t,i)=>{{const o=document.createElement('option');o.value=i;o.textContent=t.name+(t.passed?' — PASS':' — '+(t.failed_phase||'failed'));pick.appendChild(o)}});
function esc(s){{return String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function render(){{const t=trials[pick.value]; const cls=t.passed?'ok':'bad'; const ov=t.overhang_m==null?'—':(t.overhang_m*100).toFixed(1)+' cm';
let rows=t.phases.map(p=>`<div class="phase ${{p.phase===t.failed_phase?'fail':''}}"><span class="dot"></span><code>${{esc(p.phase)}}</code><span class="muted">${{p.ok===false?'FAILED':'ok'}}</span></div>`).join('');
view.innerHTML=`<div class="grid"><div class="card"><div class="muted">Result</div><div class="big ${{cls}}">${{t.passed?'PASS':'FAIL'}}</div></div><div class="card"><div class="muted">Slide overhang</div><div class="big">${{ov}}</div><div class="bar"><div class="fill" style="width:${{Math.min(100,Math.max(0,(t.overhang_m||0)/0.05*100))}}%"></div></div><div class="muted">gate: 5.0 cm</div></div><div class="card"><div class="muted">Gripper at close</div><div class="big">${{t.gripper_rad==null?'—':t.gripper_rad.toFixed(4)+' rad'}}</div></div><div class="card"><div class="muted">Measured lift</div><div class="big">${{t.lift_m==null?'—':(t.lift_m*100).toFixed(1)+' cm'}}</div></div></div>
<div class="card"><b>Failure phase:</b> <span class="${{cls}}">${{esc(t.failed_phase||'none')}}</span><br><span class="muted">wall time: ${{t.wall_time_s??'—'}} s</span><hr>${{rows}}</div>`}}
pick.addEventListener('change',render); render();
</script></body></html>"""


def main() -> None:
    args = parse_args()
    trials: list[dict[str, Any]] = []
    for path in args.inputs:
        trial = json.loads(path.read_text(encoding="utf-8"))
        trial["_source"] = str(path)
        trials.append(trial)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_dashboard(trials), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
