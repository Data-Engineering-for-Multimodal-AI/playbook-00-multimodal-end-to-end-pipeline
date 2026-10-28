"""
Stage 2: Historical baselines (the first edition's historical processor). Per sensor, over the 30-hour
analog dataset: mean, standard deviation, 95th and 99th percentiles, count. Implausible values (the
drive temperature sensors sometimes report about 3e38) are left out and counted.
"""
from typing import Dict

import numpy as np
import pandas as pd

from resolve import config
from resolve.readings import VFD

FILES = ["Conveyor_Signals.csv", "R01_Data.csv", "R02_Data.csv", "R03_Data.csv", "R04_Data.csv"]
PLAUSIBLE = {**{k: (-40, 150) for k in VFD}}


def compute() -> Dict[str, Dict]:
    frames = []
    for name in FILES:
        path = config.ANALOG / name
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing: python download_data.py")
        frame = pd.read_csv(path, low_memory=False)
        frames.append(frame.drop(columns=["_time", "Description"], errors="ignore"))
    data = pd.concat(frames, axis=1)
    out = {}
    numeric = [c for c in data.columns if pd.api.types.is_numeric_dtype(data[c]) and not pd.api.types.is_bool_dtype(data[c])]
    for column in numeric:
        values = data[column].astype(float)
        lo, hi = PLAUSIBLE.get(column, (-1e6, 1e6))
        ok = values.between(lo, hi)
        v = values[ok]
        out[column] = {"component": component(column), "mean": float(v.mean()), "std": float(v.std()),
                       "percentile_95": float(v.quantile(.95)), "percentile_99": float(v.quantile(.99)),
                       "sample_count": int(ok.sum()), "implausible_count": int((~ok & values.notna()).sum())}
    raw = data[VFD].astype(float)
    temps = raw.where((raw >= -40) & (raw <= 150)).max(axis=1)
    out["max_vfd_temperature"] = {"component": "conveyor", "mean": float(temps.mean()), "std": float(temps.std()),
                                  "percentile_95": float(temps.quantile(.95)), "percentile_99": float(temps.quantile(.99)),
                                  "sample_count": int(temps.notna().sum()), "implausible_count": 0,
                                  # the first edition's rule: emergency stop above 85 C
                                  "share_above_85": float((temps > 85).mean())}
    return out


def component(column: str) -> str:
    for robot in ("R01", "R02", "R03", "R04"):
        if f"_{robot}_" in column:
            return robot.lower()
    return "conveyor" if "VFD" in column or "Conv" in column or "Stopper" in column else "cell"


def zscore(baselines: Dict[str, Dict], name: str, value) -> float:
    b = baselines.get(name)
    if b is None or value is None or not b["std"] or not np.isfinite(b["std"]):
        return 0.0
    return (float(value) - b["mean"]) / b["std"]
