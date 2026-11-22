"""
Stage 1: Ingest. Read the multimodal batches (data_<N>.json: timestamp -> sensor values and the two
camera images), validate every reading against schemas/ff_reading_v1.json, and add derived features.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from jsonschema import Draft7Validator

from resolve import config

VFD = [f"Q_VFD{i}_Temperature" for i in range(1, 5)]
CONVEYORS = [f"M_Conv{i}_Speed_mmps" for i in range(1, 5)]
_validator = Draft7Validator(json.loads((config.SCHEMAS / "ff_reading_v1.json").read_text()))


@dataclass
class Reading:
    trace_id: str
    batch: str
    ts: str
    sensor_values: Dict
    images: List[str]
    errors: List[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def derived(values: Dict) -> Dict:
    temps = [values[k] for k in VFD if isinstance(values.get(k), (int, float)) and -40 <= values[k] <= 150]
    return {"max_vfd_temperature": max(temps) if temps else None,
            "conveyor_moving": any((values.get(k) or 0) > 0 for k in CONVEYORS)}


def batches(folder: Optional[Path] = None) -> List[Path]:
    return sorted((folder or config.MULTIMODAL).glob("data_*.json"), key=lambda p: int(p.stem.split("_")[1]))


def read(paths: List[Path]) -> Iterator[Reading]:
    for path in paths:
        records = json.loads(path.read_text())
        for i, (ts, record) in enumerate(records.items()):
            reading = Reading(trace_id=f"{path.stem}-{i:04d}", batch=path.stem, ts=ts,
                              sensor_values=record.get("Sensor_values", {}), images=record.get("Images", []))
            document = {"ts": ts, "sensor_values": reading.sensor_values, "images": reading.images}
            reading.errors = [f"{'/'.join(map(str, e.path)) or 'record'}: {e.message[:120]}"
                              for e in _validator.iter_errors(document)]
            yield reading


def local_image(reference: str) -> Optional[Path]:
    """The downloaded file for an image reference ("Dataset/BATCH1000/000000_0.png"), if it was downloaded."""
    path = config.MULTIMODAL / reference.replace("Dataset/", "")
    return path if path.exists() else None
