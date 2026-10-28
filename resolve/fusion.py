"""
Stage 3: Fusion. Joins each reading's telemetry with its camera images (one message per image) by trace
ID. A record is complete when the telemetry and all its images have arrived; if images are still
missing FUSION_TIMEOUT_S (data time) later, it is fused without them and says so. The first edition fused
as soon as the first image arrived, so the second camera's image was always dropped.
"""
from datetime import datetime
from typing import Dict, Iterator, List

from resolve import config


def _seconds(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


class Fusion:
    def __init__(self, timeout_s: float = config.FUSION_TIMEOUT_S):
        self.timeout_s = timeout_s
        self.open: Dict[str, Dict] = {}
        self.timeouts = 0

    def add(self, message: Dict) -> List[Dict]:
        window = self.open.setdefault(message["trace_id"], {"images": []})
        if message["kind"] == "telemetry":
            window["telemetry"] = message
        else:
            window["images"].append(message)
        done = []
        if "telemetry" in window and len(window["images"]) >= window["telemetry"]["expected_images"]:
            done.append(self._fuse(message["trace_id"], complete=True))
        done += self._expire(message["ts"])
        return done

    def flush(self) -> Iterator[Dict]:
        for trace_id in list(self.open):
            if "telemetry" in self.open[trace_id]:
                yield self._fuse(trace_id, complete=False)

    def _expire(self, now_ts: str) -> List[Dict]:
        now = _seconds(now_ts)
        late = [t for t, w in self.open.items() if "telemetry" in w and now - _seconds(w["telemetry"]["ts"]) > self.timeout_s]
        return [self._fuse(t, complete=False) for t in late]

    def _fuse(self, trace_id: str, complete: bool) -> Dict:
        window = self.open.pop(trace_id)
        if not complete:
            self.timeouts += 1
        telemetry = window["telemetry"]
        return {"trace_id": trace_id, "ts": telemetry["ts"], "batch": telemetry["batch"],
                "telemetry": telemetry["features"], "images": sorted(window["images"], key=lambda m: m["camera_id"]),
                "fusion": {"images_expected": telemetry["expected_images"], "images_received": len(window["images"]),
                           "images_local": sum(1 for m in window["images"] if m["local_path"]),
                           "complete": complete}}
