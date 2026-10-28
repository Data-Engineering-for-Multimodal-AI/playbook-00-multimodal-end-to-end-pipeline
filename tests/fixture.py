"""A tiny stand-in for the Future Factories data (CI can't download from Kaggle):
    python tests/fixture.py <folder>   then   RESOLVE_DATA=<folder> python run_pipeline.py"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


def sensors(temp=89.0, door1=True, door2=True, speed=111, load=1371):
    values = {f"Q_VFD{i}_Temperature": temp for i in range(1, 5)}
    values.update({f"M_Conv{i}_Speed_mmps": speed for i in range(1, 5)})
    values.update({f"I_R0{i}_Gripper_Load": load if i == 3 else 500 for i in range(1, 5)})
    values.update({"I_SafetyDoor1_Status": door1, "I_SafetyDoor2_Status": door2, "Q_Cell_CycleCount": 7})
    return values


def make(root: Path) -> Path:
    rng = np.random.default_rng(0)
    analog = root / "analog"
    analog.mkdir(parents=True, exist_ok=True)
    n = 2000
    time = pd.date_range("2023-12-11 13:00", periods=n, freq="100ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    conveyor = {"_time": time, **{f"Q_VFD{i}_Temperature": 89 + rng.normal(0, 1, n) for i in range(1, 5)},
                "Description": ""}
    conveyor["Q_VFD2_Temperature"][:5] = 2.98e38            # the sensor fault seen in the real data
    pd.DataFrame(conveyor).to_csv(analog / "Conveyor_Signals.csv", index=False)
    for r in range(1, 5):
        load = 1371 + rng.normal(0, 20, n) if r == 3 else 500 + rng.normal(0, 20, n)
        pd.DataFrame({"_time": time, f"I_R0{r}_Gripper_Load": load, "Description": ""}).to_csv(analog / f"R0{r}_Data.csv", index=False)

    multimodal = root / "multimodal"
    (multimodal / "BATCH1").mkdir(parents=True, exist_ok=True)
    records = {}
    for i in range(10):
        values = sensors()
        if 3 <= i <= 6:
            values = sensors(door2=False)                   # door 2 open while the conveyor runs
        if i == 8:
            values = sensors(temp=2.98e38)                  # an implausible reading: rejected
        if i == 9:
            values = sensors(load=6000)                     # R03 gripper far above its usual load
        images = [f"Dataset/BATCH1/{i:06d}_0.png", f"Dataset/BATCH1/{i:06d}_1.png"]
        ts = (pd.Timestamp("2023-12-11 10:00") + pd.Timedelta(seconds=20 * i)).strftime("%Y-%m-%d %H:%M:%S.%f")
        records[ts] = {"Images": images, "Sensor_values": values}
        if i % 5 == 0:
            for name in images:
                Image.new("RGB", (64, 48), (i * 20, 80, 120)).save(multimodal / name.replace("Dataset/", ""))
    (multimodal / "data_1.json").write_text(json.dumps(records))
    return root


if __name__ == "__main__":
    print(make(Path(sys.argv[1])))
