"""Try this 3: what do a few broken sensor values do to the baselines? (make try-bad-values)

The real drive temperature sensors sometimes report about 3e38 (the analog data has such values).
Stage 2 (resolve/baselines.py) leaves values outside -40 to 150 C out of the baselines. This builds
synthetic analog files like the test fixture (2,000 samples, drives at about 89 C) with more and
more of those values, computes the baselines both ways, and checks whether a drive at 95 C still
triggers the policy's "drive_hotter_than_usual" rule (z above 3). No data download, no cloud.

Change BAD_COUNTS or HOT_C and run it again.
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from resolve import baselines, config  # noqa: E402
from resolve.readings import VFD  # noqa: E402

SAMPLES = 2000
BAD_COUNTS = [0, 1, 5, 20, 100]
HOT_C = 95.0
BROKEN = 2.98e38


def analog(folder: Path, bad: int) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    time = pd.date_range("2023-12-11 13:00", periods=SAMPLES, freq="100ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    conveyor = pd.DataFrame({"_time": time, **{k: 89 + rng.normal(0, 1, SAMPLES) for k in VFD}, "Description": ""})
    conveyor.loc[rng.choice(SAMPLES, bad, replace=False), "Q_VFD2_Temperature"] = BROKEN
    folder.mkdir(parents=True, exist_ok=True)
    conveyor.to_csv(folder / "Conveyor_Signals.csv", index=False)
    for r in range(1, 5):
        pd.DataFrame({"_time": time, f"I_R0{r}_Gripper_Load": 500 + rng.normal(0, 20, SAMPLES)}).to_csv(
            folder / f"R0{r}_Data.csv", index=False)
    return conveyor


def main() -> int:
    print(f"{SAMPLES:,} analog samples; a reading with the hottest drive at {HOT_C:g} C\n")
    print(f"{'broken values':>13}  {'raw mean':>9}  {'raw z':>6}  {'alert':>5}  {'cleaned mean':>12}  {'cleaned z':>9}  {'alert':>5}")
    with tempfile.TemporaryDirectory() as tmp:
        for bad in BAD_COUNTS:
            folder = Path(tmp) / f"bad{bad}"
            conveyor = analog(folder, bad)
            raw = conveyor[VFD].astype(float).max(axis=1)
            raw_z = (HOT_C - raw.mean()) / raw.std()
            config.ANALOG = folder
            b = baselines.compute()["max_vfd_temperature"]
            z = baselines.zscore({"max_vfd_temperature": b}, "max_vfd_temperature", HOT_C)
            print(f"{bad:>13}  {raw.mean():>9.3g}  {raw_z:>6.2f}  {'yes' if raw_z > 3 else 'no':>5}  "
                  f"{b['mean']:>12.1f}  {z:>9.1f}  {'yes' if z > 3 else 'no':>5}")
    print("\nraw: every value counted. cleaned: values outside -40 to 150 C left out, as stage 2 does.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
