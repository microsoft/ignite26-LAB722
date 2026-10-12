import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import duckdb
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles

from data.pipeline.contracts import (
    Candidate, Condition, Contract, FIXTURE_WARNING, LIMITATIONS, Manifest, SafetyReport, Trial,
)
from data.pipeline.extract_public import DraftReport, DraftTrial
from data.pipeline.validate_dataset import read_original_records, validate_artifact, validate_auxiliary
from queries import records
from safety_feature import query_safety_reports
from trial_feature import query_trials

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("CALDOVA_DATA_DIR", ROOT / "data" / "artifacts" / "development"))
STATIC_DIR = Path(os.environ.get("CALDOVA_STATIC_DIR", ROOT / "src" / "research-portal" / "frontend" / "dist"))


class ResearchResponse(Contract):
    status: Literal["ready", "unavailable"]
    candidate: Candidate
    condition: Condition | None
    dataset_version: str
    trials: list[Trial | DraftTrial]
    safety_reports: list[SafetyReport | DraftReport]
    limitations: str
    fixture_warning: str | None


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = os.environ.get("CALDOVA_PREVIEW_STATE", "reference")
    if state not in {"starter", "reference"}:
        raise ValueError("CALDOVA_PREVIEW_STATE must be starter or reference.")
    app.state.preview_state = state
    app.state.manifest = validate_artifact(DATA_DIR / "data-manifest.json")
    original = (
        read_original_records(DATA_DIR, app.state.manifest)
        if app.state.manifest.public_extract is not None else None
    )
    app.state.original_trials = {item.trial_id: item for item in original.trials} if original else {}
    app.state.original_reports = {item.report_id: item for item in original.safety_reports} if original else {}
    if not (STATIC_DIR / "index.html").is_file():
        raise FileNotFoundError(f"Frontend build is missing from {STATIC_DIR}.")
    yield


app = FastAPI(title="Caldova research portal", lifespan=lifespan)


def connect():
    return duckdb.connect(
        str(DATA_DIR / app.state.manifest.database.path),
        read_only=True,
        config={"enable_external_access": False},
    )


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/") or request.url.path == "/health":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health():
    manifest: Manifest = app.state.manifest
    return {
        "status": "healthy",
        "dataset_version": manifest.dataset_version,
        "dataset_kind": manifest.dataset_kind,
        "preview_state": app.state.preview_state,
    }


@app.get("/api/metadata")
def metadata():
    manifest: Manifest = app.state.manifest
    with connect() as connection:
        candidates = records(
            connection,
            "SELECT candidate_id, name, research_area FROM candidates ORDER BY candidate_id",
            [],
        )
    return {
        "manifest": manifest.model_dump(mode="json"),
        "candidates": candidates,
        "preview_state": app.state.preview_state,
        "fixture_warning": FIXTURE_WARNING if manifest.dataset_kind == "synthetic-development" else None,
    }


@app.get("/api/research", response_model=ResearchResponse)
def research(
    candidate: str = Query(min_length=1, max_length=128),
    condition: Condition | None = None,
):
    manifest: Manifest = app.state.manifest
    with connect() as connection:
        candidates = records(
            connection,
            "SELECT candidate_id, name, research_area FROM candidates WHERE candidate_id = ?",
            [candidate],
        )
        if not candidates:
            raise HTTPException(status_code=404, detail="The requested research candidate does not exist.")
        trials = []
        safety_reports = []
        if app.state.preview_state == "reference":
            trials = query_trials(connection, candidate, condition)
            safety_reports = query_safety_reports(connection, candidate)
    trial_records = []
    report_records = []
    for trial in trials:
        if manifest.public_extract is None:
            trial_records.append(Trial.model_validate(trial))
        else:
            original = app.state.original_trials.get(trial["trial_id"])
            if original is None:
                raise ValueError("The query returned a trial outside the frozen public source records.")
            trial_records.append(DraftTrial.model_validate({
                **trial, "source_conditions": original.source_conditions,
                "source_interventions": original.source_interventions,
            }))
    for report in safety_reports:
        if manifest.public_extract is None:
            report_records.append(SafetyReport.model_validate(report))
        else:
            original = app.state.original_reports.get(report["report_id"])
            if original is None:
                raise ValueError("The query returned a report outside the frozen public source records.")
            report_records.append(DraftReport.model_validate({
                **report, "source_drugs": original.source_drugs,
                "original_reaction_terms": original.original_reaction_terms,
            }))
    return ResearchResponse(
        status="ready" if app.state.preview_state == "reference" else "unavailable",
        candidate=Candidate.model_validate(candidates[0]),
        condition=condition,
        dataset_version=manifest.dataset_version,
        trials=trial_records,
        safety_reports=report_records,
        limitations=LIMITATIONS,
        fixture_warning=FIXTURE_WARNING if manifest.dataset_kind == "synthetic-development" else None,
    )


@app.get("/api/source-records")
def source_records():
    manifest: Manifest = app.state.manifest
    if manifest.source_records is None or manifest.public_extract is None:
        raise HTTPException(status_code=404, detail="This dataset has no frozen original-source projections.")
    path = validate_auxiliary(DATA_DIR, manifest.source_records)
    return {
        "dataset_version": manifest.dataset_version,
        "source_use_decision": manifest.public_extract.source_use.model_dump(mode="json"),
        "note": "Original extraction-time projections; their historical draft flags are not deployment approval.",
        "original_extraction": json.loads(path.read_text(encoding="utf-8")),
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True, check_dir=False), name="portal")
