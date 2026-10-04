import hashlib
from threading import RLock

from .models import Artifact, JobEvent, JobRecord


class JobStore:
    def __init__(self):
        self._lock = RLock()
        self._jobs = {}
        self._fingerprints = {}  # (provider_id, plan_fingerprint) -> job_id
        self._events = {}
        self._artifacts = {}

    def get_by_fingerprint(self, provider_id: str, plan_fingerprint: str) -> JobRecord | None:
        with self._lock:
            job_id = self._fingerprints.get((provider_id, plan_fingerprint))
            if job_id is not None:
                return self._jobs.get(job_id)
            return None

    def reserve_and_create(self, job: JobRecord, max_concurrent: int | None = None) -> tuple[JobRecord, bool]:
        """
        Atomically reserve and create a job by (provider_id, plan_fingerprint).
        Returns (job_record, created_new: bool).
        If an identical job already exists, returns the existing job and False.
        """
        with self._lock:
            key = (job.provider_id, job.plan_fingerprint)
            existing_id = self._fingerprints.get(key)
            if existing_id is not None:
                return self._jobs[existing_id], False

            if max_concurrent is not None:
                active_count = sum(1 for j in self._jobs.values() if j.status in {"queued", "running"})
                if active_count >= max_concurrent:
                    raise RuntimeError(f"lease limit of {max_concurrent} concurrent jobs reached")

            if job.id in self._jobs:
                raise ValueError(f"duplicate job id {job.id}")

            self._jobs[job.id] = job
            self._fingerprints[key] = job.id
            self._events[job.id] = []
            self.append(job.id, "queued")
            return job, True

    def create(self, job: JobRecord) -> None:
        self.reserve_and_create(job, max_concurrent=None)

    def get_job(self, job_id: str) -> JobRecord:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError:
                raise KeyError(f"unknown job {job_id}") from None

    def transition(self, job_id: str, status: str, *, artifact_id=None, error=None) -> JobRecord:
        with self._lock:
            current = self.get_job(job_id)
            allowed = {
                "queued": {"running", "cancelled"},
                "running": {"succeeded", "failed", "cancelled"},
                "succeeded": set(), "failed": set(), "cancelled": set(),
            }
            if status not in allowed[current.status]:
                raise ValueError(f"invalid job transition {current.status} -> {status}")
            updated = current.model_copy(update={"status": status, "artifact_id": artifact_id, "error": error})
            self._jobs[job_id] = updated
            self.append(job_id, status, error or "")
            return updated

    def append(self, job_id: str, kind: str, message: str = "") -> JobEvent:
        events = self._events[job_id]
        event = JobEvent(sequence=len(events) + 1, job_id=job_id, kind=kind, message=message)
        events.append(event)
        return event

    def events(self, job_id: str) -> tuple[JobEvent, ...]:
        with self._lock:
            self.get_job(job_id)
            return tuple(self._events[job_id])

    def put_artifact(self, content: bytes, media_type: str) -> Artifact:
        digest = hashlib.sha256(content).hexdigest()
        artifact = Artifact(sha256=digest, media_type=media_type, content=content)
        with self._lock:
            self._artifacts[digest] = artifact
        return artifact

    def get_artifact(self, artifact_id: str) -> Artifact:
        with self._lock:
            try:
                return self._artifacts[artifact_id]
            except KeyError:
                raise KeyError(f"unknown artifact {artifact_id}") from None
