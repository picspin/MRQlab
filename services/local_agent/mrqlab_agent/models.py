from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


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


class LeaseSoftware(AgentModel):
    """Signed runtime-compatibility window a lease is valid against.

    Only the keys the verifier enforces are declared; ``extra="forbid"`` stops a
    signed-but-unenforced key from being silently accepted. Strict scalar members
    keep JSON ``true``/``false`` from coercing into a numeric bound (``bool`` is
    an ``int`` subtype) and keep a quoted number such as ``"2"`` from passing as
    a version bound.
    """

    min_version: StrictStr | None = None
    max_major: StrictInt | None = None


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
    limits: dict[str, StrictInt]
    # Required: a signed lease always carries its compatibility window, so an
    # omitted claim fails closed as malformed rather than verifying active with
    # no window. StrictInt limits stop a signed `true` becoming the limit 1.
    software: LeaseSoftware
    key_id: str


class LeaseDecision(AgentModel):
    state: Literal["active", "offline_grace"]
    claims: LeaseClaims
