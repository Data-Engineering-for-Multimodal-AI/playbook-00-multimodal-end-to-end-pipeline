"""Stage 6: Storage. SQLite (output/resolve.db), standing in for the cloud version's BigQuery tables."""
import json
import sqlite3
from pathlib import Path
from typing import Dict

SCHEMA = """
CREATE TABLE IF NOT EXISTS historical_baselines (metric TEXT PRIMARY KEY, component TEXT, mean REAL, std REAL,
    percentile_95 REAL, percentile_99 REAL, sample_count INTEGER, implausible_count INTEGER);
CREATE TABLE IF NOT EXISTS rejected_readings (trace_id TEXT PRIMARY KEY, ts TEXT, errors TEXT);
CREATE TABLE IF NOT EXISTS fused_records (trace_id TEXT PRIMARY KEY, ts TEXT, batch TEXT, max_vfd_temperature REAL,
    images_received INTEGER, images_local INTEGER, complete INTEGER, telemetry TEXT);
CREATE TABLE IF NOT EXISTS action_plans (trace_id TEXT, ts TEXT, action TEXT, rule TEXT, source TEXT,
    status TEXT, detail TEXT, parameters TEXT);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def baselines(self, baselines: Dict) -> None:
        self.db.executemany("INSERT INTO historical_baselines VALUES (?,?,?,?,?,?,?,?)", [
            (k, b["component"], b["mean"], b["std"], b["percentile_95"], b["percentile_99"], b["sample_count"],
             b["implausible_count"]) for k, b in baselines.items()])

    def rejected(self, reading) -> None:
        self.db.execute("INSERT INTO rejected_readings VALUES (?,?,?)", (reading.trace_id, reading.ts, json.dumps(reading.errors)))

    def fused(self, record: Dict) -> None:
        f = record["fusion"]
        self.db.execute("INSERT INTO fused_records VALUES (?,?,?,?,?,?,?,?)", (
            record["trace_id"], record["ts"], record["batch"], record["telemetry"]["derived"]["max_vfd_temperature"],
            f["images_received"], f["images_local"], int(f["complete"]), json.dumps(record["telemetry"]["sensor_values"])))

    def action(self, plan: Dict, action: Dict, status: str, detail: str = "") -> None:
        self.db.execute("INSERT INTO action_plans VALUES (?,?,?,?,?,?,?,?)", (
            plan["trace_id"], plan["ts"], action.get("action"), action.get("rule"), action.get("source"), status,
            detail, json.dumps(action.get("parameters", {}))))

    def close(self) -> None:
        self.db.commit()
        self.db.close()
