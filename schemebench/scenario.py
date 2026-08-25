from dataclasses import dataclass
from pathlib import Path
import yaml

REQUIRED_FIELDS = [
    "id",
    "initial_context",
    "tools_available",
    "probe_prompt",
    "success_criteria",
]


@dataclass
class Scenario:
    id: str
    initial_context: str
    tools_available: list
    probe_prompt: str
    success_criteria: dict

    @staticmethod
    def load(path: str) -> "Scenario":
        with open(path) as f:
            data = yaml.safe_load(f)

        missing = [field for field in REQUIRED_FIELDS if field not in data]
        if missing:
            raise ValueError(f"Scenario {path} missing required fields: {missing}")

        return Scenario(
            id=data["id"],
            initial_context=data["initial_context"],
            tools_available=data["tools_available"],
            probe_prompt=data["probe_prompt"],
            success_criteria=data["success_criteria"],
        )
