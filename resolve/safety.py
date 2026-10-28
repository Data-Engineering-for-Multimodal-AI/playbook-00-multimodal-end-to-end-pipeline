"""
Stage 5: Safety check (the first edition called a Safety API that wasn't in the repository). Every
proposed action must be a tool in schemas/tool_registry.json with valid parameters, and the same
action for the same zone is allowed at most once per policy interval, so a sustained condition raises
one alert a minute instead of one per reading.
"""
import json
from datetime import datetime
from typing import Dict, List, Tuple

from jsonschema import Draft7Validator

from resolve import config


class SafetyCheck:
    def __init__(self, policy: Dict):
        registry = json.loads((config.SCHEMAS / "tool_registry.json").read_text())
        self.tools = {t["id"]: t for t in registry["default"]["tools"]}
        self.validators = {k: Draft7Validator(t["parameters"]) for k, t in self.tools.items()}
        self.interval = policy.get("constraints", {}).get("min_seconds_between_same_action", 60)
        self.last: Dict[Tuple[str, str], float] = {}

    def check(self, plan: Dict) -> Tuple[List[Dict], List[Dict]]:
        approved, blocked = [], []
        now = datetime.fromisoformat(plan["ts"]).timestamp()
        for action in plan["actions"]:
            name = action.get("action")
            if name not in self.tools:
                blocked.append({**action, "blocked_because": f"{name!r} is not in the tool registry"})
                continue
            errors = [e.message for e in self.validators[name].iter_errors(action.get("parameters", {}))]
            if errors:
                blocked.append({**action, "blocked_because": "invalid parameters: " + "; ".join(errors)})
                continue
            key = (name, action.get("parameters", {}).get("zone", "cell"))
            if key in self.last and now - self.last[key] < self.interval:
                blocked.append({**action, "blocked_because": f"same action within {self.interval} s"})
                continue
            self.last[key] = now
            approved.append({**action, "safety_level": self.tools[name].get("safety_level")})
        return approved, blocked
