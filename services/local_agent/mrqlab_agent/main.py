from fastapi import FastAPI, HTTPException, Response, status

from mrqlab_experiment import plan_experiment

from .models import JobSubmitRequest
from .providers import CpuExecutionProvider, ProviderRegistry
from .store import JobStore

app = FastAPI(title="MRQLab Local Agent")
store = JobStore()
cpu_provider = CpuExecutionProvider(store)
providers = ProviderRegistry((cpu_provider,))


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
def create_job(request: JobSubmitRequest):
    try:
        provider = providers.get(request.provider_id)
        plan = plan_experiment(request.experiment)
        report = provider.validate(plan)
        if not report.valid:
            raise ValueError(report.errors[0].message)
        return provider.submit(plan)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    try:
        job = store.get_job(job_id)
        providers.get(job.provider_id).cancel(job_id)
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/jobs/{job_id}/events")
def job_events(job_id: str):
    try:
        return {"events": store.events(job_id)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    try:
        artifact = store.get_artifact(artifact_id)
        return Response(content=artifact.content, media_type=artifact.media_type)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
