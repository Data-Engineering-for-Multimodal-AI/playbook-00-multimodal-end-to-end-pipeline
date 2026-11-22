"""Try this 2: how many alerts should one incident raise? (make try-rate-limit)

The safety check (stage 5) lets the same action for the same zone through at most once per
`min_seconds_between_same_action` (schemas/ff_safety_policy_v1.yaml, 60 s). This plans and checks a
synthetic 20-minute stream, one reading a second, in which safety door 2 is open while the conveyor
runs twice: for 3 minutes from minute 2, and for 30 seconds from minute 8. The rules propose an
emergency stop for every one of those readings. No data download, no cloud.

Change INTERVALS or the door-open periods in OPEN and run it again.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from fixture import sensors  # noqa: E402
from resolve.planner import load_policy, plan  # noqa: E402
from resolve.readings import derived  # noqa: E402
from resolve.safety import SafetyCheck  # noqa: E402

MINUTES = 20
OPEN = [(120, 300), (480, 510)]          # seconds from the start: door 2 open, conveyor running
INTERVALS = [0, 10, 60, 300, 600]
START = datetime(2023, 12, 11, 13, 0, 0)
# Baselines for the z-score rules: the fixture's (drives at 90 +- 0.7 C, R03 gripper at 1,371 +- 20)
BASELINES = {"max_vfd_temperature": {"mean": 90.0, "std": 0.7},
             "I_R03_Gripper_Load": {"mean": 1371.0, "std": 20.0}}


def records():
    for second in range(MINUTES * 60):
        values = sensors(temp=89.0, door2=not any(a <= second < b for a, b in OPEN))
        yield {"trace_id": f"r{second:04d}", "ts": (START + timedelta(seconds=second)).isoformat(sep=" "),
               "telemetry": {"sensor_values": values, "derived": derived(values)}}


def main() -> int:
    policy = load_policy()
    proposed = sum(1 for r in records() for _ in plan(r, BASELINES, policy)["actions"])
    print(f"{MINUTES} minutes, one reading a second; door 2 open for {OPEN[0][1] - OPEN[0][0]} s from minute "
          f"{OPEN[0][0] // 60}, then {OPEN[1][1] - OPEN[1][0]} s from minute {OPEN[1][0] // 60}")
    print(f"The rules propose {proposed} emergency stops.\n")
    print(f"{'interval':>8}  {'approved':>8}  {'blocked':>7}  {'first incident':>14}  {'second incident':>15}")
    for interval in INTERVALS:
        check = SafetyCheck({**policy, "constraints": {"min_seconds_between_same_action": interval}})
        approved_at = []
        blocked = 0
        for record in records():
            ok, no = check.check(plan(record, BASELINES, policy))
            blocked += len(no)
            if ok:
                approved_at.append(int(record["trace_id"][1:]))
        per = [sum(a <= t < b for t in approved_at) for a, b in OPEN]
        mark = "  (the policy)" if interval == policy["constraints"]["min_seconds_between_same_action"] else ""
        print(f"{interval:>7}s  {len(approved_at):>8}  {blocked:>7}  {per[0]:>14}  {per[1]:>15}{mark}")
    print("\nfirst / second incident: emergency stops approved during each door-open period.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
