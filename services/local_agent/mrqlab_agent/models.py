from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, model_validator


class AgentModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# A signed lease timestamp: a real (finite) number, never a bool and never a
# quoted string. Plain ``float`` would coerce JSON ``true`` to ``1.0`` (``bool``
# is an ``int`` subtype — rule R3) and accept ``NaN``/``Infinity``/``1e999``
# (``inf``), any of which defeats the time-window comparison below (``now > NaN``
# is always ``False``, so such a lease would never expire).
LeaseTimestamp = Annotated[StrictFloat, Field(allow_inf_nan=False)]


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
    license: dict[str, str | bool]


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
    a version bound. At least one bound is required: an empty window would be the
    same "active with no window" outcome as an omitted claim, reached through an
    empty object, so it fails closed too.
    """

    min_version: StrictStr | None = None
    max_major: StrictInt | None = None

    @model_validator(mode="after")
    def requires_a_bound(self):
        if self.min_version is None and self.max_major is None:
            raise ValueError("software claim must declare at least one bound")
        return self


class LeaseClaims(AgentModel):
    iss: str
    aud: str
    lease_id: str
    organization_id: str
    device_id: str
    device_public_key_hash: str
    fingerprint_hash: str
    issued_at: LeaseTimestamp
    not_before: LeaseTimestamp
    expires_at: LeaseTimestamp
    offline_grace_until: LeaseTimestamp
    product: str
    features: frozenset[str]
    limits: dict[str, StrictInt]
    # Required: a signed lease always carries its compatibility window, so an
    # omitted claim fails closed as malformed rather than verifying active with
    # no window. StrictInt limits stop a signed `true` becoming the limit 1.
    software: LeaseSoftware
    key_id: str

    @model_validator(mode="after")
    def window_is_chronological(self):
        # A signed lease whose window is out of order is malformed, not merely
        # unusual: accepting it would let a future ``not_before`` or an
        # ``offline_grace_until`` before ``expires_at`` widen the validity gate
        # in a way the issuer cannot have intended.
        if not self.issued_at <= self.not_before <= self.expires_at <= self.offline_grace_until:
            raise ValueError(
                "lease window must satisfy issued_at <= not_before <= expires_at <= offline_grace_until"
            )
        return self


class LeaseDecision(AgentModel):
    state: Literal["active", "offline_grace"]
    claims: LeaseClaims
