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


class DeviceIdentity(AgentModel):
    device_id: str
    device_public_key_hash: str
    fingerprint_hash: str


class DeviceRegistrationRequest(AgentModel):
    device_id: str
    device_public_key_b64: str
    device_public_key_hash: str
    fingerprint_hash: str


class LeaseClaims(AgentModel):
    iss: str
    aud: str
    lease_id: str
    organization_id: str
    device_id: str
    device_public_key_hash: str
    fingerprint_hash: str
    issued_at: float
    not_before: float
    expires_at: float
    offline_grace_until: float
    product: str
    features: frozenset[str]
    limits: dict[str, int]
    software: dict[str, str | int]
    key_id: str


class LeaseDecision(AgentModel):
    state: Literal["active", "offline_grace"]
    claims: LeaseClaims
