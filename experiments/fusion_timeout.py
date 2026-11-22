"""Try this 1: how long should fusion wait for the camera images? (make try-fusion-timeout)

Stage 3 joins each reading's telemetry with its two camera images. If an image hasn't arrived
FUSION_TIMEOUT_S seconds (data time) after the reading, the record is fused without it. This
replays a synthetic stream through resolve.fusion.Fusion with different timeouts: one reading a
second, camera 0's image 0.2 s after the reading, camera 1's after a random delay (2 s on average,
some much later), and 5% of camera 1's images lost. No data download, no cloud.

Change the delays, the loss rate or TIMEOUTS below and run it again.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from resolve.fusion import Fusion  # noqa: E402

READINGS = 2000
TIMEOUTS = [0.5, 1, 2, 5, 10, 30]
CAMERA1_MEAN_DELAY_S = 2.0
CAMERA1_LOSS = 0.05
START = datetime(2023, 12, 11, 13, 0, 0)


def stream(seed: int = 0):
    """Messages in arrival order. Image messages carry their reading's timestamp, as in the pipeline."""
    rng = np.random.default_rng(seed)
    events = []
    for i in range(READINGS):
        ts = START + timedelta(seconds=i)
        stamp = ts.isoformat(sep=" ")
        trace = f"r{i:05d}"
        events.append((i, 0, {"kind": "telemetry", "trace_id": trace, "ts": stamp, "batch": "sim",
                              "expected_images": 2, "features": {}}))
        events.append((i + 0.2, 1, {"kind": "image", "trace_id": trace, "ts": stamp, "camera_id": "camera_0",
                                    "local_path": None}))
        if rng.random() >= CAMERA1_LOSS:
            events.append((i + rng.exponential(CAMERA1_MEAN_DELAY_S), 2,
                           {"kind": "image", "trace_id": trace, "ts": stamp, "camera_id": "camera_1", "local_path": None}))
    events.sort(key=lambda e: (e[0], e[1]))
    return [(arrival, message) for arrival, _, message in events]


def main() -> int:
    messages = stream()
    lost = READINGS * 2 - sum(1 for _, m in messages if m["kind"] == "image")
    print(f"{READINGS:,} readings, one a second; {lost} of camera 1's images never arrive\n")
    print(f"{'timeout':>8}  {'both images':>11}  {'one image':>9}  {'image came later':>16}  {'wait p50':>8}  {'wait p95':>8}")
    for timeout in TIMEOUTS:
        fusion = Fusion(timeout_s=timeout)
        fused_at, partial = {}, set()
        for arrival, message in messages:
            for record in fusion.add(message):
                fused_at[record["trace_id"]] = arrival
                if not record["fusion"]["complete"]:
                    partial.add(record["trace_id"])
        for record in fusion.flush():
            fused_at[record["trace_id"]] = messages[-1][0]
            partial.add(record["trace_id"])
        late_images = sum(1 for arrival, m in messages
                          if m["kind"] == "image" and m["trace_id"] in partial and arrival > fused_at[m["trace_id"]])
        waits = np.array([fused_at[f"r{i:05d}"] - i for i in range(READINGS)])
        print(f"{timeout:>7g}s  {READINGS - len(partial):>11,}  {len(partial):>9,}  {late_images:>16,}  "
              f"{np.percentile(waits, 50):>7.1f}s  {np.percentile(waits, 95):>7.1f}s")
    print("\nimage came later: records fused with one image whose second image did arrive, too late.")
    print("wait: seconds from the reading to its fused record, in data time.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
