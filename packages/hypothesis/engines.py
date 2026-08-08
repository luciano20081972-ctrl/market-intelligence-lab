from __future__ import annotations

import importlib.metadata
import shutil
from dataclasses import asdict
from typing import Any

from packages.hypothesis.types import EngineStatus


class QlibResearchEngine:
    name = "qlib"
    supported_version = "0.9.7"

    def status(self) -> EngineStatus:
        try:
            version = importlib.metadata.version("pyqlib")
        except importlib.metadata.PackageNotFoundError:
            version = None
        return EngineStatus(
            engine=self.name,
            version=version,
            available=version is not None,
            enabled=False,
            message=(
                "Qlib is installed but execution is disabled by default"
                if version
                else "Qlib is optional and unavailable; core research remains functional"
            ),
            capabilities=("snapshot_input", "factor_evaluation", "model_workflow", "backtest"),
            security_boundaries=(
                "MIL remains canonical storage",
                "point-in-time snapshots only",
                "no database credentials",
            ),
        )

    def fixture_run(self, manifest: dict[str, Any]) -> dict[str, Any]:
        required = {"feature_snapshot_id", "universe_version_id", "partitions", "seed"}
        if missing := sorted(required - manifest.keys()):
            raise ValueError(f"Qlib manifest is missing: {', '.join(missing)}")
        return {
            "status": "fixture_completed",
            "engine": self.name,
            "engine_version": self.supported_version,
            "input_authority": "market-intelligence-lab",
            "manifest": manifest,
            "normalized_output": {
                "rank_ic": 0.031,
                "warnings": ["FIXTURE_ONLY", "NOT_LIVE_QLIB_EXECUTION"],
            },
        }


class RDAgentResearchEngine:
    name = "rd-agent"
    supported_version = "0.8.0"

    def status(self) -> EngineStatus:
        executable = shutil.which("rdagent")
        return EngineStatus(
            engine=self.name,
            version=self.supported_version if executable else None,
            available=executable is not None,
            enabled=False,
            message=(
                "RD-Agent is detected but host execution is disabled"
                if executable
                else "RD-Agent is optional, Linux/Docker-oriented, and unavailable"
            ),
            capabilities=("bounded_research_brief", "candidate_artifact"),
            security_boundaries=(
                "network disabled by default",
                "no production secrets",
                "no database, GitHub, brokerage, or Supabase credentials",
                "no automatic repository merge",
                "bounded CPU, memory, time, and filesystem required",
            ),
        )

    def fixture_artifact(self, brief: dict[str, Any]) -> dict[str, Any]:
        if not brief.get("hypothesis_id") or not brief.get("maximum_candidates"):
            raise ValueError("RD-Agent brief must be bounded and identify a hypothesis")
        if int(brief["maximum_candidates"]) > 10:
            raise ValueError("RD-Agent candidate limit exceeds the v0.10 hard bound")
        return {
            "status": "fixture_completed",
            "engine": self.name,
            "engine_version": self.supported_version,
            "executed_generated_code": False,
            "automatically_merged": False,
            "security": asdict(self.status()),
            "artifact": {
                "kind": "candidate_feature_spec",
                "requires_mil_validation": True,
                "source": "deterministic-rd-agent-fixture",
            },
        }
