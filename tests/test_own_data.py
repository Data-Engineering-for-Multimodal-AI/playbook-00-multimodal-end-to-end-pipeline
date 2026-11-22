"""Checks for the "Use your own data" loader (scripts/own_data.py). No download, no cloud."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import fixture  # noqa: E402
from own_data import scan  # noqa: E402


@pytest.fixture
def folder(tmp_path):
    return fixture.make(tmp_path / "cell")


def test_fixture_passes_with_notes(folder):
    readings, problems, notes = scan(folder)
    assert problems == [] and readings == 10
    assert notes[0] == "analog/Conveyor_Signals.csv: 5 drive temperatures outside -40 to 150 C; the baselines leave them out"
    assert "1 of 10 readings fail schemas/ff_reading_v1.json" in notes[1]
    assert notes[2].startswith("multimodal/data_1.json: 16 image references with no file")


@pytest.mark.parametrize("name,content,expected", [
    ("analog/R02_Data.csv", None, "analog/R02_Data.csv: missing"),
    ("analog/R03_Data.csv", b"version https://git-lfs.github.com/spec/v1\n", "Git LFS pointer"),
    ("analog/R04_Data.csv", b"_time,x\n\xff\xfe,1\n", "analog/R04_Data.csv: not UTF-8 text"),
    ("analog/R01_Data.csv", b"time,x\n1,2\n", "analog/R01_Data.csv: no _time column"),
    ("analog/R01_Data.csv", b"_time,x\nyesterday,2\n", "isn't an ISO 8601 timestamp (first at row 2)"),
    ("analog/Conveyor_Signals.csv", b"_time,Q_VFD1_Temperature\n2023-12-11T13:00:00Z,89\n",
     "missing Q_VFD2_Temperature, Q_VFD3_Temperature, Q_VFD4_Temperature"),
    ("multimodal/data_2.json", b"{not json", "multimodal/data_2.json: not valid JSON"),
    ("multimodal/data_x.json", b"{}", "multimodal/data_x.json: name must be data_<number>.json"),
    ("multimodal/data_3.json", b"[]", "must be a JSON object of timestamp -> reading"),
    ("multimodal/data_4.json", b'{"2023-12-11 10:00:00": {}, "2023-12-11 10:00:00": {}}',
     "timestamp '2023-12-11 10:00:00' appears 2 times"),
    ("multimodal/data_5.json", b'{"11/12/2023 10:00": {"Images": [], "Sensor_values": {}}}',
     "1 timestamps the pipeline can't read (first '11/12/2023 10:00')"),
    ("multimodal/data_6.json", b'{"2023-12-11 10:00:01": {}, "2023-12-11 10:00:00": {}}',
     "timestamps go back in time 1 times"),
    ("multimodal/data_7.json", b'{"2023-12-11 10:00:00": {"Images": "a.png", "Sensor_values": {}}}',
     "1 readings without an object for Sensor_values and a list for Images"),
])
def test_problems_are_reported(folder, name, content, expected):
    path = folder / name
    if content is None:
        path.unlink()
    else:
        path.write_bytes(content)
    _, problems, _ = scan(folder)
    assert len(problems) == 1 and expected in problems[0], problems


def test_every_problem_is_listed(folder):
    (folder / "analog" / "R02_Data.csv").unlink()
    (folder / "multimodal" / "data_2.json").write_text("{")
    _, problems, _ = scan(folder)
    assert [p.split(":")[0] for p in problems] == ["analog/R02_Data.csv", "multimodal/data_2.json"]


def test_missing_folders(tmp_path):
    (tmp_path / "x").mkdir()
    _, problems, _ = scan(tmp_path / "x")
    assert problems == ["analog/: missing (the historical baselines need the five analog CSV files)",
                        "multimodal/: missing"]
    assert scan(tmp_path / "nope")[1] == [f"{tmp_path / 'nope'}: not a folder"]

