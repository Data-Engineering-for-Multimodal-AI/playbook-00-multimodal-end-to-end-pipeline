"""
The local pipeline, end to end:

  1. Ingest      read the multimodal batches, validate each reading, publish telemetry and image messages
  2. Baselines   per-sensor statistics over the 30-hour analog dataset
  3. Fusion      join each reading's telemetry with its camera images
  4. Planning    deviations from the baselines; the safety policy's rules (and optionally an LLM) propose actions
  5. Safety      each action checked against the tool registry and rate limits
  6. Store       SQLite (output/resolve.db) and a report (output/report.json)
"""
import argparse
import json
import time
from collections import Counter
from typing import Dict, List, Optional

from resolve import config, readings
from resolve.baselines import compute as compute_baselines
from resolve.bus import Bus
from resolve.fusion import Fusion
from resolve.planner import llm_review, load_policy, plan
from resolve.safety import SafetyCheck
from resolve.store import Store


def run(batch_numbers: Optional[List[int]] = None, use_llm: bool = False, output=None) -> Dict:
    started = time.perf_counter()
    out = output or config.OUTPUT
    paths = [p for p in readings.batches() if batch_numbers is None or int(p.stem.split("_")[1]) in batch_numbers]
    if not paths:
        raise SystemExit(f"No multimodal batches in {config.MULTIMODAL}: python download_data.py")
    policy = load_policy()
    store = Store(out / "resolve.db")
    timings = {}

    t = time.perf_counter()
    baselines = compute_baselines()
    store.baselines(baselines)
    timings["baselines_s"] = round(time.perf_counter() - t, 1)

    bus, fusion, safety = Bus(), Fusion(), SafetyCheck(policy)
    rejected, rejected_fields = 0, Counter()
    proposed, approved, blocked = Counter(), Counter(), Counter()
    deviation_counts, llm_calls, llm_errors = Counter(), 0, []
    fused_count, temps = 0, []

    def handle(record: Dict) -> None:
        nonlocal fused_count, llm_calls
        fused_count += 1
        store.fused(record)
        if record["telemetry"]["derived"]["max_vfd_temperature"] is not None:
            temps.append(record["telemetry"]["derived"]["max_vfd_temperature"])
        result = plan(record, baselines, policy)
        deviation_counts.update(f"{k} {'above' if v > 0 else 'below'}" for k, v in result["deviations"].items())
        if use_llm and record["fusion"]["images_local"]:
            try:
                result["actions"] += llm_review(record, baselines) or []
                llm_calls += 1
            except Exception as e:  # recorded; the rules still apply
                llm_errors.append(f"{record['trace_id']}: {e}")
        ok, no = safety.check(result)
        for a in result["actions"]:
            proposed[a["rule"]] += 1
        for a in ok:
            approved[a["action"]] += 1
            store.action(result, a, "approved")
        for a in no:
            blocked[a["blocked_because"].split(":")[0]] += 1
            store.action(result, a, "blocked", a["blocked_because"])

    t = time.perf_counter()
    total = 0
    for reading in readings.read(paths):
        total += 1
        if not reading.valid:
            rejected += 1
            rejected_fields.update(e.split(":")[0] for e in reading.errors)
            store.rejected(reading)
            continue
        bus.publish("telemetry", {"kind": "telemetry", "trace_id": reading.trace_id, "ts": reading.ts,
                                  "batch": reading.batch, "expected_images": len(reading.images),
                                  "features": {"sensor_values": reading.sensor_values,
                                               "derived": readings.derived(reading.sensor_values)}})
        for camera, reference in enumerate(reading.images):
            local = readings.local_image(reference)
            bus.publish("images", {"kind": "image", "trace_id": reading.trace_id, "ts": reading.ts,
                                   "camera_id": f"camera_{camera}", "reference": reference,
                                   "local_path": str(local) if local else None})
        for topic in ("telemetry", "images"):
            for message in bus.drain(topic):
                for record in fusion.add(message):
                    handle(record)
    for record in fusion.flush():
        handle(record)
    timings["pipeline_s"] = round(time.perf_counter() - t, 1)
    store.close()

    b = baselines["max_vfd_temperature"]
    report = {
        "batches": [p.stem for p in paths],
        "ingest": {"readings": total, "rejected": rejected, "rejected_fields": dict(rejected_fields),
                   "published": dict(bus.published)},
        "baselines": {"sensors": len(baselines) - 1, "analog_samples": b["sample_count"],
                      "implausible_values_excluded": {k: v["implausible_count"] for k, v in baselines.items()
                                                      if v["implausible_count"]},
                      "max_vfd_temperature": {k: round(b[k], 2) for k in ("mean", "std", "percentile_95", "percentile_99")}},
        "fusion": {"records": fused_count, "with_both_images": fused_count - fusion.timeouts,
                   "images_downloaded": sum(1 for _ in config.MULTIMODAL.glob("BATCH*/*.png"))},
        "planning": {"deviations_over_3_std": dict(deviation_counts.most_common()),
                     "max_vfd_temperature_range": [round(min(temps), 1), round(max(temps), 1)] if temps else None,
                     "actions_proposed_by_rule": dict(proposed), "llm": {
                         "used": use_llm and bool(config.LLM_BASE_URL and config.LLM_MODEL), "calls": llm_calls,
                         "errors": llm_errors[:5]}},
        "safety": {"approved": dict(approved), "blocked": dict(blocked)},
        "first_edition_policy": {
            "rule": "emergency_stop when temperature_c > 85",
            "share_of_these_readings": round(sum(t > 85 for t in temps) / len(temps), 3) if temps else None,
            "share_of_the_30_hours": round(b["share_above_85"], 3)},
        "timings": {**timings, "total_s": round(time.perf_counter() - started, 1)},
        "output": {name: str((out / name).relative_to(config.ROOT)) if (out / name).is_relative_to(config.ROOT)
                   else str(out / name) for name in ("resolve.db", "report.json")},
    }
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report


def render(r: Dict) -> str:
    lines = [f"Batches: {', '.join(r['batches'])}",
             f"1. Ingest:    {r['ingest']['readings']} readings, {r['ingest']['rejected']} rejected by the schema"
             + (f" ({', '.join(f'{k}: {v}' for k, v in r['ingest']['rejected_fields'].items())})" if r['ingest']['rejected'] else ""),
             f"              published: {', '.join(f'{k} {v}' for k, v in r['ingest']['published'].items())}",
             f"2. Baselines: {r['baselines']['sensors']} sensors over {r['baselines']['analog_samples']:,} analog samples; "
             f"hottest drive {r['baselines']['max_vfd_temperature']['mean']:.1f} +- {r['baselines']['max_vfd_temperature']['std']:.1f} C"
             f" (99th percentile {r['baselines']['max_vfd_temperature']['percentile_99']:.1f})",
             f"              implausible values left out: " + ", ".join(f"{k} {v:,}" for k, v in r['baselines']['implausible_values_excluded'].items()),
             f"3. Fusion:    {r['fusion']['records']} records, {r['fusion']['with_both_images']} with both camera images "
             f"({r['fusion']['images_downloaded']} images downloaded)",
             f"4. Planning:  hottest drive {r['planning']['max_vfd_temperature_range'][0]}-{r['planning']['max_vfd_temperature_range'][1]} C; "
             f"readings over 3 std from the usual: "
             + (", ".join(f"{k} {v}" for k, v in r['planning']['deviations_over_3_std'].items()) or "none"),
             f"              actions proposed: {r['planning']['actions_proposed_by_rule'] or 'none'}"
             + (f"; LLM calls {r['planning']['llm']['calls']}" if r['planning']['llm']['used'] else "; LLM: not configured"),
             f"5. Safety:    approved {r['safety']['approved'] or 'none'}; blocked {r['safety']['blocked'] or 'none'}",
             f"6. Store:     {r['output']['resolve.db']}; report in {r['output']['report.json']} ({r['timings']['total_s']} s in all)",
             "",
             f"The first edition's rule ({r['first_edition_policy']['rule']}) would fire on "
             f"{r['first_edition_policy']['share_of_these_readings']:.0%} of these readings and "
             f"{r['first_edition_policy']['share_of_the_30_hours']:.0%} of the analog recording."]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batches", type=int, nargs="+", help="batch numbers (default: every downloaded batch)")
    parser.add_argument("--llm", action="store_true",
                        help="also ask an OpenAI-compatible model (LLM_BASE_URL, LLM_MODEL) about records with images")
    args = parser.parse_args(argv)
    print(render(run(args.batches, args.llm)))
    return 0
