import json
from concurrent.futures import Future, ThreadPoolExecutor
from uuid import uuid4

from mrqlab_experiment.execution_provider import (
    CapabilitySet, JobHandle, ProviderDescriptor, ResourceEstimate,
)
from mrqlab_experiment.kernel import ValidationReport, run_experiment, validate_experiment
from mrqlab_experiment.models import ExperimentGraph
from mrqlab_experiment.observations import build_result_graph

from .models import JobRecord
from .store import JobStore


class CpuExecutionProvider:
    descriptor = ProviderDescriptor(id="local_cpu_numpy", execution_profile="tier2", device="cpu", asynchronous=True)

    def __init__(self, store: JobStore, max_workers: int = 1):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=max_workers) if max_workers > 0 else None
        self.futures: dict[str, Future] = {}

    def validate(self, plan) -> ValidationReport:
        return validate_experiment(ExperimentGraph.model_validate(dict(plan.experiment_snapshot)))

    def estimate(self, plan) -> ResourceEstimate:
        return ResourceEstimate(work_units=plan.cost_estimate, memory_bytes=max(1, int(plan.cost_estimate)) * 16)

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(features=frozenset({"cpu.numpy", "jobs", "cancel", "artifacts"}))

    def submit(self, plan) -> JobHandle:
        job_id = str(uuid4())
        self.store.create(JobRecord(id=job_id, provider_id=self.descriptor.id, plan_fingerprint=plan.fingerprint, status="queued"))
        if self.executor is not None:
            self.futures[job_id] = self.executor.submit(self._run, job_id, plan)
        return JobHandle(id=job_id, provider_id=self.descriptor.id, plan_fingerprint=plan.fingerprint, status="queued")

    def _run(self, job_id, plan):
        if self.store.get_job(job_id).status == "cancelled":
            return
        self.store.transition(job_id, "running")
        try:
            graph = ExperimentGraph.model_validate(dict(plan.experiment_snapshot))
            result = build_result_graph(run_experiment(graph))
            content = result.model_dump_json().encode()
            artifact = self.store.put_artifact(content, "application/vnd.mrqlab.result+json")
            self.store.append(job_id, "artifact", artifact.sha256)
            self.store.transition(job_id, "succeeded", artifact_id=artifact.sha256)
        except Exception as exc:
            self.store.transition(job_id, "failed", error=str(exc))

    def cancel(self, job_id: str) -> None:
        current = self.store.get_job(job_id)
        if current.status == "queued":
            self.store.transition(job_id, "cancelled")
            future = self.futures.get(job_id)
            if future is not None:
                future.cancel()
            return
        if current.status == "running":
            raise ValueError("running NumPy jobs are not preemptible; cooperative cancellation is a later provider capability")
        raise ValueError(f"cannot cancel job in state {current.status}")

    def shutdown(self):
        if self.executor is not None:
            self.executor.shutdown(wait=True)


from typing import Protocol


class GpuBackend(Protocol):
    def execute(self, plan): ...


class GpuExecutionProvider(CpuExecutionProvider):
    descriptor = ProviderDescriptor(id="local_gpu", execution_profile="tier2", device="gpu", asynchronous=True)

    def __init__(self, store: JobStore, backend: GpuBackend, max_workers: int = 1):
        super().__init__(store, max_workers=max_workers)
        self.backend = backend

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(features=frozenset({"gpu.batch", "jobs", "cancel", "artifacts"}))

    def _run(self, job_id, plan):
        if self.store.get_job(job_id).status == "cancelled":
            return
        self.store.transition(job_id, "running")
        try:
            result = self.backend.execute(plan)
            content = result.model_dump_json().encode()
            artifact = self.store.put_artifact(content, "application/vnd.mrqlab.result+json")
            self.store.append(job_id, "artifact", artifact.sha256)
            self.store.transition(job_id, "succeeded", artifact_id=artifact.sha256)
        except Exception as exc:
            self.store.transition(job_id, "failed", error=str(exc))


class ProviderRegistry:
    def __init__(self, providers=()):
        self._providers = {provider.descriptor.id: provider for provider in providers}

    def register(self, provider) -> None:
        provider_id = provider.descriptor.id
        if provider_id in self._providers:
            raise ValueError(f"duplicate provider {provider_id!r}")
        self._providers[provider_id] = provider

    def get(self, provider_id: str):
        try:
            return self._providers[provider_id]
        except KeyError:
            raise KeyError(f"provider {provider_id!r} is unavailable") from None

    def descriptors(self):
        return tuple(provider.descriptor for provider in self._providers.values())
