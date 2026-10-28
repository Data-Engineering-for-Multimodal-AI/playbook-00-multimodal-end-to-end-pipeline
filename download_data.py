#!/usr/bin/env python3
"""
Download a laptop-sized slice of the Future Factories data from Kaggle (CC BY-SA 4.0).

    python download_data.py                            # defaults below (about 830 MB, 660 MB of it the analog CSVs)
    python download_data.py --batches 1000 41000 --image-every 25

- The analog dataset (61 MB zip): 30 hours of every sensor at 10 Hz, for the historical baselines.
- Multimodal batches: each data_<N>.json holds about 1,000 synchronized sensor readings with the paths of
  two camera images per reading. The images are 1.7 MB each (the whole multimodal set is 560 GB), so only
  every Nth reading's images are downloaded.

Kaggle needs an account: put your API token in ~/.kaggle/kaggle.json, or set KAGGLE_USERNAME and KAGGLE_KEY.
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ANALOG = "ramyharik/ff-2023-12-12-analog-dataset"
# The multimodal set is split over six Kaggle datasets; batch N is in the one whose range covers it
MULTIMODAL = {16: (1000, 30000), 26: (31000, 60000), 36: (61000, 90000), 46: (91000, 120000),
              56: (121000, 150000), 66: (151000, 166000)}
DEFAULT_BATCHES = [1000, 61000, 157000]   # cold start; mid-run; a safety door open while the conveyor runs


def api():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        sys.exit("The kaggle package is missing: pip install -r requirements.txt")
    client = KaggleApi()
    try:
        client.authenticate()
    except Exception as e:
        sys.exit(f"Kaggle login failed ({e}). Put your API token in ~/.kaggle/kaggle.json "
                 "or set KAGGLE_USERNAME and KAGGLE_KEY.")
    return client


def dataset_for(batch: int) -> str:
    for part, (lo, hi) in MULTIMODAL.items():
        if lo <= batch <= hi:
            return f"ramyharik/ff-2023-12-12-multi-modal-dataset-{part}"
    raise SystemExit(f"No multimodal batch {batch}: batches are 1000, 2000, ... 166000")


def fetch(client, dataset: str, name: str, root: Path) -> Path:
    """One file from a Kaggle dataset, saved as root/name. Kaggle keeps the file's folder and may zip it."""
    target = root / name
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    client.dataset_download_file(dataset, name, path=str(target.parent if "/" not in name else root), quiet=True)
    for zipped in (root / (name + ".zip"), target.parent / (Path(name).name + ".zip")):
        if zipped.exists():
            with zipfile.ZipFile(zipped) as z:
                target.write_bytes(z.read(z.namelist()[0]))
            zipped.unlink()
    if not target.exists():
        raise SystemExit(f"Download of {name} from {dataset} failed")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batches", type=int, nargs="+", default=DEFAULT_BATCHES,
                        help="multimodal batches (default: 1000 = cold start, 61000 = mid-run, 157000 = door 2 opened)")
    parser.add_argument("--image-every", type=int, default=50, help="download the images of every Nth reading")
    parser.add_argument("--no-analog", action="store_true", help="skip the analog dataset")
    args = parser.parse_args()
    client = api()

    if not args.no_analog and not (DATA / "analog" / "R01_Data.csv").exists():
        print(f"Analog dataset ({ANALOG}, 61 MB)...")
        client.dataset_download_files(ANALOG, path=str(DATA / "analog"), quiet=True, unzip=False)
        archive = DATA / "analog" / "ff-2023-12-12-analog-dataset.zip"
        with zipfile.ZipFile(archive) as z:
            for member in z.namelist():
                if member.endswith(".csv"):
                    (DATA / "analog" / Path(member).name).write_bytes(z.read(member))
        archive.unlink()
    manifest = {}
    for batch in args.batches:
        dataset = dataset_for(batch)
        folder = DATA / "multimodal"
        path = fetch(client, dataset, f"data_{batch}.json", folder)
        readings = json.loads(path.read_text())
        images = [img for i, r in enumerate(readings.values()) if i % args.image_every == 0 for img in r["Images"]]
        print(f"Batch {batch}: {len(readings)} readings; downloading {len(images)} of their "
              f"{2 * len(readings)} images ({dataset.split('/')[1]})...")
        for name in images:
            fetch(client, dataset, name.replace("Dataset/", ""), folder)
        manifest[f"data_{batch}.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (DATA / "SOURCE.json").write_text(json.dumps({
        "analog": f"https://www.kaggle.com/datasets/{ANALOG}", "multimodal_parts": sorted({dataset_for(b) for b in args.batches}),
        "batches_sha256": manifest, "image_every": args.image_every, "license": "CC BY-SA 4.0",
        "paper": "https://arxiv.org/abs/2401.15544"}, indent=2))
    size = sum(f.stat().st_size for f in DATA.rglob("*") if f.is_file()) / 1e6
    print(f"data/: {size:.0f} MB. Next: python run_pipeline.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
