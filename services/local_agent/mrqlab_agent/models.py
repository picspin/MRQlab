from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class JobRecord(AgentModel):
    id: str
    provider_id: str
    plan_fingerprint: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    artifact_id: str | None = None
    error: str | None = None


class JobEvent(AgentModel):
    sequence: int
    job_id: str
    kind: Literal["queued", "running", "artifact", "succeeded", "failed", "cancelled"]
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""


class Artifact(AgentModel):
    sha256: str
    media_type: str
    content: bytes


class CapabilityResponse(AgentModel):
    runtime: Literal["local"] = "local"
    features: dict[str, bool]
    workers: tuple[dict[str, str], ...]
    license: dict[str, str | bool | None]


from mrqlab_experiment.models import ExperimentGraph


class JobSubmitRequest(AgentModel):
    provider_id: str
    experiment: ExperimentGraph
