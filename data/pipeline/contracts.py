from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
DatasetKind = Literal["synthetic-development", "reviewed-public"]
Condition = Literal["obesity", "type-2-diabetes"]

LIMITATIONS = (
    "Adverse-event reports do not establish causation, incidence rates, or comparative "
    "safety. This lab does not provide treatment recommendations or medical advice."
)
FIXTURE_WARNING = (
    "All trials, candidates, and safety reports in this development dataset are "
    "invented test fixtures. They are not clinical evidence."
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Review(Contract):
    approved_by: Text
    approved_at: datetime


class SourceUseApproval(Review):
    schema_version: Literal["1.0"] = "1.0"
    scope: Literal["project-owner-selected-public-lab-use"]
    draft_sha256: Sha256
    draft_provenance_sha256: Sha256
    instruction: Text
    expert_audit_performed: Literal[False] = False
    publication_authorized: Literal[False] = False
    live_replacement_authorized: Literal[False] = False
    attendee_release_approved: Literal[False] = False

    @field_validator("approved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("The source-use decision requires an explicit time zone.")
        return value


class PublicExtract(Contract):
    source_use: SourceUseApproval
    mapping_version: Literal["conservative-exact-generics-v1"]
    coverage_notes: list[Text] = Field(min_length=1)
    trial_bucket_counts: dict[str, Annotated[int, Field(ge=0, le=10, strict=True)]]
    report_candidate_counts: dict[str, Annotated[int, Field(ge=0, le=10, strict=True)]]
    source_quality_counts: dict[str, Annotated[int, Field(ge=0, strict=True)]]


class Source(Contract):
    source_id: Identifier
    name: Text
    url: HttpUrl | None = None
    release: Text
    retrieved_at: datetime | None = None
    attribution: Text
    license_notes: Text

    @field_validator("url")
    @classmethod
    def require_https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and (value.scheme != "https" or value.username):
            raise ValueError("Source URLs must use HTTPS without credentials.")
        return value


class Candidate(Contract):
    candidate_id: Identifier
    name: Text
    research_area: Text


class Evidence(Contract):
    source_id: Identifier
    source_record_id: Identifier
    source_url: HttpUrl | None = None

    @field_validator("source_url")
    @classmethod
    def require_https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and (value.scheme != "https" or value.username):
            raise ValueError("Evidence URLs must use HTTPS without credentials.")
        return value


class Trial(Evidence):
    trial_id: Identifier
    title: Text
    phase: Text
    status: Text
    conditions: list[Condition] = Field(min_length=1)
    candidate_ids: list[Identifier] = Field(min_length=1)


class SafetyReport(Evidence):
    report_id: Identifier
    version: int = Field(ge=1, strict=True)
    candidate_ids: list[Identifier] = Field(min_length=1)
    reaction_terms: list[Text] = Field(min_length=1)


class DatasetInput(Contract):
    schema_version: Literal["1.0"]
    dataset_version: Identifier
    dataset_kind: DatasetKind
    review: Review | None = None
    public_extract: PublicExtract | None = None
    sources: list[Source] = Field(min_length=1)
    candidates: list[Candidate] = Field(min_length=1)
    trials: list[Trial] = Field(min_length=1)
    safety_reports: list[SafetyReport] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        candidate_ids = {candidate.candidate_id for candidate in self.candidates}
        source_ids = {source.source_id for source in self.sources}
        if len(candidate_ids) != len(self.candidates) or len(source_ids) != len(self.sources):
            raise ValueError("Candidate and source IDs must be unique.")
        if len({trial.trial_id for trial in self.trials}) != len(self.trials):
            raise ValueError("Trial IDs must be unique.")
        for record in [*self.trials, *self.safety_reports]:
            if record.source_id not in source_ids:
                raise ValueError(f"Unknown source for record {record.source_record_id}.")
            if not set(record.candidate_ids).issubset(candidate_ids):
                raise ValueError(f"Unknown candidate for record {record.source_record_id}.")
        if self.dataset_kind == "reviewed-public":
            if self.review is None:
                raise ValueError("A public dataset requires a recorded source review.")
            if any(source.url is None or source.retrieved_at is None for source in self.sources):
                raise ValueError("Public sources require fixed URLs and retrieval dates.")
            if any(record.source_url is None for record in [*self.trials, *self.safety_reports]):
                raise ValueError("Public evidence requires a source URL for every record.")
        elif self.review is not None:
            raise ValueError("Synthetic development fixtures cannot claim public-data approval.")
        if self.public_extract is not None:
            approval = self.public_extract.source_use
            if self.dataset_kind != "reviewed-public" or self.review != Review(
                approved_by=approval.approved_by, approved_at=approval.approved_at,
            ):
                raise ValueError("The public extract must match its recorded source-use decision.")
        return self


class Artifact(Contract):
    path: Text
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    bytes: int = Field(gt=0, le=64 * 1024 * 1024)

    @field_validator("path")
    @classmethod
    def require_basename(cls, value: str) -> str:
        if "\\" in value or PurePosixPath(value).name != value or not value.endswith(".duckdb"):
            raise ValueError("The database path must be a DuckDB filename, not a path or URL.")
        return value


class AuxiliaryArtifact(Contract):
    path: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.(json|zip)$")]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    bytes: int = Field(gt=0, le=64 * 1024 * 1024)

    @field_validator("path")
    @classmethod
    def require_basename(cls, value: str) -> str:
        if "\\" in value or PurePosixPath(value).name != value or not value.endswith((".json", ".zip")):
            raise ValueError("An auxiliary artifact must be a JSON/ZIP filename, not a path or URL.")
        return value


class Manifest(Contract):
    schema_version: Literal["1.0"]
    dataset_version: Identifier
    dataset_kind: DatasetKind
    built_at: datetime
    pipeline_commit: Text
    logical_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    database: Artifact
    source_records: AuxiliaryArtifact | None = None
    pipeline_source: AuxiliaryArtifact | None = None
    public_extract: PublicExtract | None = None
    record_counts: dict[str, Annotated[int, Field(ge=0, strict=True)]]
    sources: list[Source] = Field(min_length=1)
    review: Review | None = None
    limitations: Literal[LIMITATIONS] = LIMITATIONS

    @model_validator(mode="after")
    def require_public_review(self) -> Self:
        if self.dataset_kind == "reviewed-public":
            if self.review is None:
                raise ValueError("A public manifest requires a recorded source review.")
            committed = len(self.pipeline_commit) == 40 and all(
                character in "0123456789abcdef" for character in self.pipeline_commit
            )
            frozen_working_tree = (
                self.pipeline_commit == "uncommitted-development"
                and self.pipeline_source is not None and self.pipeline_source.path.endswith(".zip")
                and self.public_extract is not None
            )
            if not committed and not frozen_working_tree:
                raise ValueError("Public artifacts require a full pipeline commit SHA or a frozen source ZIP.")
            if self.source_records is not None and not self.source_records.path.endswith(".json"):
                raise ValueError("Frozen original source records must be a JSON file.")
            if any(source.url is None or source.retrieved_at is None for source in self.sources):
                raise ValueError("Public manifests require source URLs and retrieval dates.")
        elif any(item is not None for item in (self.source_records, self.pipeline_source, self.public_extract)):
            raise ValueError("Synthetic artifacts cannot contain public-source attachments or approval.")
        if self.source_records is not None and self.public_extract is None:
            raise ValueError("Original public source records require their bound extraction metadata and decision.")
        if self.public_extract is not None:
            approval = self.public_extract.source_use
            if (
                self.review != Review(approved_by=approval.approved_by, approved_at=approval.approved_at)
                or self.source_records is None or self.pipeline_source is None
                or self.source_records.sha256 != approval.draft_sha256
            ):
                raise ValueError("The frozen public extract requires its exact source records, pipeline and decision.")
            if not self.pipeline_source.path.endswith(".zip"):
                raise ValueError("The frozen public pipeline must be a ZIP file.")
        return self

    @property
    def has_committed_pipeline(self) -> bool:
        return len(self.pipeline_commit) == 40 and all(
            character in "0123456789abcdef" for character in self.pipeline_commit
        )
