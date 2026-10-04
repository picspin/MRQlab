from __future__ import annotations

from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from .kernel import ValidationReport, run_experiment
from .models import ExperimentGraph
from .observations import ResultGraph, build_result_graph
from .resolution import ResolvedExecutionPlan


class ProviderModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilitySet(ProviderModel):
    features: frozenset[str]


class ProviderDescriptor(ProviderModel):
    id: str
    execution_profile: Literal["tier1", "tier2"]
    device: Literal["cpu", "gpu"]
    asynchronous: bool


class ResourceEstimate(ProviderModel):
    work_units: float
    memory_bytes: int


class JobHandle(ProviderModel):
    id: str
    provider_id: str
    plan_fingerprint: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    result: ResultGraph | None = None
    artifact_id: str | None = None
    error: str | None = None


class ExecutionProvider(Protocol):
    descriptor: ProviderDescriptor

    def validate(self, plan: ResolvedExecutionPlan) -> ValidationReport: ...
    def estimate(self, plan: ResolvedExecutionPlan) -> ResourceEstimate: ...
    def submit(self, plan: ResolvedExecutionPlan) -> JobHandle: ...
    def cancel(self, job_id: str) -> None: ...
    def capabilities(self) -> CapabilitySet: ...


class InProcessNumpyProvider:
    descriptor = ProviderDescriptor(id="in_process_numpy", execution_profile="tier1", device="cpu", asynchronous=False)

    def validate(self, plan: ResolvedExecutionPlan) -> ValidationReport:
        from .kernel import validate_experiment
        try:
            graph = ExperimentGraph.model_validate(dict(plan.experiment_snapshot))
        except Exception as exc:
            return ValidationReport(valid=False, errors=({"code": "invalid_snapshot", "message": str(exc)},))
        return validate_experiment(graph)

    def estimate(self, plan: ResolvedExecutionPlan) -> ResourceEstimate:
        return ResourceEstimate(work_units=plan.cost_estimate, memory_bytes=max(1, int(plan.cost_estimate)) * 16)

    def submit(self, plan: ResolvedExecutionPlan) -> JobHandle:
        job_id = str(uuid4())
        try:
            graph = ExperimentGraph.model_validate(dict(plan.experiment_snapshot))
            result = build_result_graph(run_experiment(graph))
            return JobHandle(id=job_id, provider_id=self.descriptor.id, plan_fingerprint=plan.fingerprint, status="succeeded", result=result)
        except Exception as exc:
            return JobHandle(id=job_id, provider_id=self.descriptor.id, plan_fingerprint=plan.fingerprint, status="failed", error=f"ExperimentGraph execution failed: {exc}")

    def cancel(self, job_id: str) -> None:
        raise ValueError("in-process synchronous jobs cannot be cancelled")

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(features=frozenset({"cpu.numpy", "sync.experiment"}))
