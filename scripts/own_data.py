#!/usr/bin/env python3
"""
Use your own data: check a folder in the layout of data/, then run the local pipeline on it.

    python scripts/own_data.py --dir my_cell --check-only   # check every file, write nothing
    python scripts/own_data.py --dir my_cell                # check, then run (output in output/own/)

Layout (the same as download_data.py writes):

    my_cell/
      analog/      Conveyor_Signals.csv R01_Data.csv R02_Data.csv R03_Data.csv R04_Data.csv
      multimodal/  data_<N>.json, and optionally BATCH<N>/<image>.png for the images they reference

Nothing here calls Google Cloud or an LLM.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
ANALOG_FILES = ["Conveyor_Signals.csv", "R01_Data.csv", "R02_Data.csv", "R03_Data.csv", "R04_Data.csv"]
OUT = ROOT / "output" / "own"


def _lfs(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(100).startswith(b"version https://git-lfs")


class Repeated(Exception):
    pass


def _no_duplicates(pairs):
    """json.loads keeps only the last of two equal keys; a repeated timestamp would lose a reading."""
    keys = [k for k, _ in pairs]
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    if repeated:
        raise Repeated(f"timestamp {repeated[0]!r} appears {keys.count(repeated[0])} times; "
                       "only the last reading would be kept")
    return dict(pairs)


def check_analog(folder: Path, problems: List[str], notes: List[str]) -> None:
    import pandas as pd

    from resolve.readings import VFD
    times = None
    if not folder.is_dir():
        problems.append("analog/: missing (the historical baselines need the five analog CSV files)")
        return
    for name in ANALOG_FILES:
        path = folder / name
        rel = f"analog/{name}"
        if not path.is_file():
            problems.append(f"{rel}: missing")
            continue
        if _lfs(path):
            problems.append(f"{rel}: a Git LFS pointer, not the file (run git lfs pull)")
            continue
        try:
            frame = pd.read_csv(path, low_memory=False, encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"{rel}: not UTF-8 text")
            continue
        except Exception as e:  # noqa: BLE001
            problems.append(f"{rel}: can't read as CSV ({type(e).__name__})")
            continue
        if frame.empty:
            problems.append(f"{rel}: no rows")
            continue
        if "_time" not in frame.columns:
            problems.append(f"{rel}: no _time column")
            continue
        parsed = pd.to_datetime(frame["_time"], format="ISO8601", errors="coerce", utc=True)
        if parsed.isna().any():
            problems.append(f"{rel}: {int(parsed.isna().sum())} rows with a _time that isn't an ISO 8601 timestamp "
                            f"(first at row {int(parsed.isna().idxmax()) + 2})")
        numeric = [c for c in frame.columns if c not in ("_time", "Description")
                   and pd.api.types.is_numeric_dtype(frame[c]) and not pd.api.types.is_bool_dtype(frame[c])]
        if not numeric:
            problems.append(f"{rel}: no numeric sensor columns")
        if name == "Conveyor_Signals.csv":
            missing = [c for c in VFD if c not in frame.columns]
            if missing:
                problems.append(f"{rel}: missing {', '.join(missing)} (the drive temperature baselines)")
            else:
                broken = int(sum((~frame[c].between(-40, 150) & frame[c].notna()).sum() for c in VFD))
                if broken:
                    notes.append(f"{rel}: {broken:,} drive temperatures outside -40 to 150 C; the baselines leave them out")
        if times is None:
            times = len(frame)
        elif len(frame) != times:
            notes.append(f"{rel}: {len(frame):,} rows, the first file has {times:,}; the files are joined row by row")


def check_batches(folder: Path, problems: List[str], notes: List[str]) -> int:
    from resolve.readings import _validator
    if not folder.is_dir():
        problems.append("multimodal/: missing")
        return 0
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix == ".json")
    if not files:
        problems.append("multimodal/: no data_<N>.json files")
    readings = 0
    for path in files:
        rel = f"multimodal/{path.name}"
        number = path.stem.split("_", 1)[1] if path.stem.startswith("data_") and "_" in path.stem else ""
        if not number.isdigit():
            problems.append(f"{rel}: name must be data_<number>.json")
            continue
        if _lfs(path):
            problems.append(f"{rel}: a Git LFS pointer, not the file (run git lfs pull)")
            continue
        try:
            records = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)
        except UnicodeDecodeError:
            problems.append(f"{rel}: not UTF-8 text")
            continue
        except Repeated as e:
            problems.append(f"{rel}: {e}")
            continue
        except ValueError as e:
            problems.append(f"{rel}: not valid JSON ({str(e).splitlines()[0][:100]})")
            continue
        if not isinstance(records, dict) or not records:
            problems.append(f"{rel}: must be a JSON object of timestamp -> reading, with at least one reading")
            continue
        last, bad_ts, order, shapes, invalid, first_error, missing_images = None, [], 0, 0, 0, "", 0
        for ts, record in records.items():
            try:
                when = datetime.fromisoformat(ts)
            except ValueError:
                bad_ts.append(ts)
                continue
            if last is not None and when < last:
                order += 1
            last = when
            if not isinstance(record, dict) or not isinstance(record.get("Sensor_values", {}), dict) \
                    or not isinstance(record.get("Images", []), list):
                shapes += 1
                continue
            errors = list(_validator.iter_errors({"ts": ts, "sensor_values": record.get("Sensor_values", {}),
                                                  "images": record.get("Images", [])}))
            if errors:
                invalid += 1
                first_error = first_error or f"{'/'.join(map(str, errors[0].path)) or 'record'}: {errors[0].message[:80]}"
            for reference in record.get("Images", []):
                if isinstance(reference, str) and not (folder / reference.replace("Dataset/", "")).exists():
                    missing_images += 1
        readings += len(records)
        if bad_ts:
            problems.append(f"{rel}: {len(bad_ts)} timestamps the pipeline can't read (first {bad_ts[0]!r}); "
                            "use ISO 8601, like 2023-12-11 13:00:00.000")
        if order:
            problems.append(f"{rel}: timestamps go back in time {order} times; fusion's timeout needs them in order")
        if shapes:
            problems.append(f"{rel}: {shapes} readings without an object for Sensor_values and a list for Images")
        if invalid:
            notes.append(f"{rel}: {invalid} of {len(records)} readings fail schemas/ff_reading_v1.json and will be "
                         f"rejected (first: {first_error})")
        if missing_images:
            notes.append(f"{rel}: {missing_images} image references with no file next to it; those records fuse "
                         "without local images")
    return readings


def scan(folder: Path) -> Tuple[int, List[str], List[str]]:
    sys.path.insert(0, str(ROOT))
    folder = Path(folder)
    problems: List[str] = []
    notes: List[str] = []
    if not folder.is_dir():
        return 0, [f"{folder}: not a folder"], notes
    check_analog(folder / "analog", problems, notes)
    readings = check_batches(folder / "multimodal", problems, notes)
    return readings, problems, notes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", required=True, type=Path, help="a folder with analog/ and multimodal/")
    parser.add_argument("--check-only", action="store_true", help="check the files and write nothing")
    args = parser.parse_args(argv)
    readings, problems, notes = scan(args.dir)
    if problems:
        print(f"{len(problems)} problem{'s' if len(problems) > 1 else ''} in {args.dir}; nothing was written:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"{args.dir}: OK, {readings:,} readings")
    for n in notes:
        print(f"  note: {n}")
    if args.check_only:
        return 0
    from resolve import config
    config.DATA = args.dir.resolve()
    config.MULTIMODAL, config.ANALOG, config.OUTPUT = config.DATA / "multimodal", config.DATA / "analog", OUT
    from resolve.pipeline import main as pipeline
    return pipeline([])


if __name__ == "__main__":
    sys.exit(main())
