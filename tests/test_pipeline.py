import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
DATA = Path(tempfile.mkdtemp(prefix="resolve-data-"))
OUT = Path(tempfile.mkdtemp(prefix="resolve-out-"))
os.environ["RESOLVE_DATA"], os.environ["RESOLVE_OUTPUT"] = str(DATA), str(OUT)

import fixture  # noqa: E402
fixture.make(DATA)

from resolve.fusion import Fusion  # noqa: E402
from resolve.pipeline import run  # noqa: E402
from resolve.planner import evaluate, load_policy  # noqa: E402
from resolve.safety import SafetyCheck  # noqa: E402


def test_conditions():
    assert evaluate("a == false and b == true", {"a": False, "b": True})
    assert not evaluate("a == false and b == true", {"a": False, "b": False})
    assert evaluate("z.t > 3", {"z.t": 3.5}) and not evaluate("missing > 1", {})


def test_fusion_waits_for_both_images_and_times_out():
    fusion = Fusion(timeout_s=5)
    telemetry = {"kind": "telemetry", "trace_id": "a", "ts": "2023-12-11 10:00:00", "batch": "b",
                 "expected_images": 2, "features": {}}
    image = {"kind": "image", "trace_id": "a", "ts": "2023-12-11 10:00:00", "camera_id": "camera_0", "local_path": None}
    assert fusion.add(telemetry) == [] and fusion.add(image) == []        # one image isn't enough
    done = fusion.add({**image, "camera_id": "camera_1"})
    assert len(done) == 1 and done[0]["fusion"]["complete"] and done[0]["fusion"]["images_received"] == 2
    fusion.add({**telemetry, "trace_id": "b"})
    late = fusion.add({**telemetry, "trace_id": "c", "ts": "2023-12-11 10:00:09"})
    assert [r["trace_id"] for r in late] == ["b"] and not late[0]["fusion"]["complete"]


def test_safety_check():
    check = SafetyCheck(load_policy())
    plan = {"ts": "2023-12-11 10:00:00", "actions": [
        {"action": "emergency_stop", "parameters": {"reason": "door", "zone": "cell"}, "rule": "r"},
        {"action": "self_destruct", "parameters": {}, "rule": "r"},
        {"action": "reduce_speed", "parameters": {"reduction_percent": 150}, "rule": "r"}]}
    approved, blocked = check.check(plan)
    assert [a["action"] for a in approved] == ["emergency_stop"]
    assert len(blocked) == 2
    again, blocked = check.check({**plan, "ts": "2023-12-11 10:00:30", "actions": plan["actions"][:1]})
    assert not again and "within 60 s" in blocked[0]["blocked_because"]


def test_pipeline_end_to_end():
    report = run()
    assert report["ingest"] == {"readings": 10, "rejected": 1, "rejected_fields": {
        "sensor_values/Q_VFD1_Temperature": 1, "sensor_values/Q_VFD2_Temperature": 1,
        "sensor_values/Q_VFD3_Temperature": 1, "sensor_values/Q_VFD4_Temperature": 1},
        "published": {"telemetry": 9, "images": 18}}
    assert report["baselines"]["implausible_values_excluded"] == {"Q_VFD2_Temperature": 5}
    assert report["fusion"]["records"] == 9 and report["fusion"]["with_both_images"] == 9
    assert report["planning"]["actions_proposed_by_rule"] == {"door2_open_while_moving": 4, "gripper_overload_r03": 1}
    # 4 door readings 20 s apart: the first and the one a minute later get through
    assert report["safety"] == {"approved": {"emergency_stop": 2, "alert_maintenance": 1},
                                "blocked": {"same action within 60 s": 2}}
    assert json.loads((OUT / "report.json").read_text())["batches"] == ["data_1"]
