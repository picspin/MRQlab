import time
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status

from mrqlab_experiment import plan_experiment

from .license import LeaseVerifier, require_entitlement
from .models import CapabilityResponse, JobSubmitRequest
from .providers import CpuExecutionProvider, ProviderRegistry
from .security import LocalSecurity
from .store import JobStore

app = FastAPI(title="MRQLab Local Agent")
store = JobStore()
cpu_provider = CpuExecutionProvider(store)
providers = ProviderRegistry((cpu_provider,))
local_security = LocalSecurity(frozenset({"https://app.mrqlab.local", "http://127.0.0.1:3000"}))
lease_verifier: LeaseVerifier | None = None


def require_local_security(request: Request, response: Response):
    local_security.verify(request, response)


def verify_lease(authorization: str = Header(default="")):
    if lease_verifier is None:
        raise HTTPException(503, "lease verifier is not configured")
    if not authorization.startswith("Lease "):
        raise HTTPException(401, "signed device lease is required")
    try:
        decision = lease_verifier.verify(
            authorization.removeprefix("Lease "),
            wall_time=time.time(), monotonic_time=time.monotonic(),
        )
        return decision
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc


@app.options("/{path:path}")
def preflight_handler(request: Request, path: str):
    resp = Response(status_code=204)
    local_security.handle_cors(request, resp)
    return resp


@app.post(
    "/jobs",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_local_security)],
)
def create_job(request: JobSubmitRequest, decision=Depends(verify_lease)):
    try:
        provider = providers.get(request.provider_id)
        # Check provider-specific entitlement (e.g. compute.gpu for local_gpu, compute.cpu for CPU)
        required_feature = "compute.gpu" if provider.descriptor.device == "gpu" else "compute.cpu"
        try:
            require_entitlement(decision, required_feature)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc

        # Check concurrency limits if defined in lease claims
        max_concurrent = decision.claims.limits.get("max_concurrent_jobs")
        if max_concurrent is not None:
            active_jobs = [j for j in store._jobs.values() if j.status in {"queued", "running"}]
            if len(active_jobs) >= max_concurrent:
                raise HTTPException(429, f"lease limit of {max_concurrent} concurrent jobs reached")

        plan = plan_experiment(request.experiment)
        report = provider.validate(plan)
        if not report.valid:
            raise ValueError(report.errors[0].message)
        return provider.submit(plan)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/jobs/{job_id}", dependencies=[Depends(require_local_security)])
def get_job(job_id: str):
    try:
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post(
    "/jobs/{job_id}/cancel",
    dependencies=[Depends(require_local_security)],
)
def cancel_job(job_id: str, decision=Depends(verify_lease)):
    try:
        require_entitlement(decision, "jobs.cancel")
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    try:
        job = store.get_job(job_id)
        providers.get(job.provider_id).cancel(job_id)
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/jobs/{job_id}/events", dependencies=[Depends(require_local_security)])
def job_events(job_id: str):
    try:
        return {"events": store.events(job_id)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/artifacts/{artifact_id}", dependencies=[Depends(require_local_security)])
def get_artifact(artifact_id: str):
    try:
        artifact = store.get_artifact(artifact_id)
        return Response(content=artifact.content, media_type=artifact.media_type)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/v1/capabilities", dependencies=[Depends(require_local_security)])
def capabilities():
    descriptors = providers.descriptors()
    return CapabilityResponse(
        features={feature: True for provider in (cpu_provider,) for feature in provider.capabilities().features},
        workers=tuple({"id": item.id, "device": item.device, "status": "ready"} for item in descriptors),
        license={"state": "configured" if lease_verifier is not None else "unconfigured", "offline": False, "expires_at": None},
    )
