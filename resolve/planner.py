"""
Stage 4: Planning. For each fused record: the deviations from the historical baselines, then the rules
in schemas/safety_policy.yaml, which propose actions. Optionally, an LLM (any OpenAI-compatible chat
API, such as a local Ollama server) also reviews the record with its images; its actions go through the
same safety check. The cloud version uses Gemini for this step.
"""
import base64
import json
import re
from typing import Dict, List, Optional

import requests
import yaml

from resolve import config
from resolve.baselines import zscore
from resolve.readings import VFD

_CONDITION = re.compile(r"^\s*([\w.]+)\s*(==|!=|>=|<=|>|<)\s*(\S+)\s*$")


def load_policy() -> Dict:
    return yaml.safe_load((config.SCHEMAS / "safety_policy.yaml").read_text())


def _value(token: str):
    if token in ("true", "false"):
        return token == "true"
    return float(token)


def evaluate(condition: str, context: Dict) -> bool:
    """`field op value` clauses joined by "and"; a missing field makes the condition false."""
    for clause in condition.split(" and "):
        m = _CONDITION.match(clause)
        if not m:
            raise ValueError(f"Can't read condition clause {clause!r}")
        name, op, raw = m.groups()
        left = context.get(name)
        if left is None:
            return False
        right = _value(raw)
        ok = {"==": left == right, "!=": left != right, ">": left > right, "<": left < right,
              ">=": left >= right, "<=": left <= right}[op]
        if not ok:
            return False
    return True


def context_for(record: Dict, baselines: Dict) -> Dict:
    values = record["telemetry"]["sensor_values"]
    context = {**values, **record["telemetry"]["derived"]}
    for name in list(values) + ["max_vfd_temperature"]:
        if isinstance(context.get(name), (int, float)) and not isinstance(context.get(name), bool):
            context[f"z.{name}"] = zscore(baselines, name, context[name])
    return context


WATCHED = ("Temperature", "max_vfd_temperature", "Gripper_Load")   # the signals the policy acts on


def deviations(context: Dict, threshold: float = 3.0) -> Dict[str, float]:
    """Watched signals more than `threshold` standard deviations from their historical mean (signed)."""
    return {k[2:]: round(v, 2) for k, v in context.items()
            if k.startswith("z.") and abs(v) > threshold and any(w in k for w in WATCHED)}


def plan(record: Dict, baselines: Dict, policy: Dict) -> Dict:
    context = context_for(record, baselines)
    actions = [{"action": r["action"], "rule": r["name"], "parameters": dict(r.get("parameters", {})),
                "source": "rules"} for r in policy["rules"] if evaluate(r["condition"], context)]
    return {"trace_id": record["trace_id"], "ts": record["ts"], "deviations": deviations(context),
            "max_vfd_temperature": context.get("max_vfd_temperature"), "actions": actions}


def llm_review(record: Dict, baselines: Dict, timeout: int = 120) -> Optional[List[Dict]]:
    """Ask an OpenAI-compatible model for actions (LLM_BASE_URL and LLM_MODEL must be set)."""
    if not (config.LLM_BASE_URL and config.LLM_MODEL):
        return None
    context = context_for(record, baselines)
    text = ("You monitor a robotic assembly cell (four robots, a conveyor loop). Current readings: "
            f"drive temperatures {[context.get(k) for k in VFD]} C (usual {baselines['max_vfd_temperature']['mean']:.1f}"
            f" +- {baselines['max_vfd_temperature']['std']:.1f}), safety doors closed: "
            f"{[context.get('I_SafetyDoor1_Status'), context.get('I_SafetyDoor2_Status')]}, deviations over 3 standard "
            f"deviations: {deviations(context)}. The images are the two cameras over the cell. Reply with JSON only: "
            '{"actions": [{"action": "emergency_stop|reduce_speed|alert_maintenance|log_incident", '
            '"parameters": {...}, "reasoning": "..."}]} with an empty list if nothing is needed.')
    content = [{"type": "text", "text": text}]
    for image in record["images"]:
        if image["local_path"]:
            data = base64.b64encode(open(image["local_path"], "rb").read()).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}})
    response = requests.post(f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions", timeout=timeout,
                             headers={"Authorization": f"Bearer {config.LLM_API_KEY}"} if config.LLM_API_KEY else {},
                             json={"model": config.LLM_MODEL, "messages": [{"role": "user", "content": content}],
                                   "temperature": 0})
    response.raise_for_status()
    reply = response.json()["choices"][0]["message"]["content"]
    found = re.search(r"\{.*\}", reply, re.S)
    actions = json.loads(found.group(0)).get("actions", []) if found else []
    return [{"action": a.get("action"), "parameters": a.get("parameters") or {}, "rule": "llm",
             "reasoning": a.get("reasoning", ""), "source": "llm"} for a in actions if isinstance(a, dict)]
