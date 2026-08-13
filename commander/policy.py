"""Versioned Commander autonomy policy and explicit gates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class PolicyDenied(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CommanderPolicy:
    version: int
    emergency_stop: bool
    require_experiment_approval: bool
    max_running_experiments: int
    max_experiment_budget_minor: int
    decision_confidence_threshold: float
    allow_deployment: bool
    raw: Mapping[str, Any]

    @classmethod
    def load(cls, path: Path) -> "CommanderPolicy":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            version=int(raw["version"]),
            emergency_stop=bool(raw["emergencyStop"]),
            require_experiment_approval=bool(raw["approvals"]["experiments"]),
            max_running_experiments=int(raw["experiments"]["maxRunning"]),
            max_experiment_budget_minor=int(raw["budgets"]["maxExperimentMinor"]),
            decision_confidence_threshold=float(
                raw["confidence"]["minimumForAutomaticDecision"]
            ),
            allow_deployment=bool(raw["deployment"]["allowed"]),
            raw=raw,
        )

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.raw, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def require_active(self) -> None:
        if self.emergency_stop:
            raise PolicyDenied("Commander emergency stop is active")

    def check_experiment(self, *, approved: bool, budget_minor: int, running: int) -> None:
        self.require_active()
        if self.require_experiment_approval and not approved:
            raise PolicyDenied("experiment requires approval")
        if budget_minor > self.max_experiment_budget_minor:
            raise PolicyDenied("experiment budget exceeds policy")
        if running >= self.max_running_experiments:
            raise PolicyDenied("maximum running experiments reached")
