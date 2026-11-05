from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data.pipeline.contracts import Manifest

Role = Literal["clinical-trials", "drug-safety", "quality-governance"]
ROLES: tuple[Role, ...] = ("clinical-trials", "drug-safety", "quality-governance")
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(min_length=1, max_length=4000)]
REQUIRED_CHECKS = frozenset({
    "worker-schema", "trial-fixtures", "safety-normalization", "citations",
    "responsible-use", "application-acceptance", "egress-allowed", "egress-denied",
})
APPROVED_TASKS: dict[Role, str] = {
    "clinical-trials": (
        "Implement query_trials(connection, candidate, condition) in "
        "src/research-portal/backend/trial_feature.py using parameterized cached trial "
        "queries and preserving identifiers and citations."
    ),
    "drug-safety": (
        "Implement query_safety_reports(connection, candidate) in "
        "src/research-portal/backend/safety_feature.py using normalized cached reports; "
        "do not link reports to trials or change reports when trial conditions change."
    ),
    "quality-governance": (
        "Validate the integrated application, immutable data, citations, responsible-use "
        "statements, and egress evidence; report blockers without approving release."
    ),
}
ROLE_CHECKS: dict[Role, frozenset[str]] = {
    "clinical-trials": frozenset({"trial-fixtures", "citations"}),
    "drug-safety": frozenset({"safety-normalization", "citations", "responsible-use"}),
    "quality-governance": frozenset({
        "worker-schema", "application-acceptance", "responsible-use", "egress-allowed", "egress-denied",
    }),
}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Assignment(Contract):
    role: Role
    task: Text
    acceptance_criteria: list[Text] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def require_software_delivery_scope(self) -> Self:
        if self.task != APPROVED_TASKS[self.role] or \
                set(self.acceptance_criteria) != ROLE_CHECKS[self.role] or \
                len(self.acceptance_criteria) != len(ROLE_CHECKS[self.role]):
            raise ValueError("Assignments must preserve the approved software task and deterministic checks.")
        return self


class ImplementationPlan(Contract):
    schema_version: Literal["1.0"]
    run_id: UUID
    dataset_version: str = Field(min_length=1, max_length=128)
    logical_sha256: Sha256
    assignments: list[Assignment] = Field(min_length=3, max_length=3)
    release_requires_human_approval: Literal[True]
    limitations: Text

    @model_validator(mode="after")
    def require_all_workers(self) -> Self:
        if {assignment.role for assignment in self.assignments} != set(ROLES):
            raise ValueError("The plan must assign each specialist exactly once.")
        return self


class SandboxBinding(Contract):
    role: Role
    sandbox_id: UUID
    snapshot_id: UUID
    workspace: Literal["/opt/caldova-lab"] = "/opt/caldova-lab"


class WorkerResult(Contract):
    schema_version: Literal["1.0"]
    run_id: UUID
    role: Role
    sandbox_id: UUID
    dataset_version: str = Field(min_length=1, max_length=128)
    logical_sha256: Sha256
    summary: Text = Field(
        description="Completed work, review findings and non-blocking notes or expected later-stage caveats."
    )
    source_record_ids: list[str] = Field(max_length=100)
    blockers: list[Text] = Field(
        max_length=20,
        description=(
            "Actual unresolved software, data or evidence failures only. Return an empty array [] "
            "when there are none. Never include a 'no blockers' sentence, a successful check, or "
            "the expected later worker-schema/human-approval steps here; put those notes in summary. "
            "Every non-empty entry stops acceptance."
        ),
    )


class CheckEvidence(Contract):
    run_id: UUID
    name: str = Field(min_length=1, max_length=128)
    sandbox_id: UUID
    exit_code: int = Field(strict=True)
    passed: bool = Field(strict=True)
    output_sha256: Sha256


class HumanApproval(Contract):
    run_id: UUID
    logical_sha256: Sha256
    image_digest: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    approved_by: Text


class ReleaseDecision(Contract):
    run_id: UUID
    status: Literal["blocked", "development-preview-approved", "reviewed-release-approved"]
    reasons: list[Text]
    image_digest: str | None


def decide_release(
    *,
    run_id: UUID,
    manifest: Manifest,
    validation_sandbox_id: UUID,
    bindings: list[SandboxBinding],
    workers: list[WorkerResult],
    checks: list[CheckEvidence],
    approval: HumanApproval | None,
    image_digest: str,
    reviewed_release: bool,
) -> ReleaseDecision:
    """Evaluate trusted control-plane evidence, never a model's approval claim."""
    reasons = []
    assigned = {binding.role: binding for binding in bindings}
    if len(bindings) != 3 or set(assigned) != set(ROLES):
        reasons.append("Each specialist must have exactly one Sandbox binding.")
    if len({binding.sandbox_id for binding in bindings}) != 3:
        reasons.append("Specialists must execute in three distinct Sandboxes.")
    if validation_sandbox_id in {binding.sandbox_id for binding in bindings}:
        reasons.append("Integrated acceptance must run separately from model-controlled worker Sandboxes.")
    if len({binding.snapshot_id for binding in bindings}) != 1:
        reasons.append("All workers must inherit the same prepared baseline snapshot.")
    if len(workers) != 3 or {worker.role for worker in workers} != set(ROLES):
        reasons.append("Exactly one validated result is required from each specialist.")
    for worker in workers:
        binding = assigned.get(worker.role)
        if binding is None or binding.sandbox_id != worker.sandbox_id:
            reasons.append(f"{worker.role}: the result does not match its assigned Sandbox.")
        if worker.run_id != run_id or worker.dataset_version != manifest.dataset_version or \
                worker.logical_sha256 != manifest.logical_sha256:
            reasons.append(f"{worker.role}: run or dataset identity does not match.")
        if worker.blockers:
            reasons.append(f"{worker.role}: unresolved worker blockers.")
    names = [check.name for check in checks]
    if len(set(names)) != len(names):
        reasons.append("Duplicate checks cannot substitute for independent release evidence.")
    if not REQUIRED_CHECKS.issubset(names):
        reasons.append("Required deterministic release checks are missing.")
    permitted_sandboxes = {binding.sandbox_id for binding in bindings} | {validation_sandbox_id}
    for check in checks:
        if check.run_id != run_id or check.sandbox_id not in permitted_sandboxes:
            reasons.append(f"{check.name}: evidence belongs to another run or Sandbox.")
        if check.exit_code != 0 or not check.passed:
            reasons.append(f"{check.name}: deterministic validation failed.")
        if check.name in {"trial-fixtures", "safety-normalization", "citations",
                          "responsible-use", "application-acceptance"} and \
                check.sandbox_id != validation_sandbox_id:
            reasons.append(f"{check.name}: the integrated candidate was not independently validated.")
    if approval is None or approval.run_id != run_id or \
            approval.logical_sha256 != manifest.logical_sha256 or \
            approval.image_digest != image_digest:
        reasons.append("Human approval must bind the exact run, dataset, and immutable image.")
    if reviewed_release and (manifest.dataset_kind != "reviewed-public" or manifest.review is None):
        reasons.append("An attendee release requires explicitly reviewed public data.")
    if reviewed_release and not manifest.has_committed_pipeline:
        reasons.append("An attendee release requires a committed pipeline, not a local source snapshot.")
    return ReleaseDecision(
        run_id=run_id,
        status="blocked" if reasons else (
            "reviewed-release-approved" if reviewed_release else "development-preview-approved"
        ),
        reasons=reasons,
        image_digest=None if reasons else image_digest,
    )
