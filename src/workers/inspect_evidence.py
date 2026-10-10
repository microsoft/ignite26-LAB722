"""Inspect pinned workflow receipts without running candidate code or contacting Azure."""

import argparse
import html
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.workers.check_application import validate_url
from src.workers.frozen_contract import (
    PUBLIC_PURPOSE, SYNTHETIC_PURPOSE, canonical_hash, frozen_bytes, load_public_sources,
    manifest_identity, public_identity, timestamp,
)

spec = importlib.util.spec_from_file_location("caldova_candidate_inspection", ROOT / "src/developer-image/stage_candidate.py")
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
require = candidate.require


def inspect_evidence(*, result_path, result_sha256, descriptor_path, descriptor_sha256,
                     manifest_path, manifest_sha256, purpose, image_path=None, image_sha256=None,
                     approval_path=None, approval_sha256=None, startup_path=None, startup_sha256=None):
    for path, checksum in ((image_path, image_sha256), (approval_path, approval_sha256),
                           (startup_path, startup_sha256)):
        require((path is None) == (checksum is None), "Each optional receipt requires its separate SHA-256 pin.")
    require(image_path is not None or (approval_path is None and startup_path is None),
            "Approval and application observations require a pinned image descriptor.")
    result = candidate.read_json(result_path, 256 * 1024, result_sha256)
    descriptor = candidate.read_json(descriptor_path, expected_sha256=descriptor_sha256)
    manifest = candidate.read_json(manifest_path, 128 * 1024, manifest_sha256)
    candidate.check_manifest(manifest, purpose)
    identity = manifest_identity(manifest_path, manifest_sha256, purpose)
    require(descriptor.get("schema_version") == "1.0" and
            descriptor.get("dataset_version") == manifest["dataset_version"] and
            descriptor.get("dataset_kind") == manifest["dataset_kind"] and
            descriptor.get("acceptance_purpose", SYNTHETIC_PURPOSE) == purpose,
            "Baseline descriptor changed the dataset or development purpose.")
    frozen = descriptor["frozen_identity"]
    require(type(frozen) is dict and set(frozen) == {
        "database_sha256", "logical_sha256", "data_manifest_sha256", "baseline_manifest_sha256",
    } | (set(public_identity(manifest)) if purpose == PUBLIC_PURPOSE else set()),
        "Baseline frozen identity is incomplete.")
    for field, value in frozen.items():
        candidate.digest(value)
        if field != "baseline_manifest_sha256":
            require(identity[field] == value, "Baseline frozen identity differs from the pinned manifest.")
    require(descriptor["artifacts"] == {
        "manifest": "data-manifest.json", "baseline": "prepared-baseline.json", "bindings": "bindings.json",
    }, "Baseline artifact filenames changed.")
    baseline = candidate.read_json(
        descriptor_path.parent / "prepared-baseline.json",
        expected_sha256=frozen["baseline_manifest_sha256"],
    )
    require(baseline.get("schema_version") == "1.0" and
            baseline.get("source_revision") == descriptor["source_revision"] and
            baseline.get("editable_modules") == candidate.MODULES and
            all(baseline.get(field) == manifest[field] for field in ("dataset_kind", "dataset_version")) and
            baseline.get("database_sha256") == identity["database_sha256"] and
            baseline.get("data_manifest_sha256") == manifest_sha256,
            "Prepared baseline changed its source or frozen identity.")
    candidate.identifier(descriptor["source_revision"])
    frozen_bytes(manifest_path.parent, manifest["database"])
    if purpose == PUBLIC_PURPOSE:
        load_public_sources(manifest_path.parent, manifest)
        require(baseline.get("acceptance_purpose") == purpose and
                baseline.get("public_identity") == public_identity(manifest),
                "Prepared baseline changed its original-source/decision pins.")
    sources, workers, checks = candidate.check_result(result, result["plan"]["run_id"], descriptor, manifest)
    source_hashes = {path: candidate.sha256_bytes(content) for path, content in sources.items()}
    pins = {
        "result": result_sha256, "baseline_descriptor": descriptor_sha256,
        "manifest": manifest_sha256, "prepared_baseline": frozen["baseline_manifest_sha256"],
    }
    image = None
    if image_path is not None:
        image = candidate.read_json(image_path, expected_sha256=image_sha256)
        require(image.get("schema_version") == "1.0" and
                image.get("status") == "container-validated-unapproved-candidate" and
                all(image.get(field) == value for field, value in {
                    "run_id": result["plan"]["run_id"], "dataset_version": manifest["dataset_version"],
                    "dataset_kind": manifest["dataset_kind"], "logical_sha256": manifest["logical_sha256"],
                    "frozen_identity": frozen, "candidate_sources": source_hashes,
                    "database": manifest["database"], "result_sha256": result_sha256,
                    "baseline_descriptor_sha256": descriptor_sha256, "source_revision": descriptor["source_revision"],
                    "acceptance_purpose": purpose,
                }.items()), "Image descriptor is not bound to this accepted run, baseline, data and source.")
        require(all(image.get(field) is False for field in ("human_approval", "release_approved", "deployed")),
                "Historical build-time approval flags must remain false.")
        candidate.digest(image["provenance_sha256"])
        artifact = image["image"]
        require(type(artifact) is dict and
                isinstance(artifact.get("registry"), str) and
                re.fullmatch(r"[a-z0-9]{5,50}", artifact["registry"]) and
                artifact.get("repository") == "caldova/research-portal" and
                isinstance(artifact.get("digest"), str) and
                re.fullmatch(r"sha256:[0-9a-f]{64}", artifact["digest"]) and
                isinstance(artifact.get("acr_run_id"), str) and
                re.fullmatch(r"[A-Za-z0-9-]{1,128}", artifact["acr_run_id"]) and
                artifact.get("platform") == "linux/amd64" and artifact.get("target") == "candidate" and
                artifact.get("reference") ==
                f'{artifact["registry"]}.azurecr.io/caldova/research-portal@{artifact["digest"]}',
                "Image descriptor lacks its immutable published image/build identity.")
        candidate.uuid(artifact["subscription"])
        pattern, count = candidate.acceptance_selection(manifest, purpose)
        require(canonical_hash(image.get("validation")) == canonical_hash({
            "container_only": True, "frozen_artifact_unchanged": True,
            "original_research_tests": count if purpose == SYNTHETIC_PURPOSE else 0,
            "original_synthetic_tests_preserved": True,
            "public_research_tests": count if purpose == PUBLIC_PURPOSE else 0,
            "purpose": purpose, "test_pattern": pattern, "tests_required": count,
        }), "Image acceptance contract changed.")
        pins["image_descriptor"] = image_sha256

    approval = None
    if approval_path is not None:
        approval = candidate.read_json(approval_path, expected_sha256=approval_sha256)
        candidate.object_fields(approval, {"run_id", "logical_sha256", "image_digest", "approved_by"}, "human approval")
        require(approval["run_id"] == result["plan"]["run_id"] and
                approval["logical_sha256"] == identity["logical_sha256"] and
                approval["image_digest"] == image["image"]["digest"] and
                isinstance(approval["approved_by"], str) and 0 < len(approval["approved_by"].strip()) <= 4000,
                "Recorded human approval belongs to another run, dataset or image.")
        pins["human_approval"] = approval_sha256

    application = None
    if startup_path is not None:
        receipt = candidate.read_json(startup_path, expected_sha256=startup_sha256)
        timestamp(receipt["observed_at"])
        report = receipt["report"]
        app = report["application"]
        require(report.get("schema_version") == "1.0" and report.get("mode") == "Readiness" and
                all(report.get(field) is True for field in (
                    "infrastructure_ready", "application_ready", "application_manifest_verified", "frozen_data_verified",
                )) and report.get("data_ready") is False and report.get("attendee_ready") is False,
                "Startup receipt is not a verified development application observation.")
        require(type(app) is dict and app.get("schema_version") == "1.0" and
                app.get("status") == "pinned-development-application-ready" and
                canonical_hash(app.get("identity")) == canonical_hash(identity) and
                app.get("image") == image["image"]["reference"] and
                app.get("preview_state") == "reference" and
                all(app.get(field) is True for field in (
                    "local_frozen_artifacts_verified", "live_manifest_verified", "sample_state_verified",
                )) and all(app.get(field) is False for field in (
                    "attendee_ready", "release_approved", "full_functional_acceptance_rerun",
                )) and
                (purpose != PUBLIC_PURPOSE or app.get("live_original_sources_verified") is True),
                "Observed application differs from this image/data or overstates its checks.")
        url = validate_url(app["url"])
        outputs = report["outputs"]
        require(outputs.get("CALDOVA_APPLICATION_URL") == url and
                outputs.get("CALDOVA_APPLICATION_IMAGE") == image["image"]["reference"] and
                outputs.get("AZURE_SUBSCRIPTION_ID") == image["image"]["subscription"] and
                isinstance(outputs.get("AZURE_RESOURCE_GROUP"), str) and
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._()-]{0,89}", outputs["AZURE_RESOURCE_GROUP"]) and
                isinstance(outputs.get("CALDOVA_APPLICATION_NAME"), str) and
                re.fullmatch(r"[a-z][a-z0-9-]{0,30}[a-z0-9]", outputs["CALDOVA_APPLICATION_NAME"]) and
                app.get("resource_id") ==
                f'/subscriptions/{outputs["AZURE_SUBSCRIPTION_ID"]}/resourceGroups/'
                f'{outputs["AZURE_RESOURCE_GROUP"]}/providers/Microsoft.App/containerApps/'
                f'{outputs["CALDOVA_APPLICATION_NAME"]}',
                "Application observation changed its scoped resource or image outputs.")
        application = {
            "observed_at": receipt["observed_at"], "url": url,
            "resource_id": app["resource_id"], "image": app["image"], "preview_state": app["preview_state"],
            "freshness": "Recorded observation only; this inspector made no network request.",
        }
        pins["startup_receipt"] = startup_sha256

    return {
        "schema_version": "1.0", "status": "evidence-integrity-verified",
        "run_id": result["plan"]["run_id"], "dataset": identity,
        "pipeline_provenance": manifest["pipeline_commit"],
        "baseline": {
            "source_revision": descriptor["source_revision"], "snapshot_id": descriptor["snapshot_id"],
            "primary_id": descriptor["primary_id"], "mode": descriptor.get("mode"),
            "verification": "Pinned descriptor/prepared-file identities, not a new remote starter/policy check.",
        },
        "assignments": result["plan"]["assignments"], "workers": workers, "worker_blockers": 0,
        "checks": sorted(checks, key=lambda check: check["name"]),
        "candidate_sources": source_hashes, "image": image["image"] if image else None,
        "human_approval": approval, "application_observation": application, "receipt_sha256": pins,
        "limitations": manifest["limitations"],
        "missing_stages": [
            label for value, label in ((image, "Published-image descriptor"), (approval, "Human approval"),
                                      (application, "Recorded application observation")) if value is None
        ],
        "not_evidenced": [
            "GitHub issue identifier and Foundry session identifiers are not stored in this accepted-result contract.",
            "Detailed token/timing telemetry and an Azure Monitor correlation workbook are not supplied by these receipts.",
            "Output hashes bind recorded checks; raw execution logs are not reproduced or independently rehashed here.",
        ],
        "release_approved": False, "attendee_ready": False, "current_live_state_checked": False,
        "full_functional_acceptance_rerun": False,
        "interpretation": (
            "Checksum pins are caller-supplied trust anchors, not signatures. This viewer validates their "
            "integrity and cross-receipt identities only; it never authenticates an approver, executes candidate "
            "code, reruns tests, evaluates the release gate, publishes images or changes resources."
        ),
    }


def render_html(report):
    def text(value):
        return html.escape(str(value), quote=True)

    def table(title, headers, rows):
        return (
            f"<h2>{text(title)}</h2><div class=\"table-wrap\"><table><caption>{text(title)}</caption>"
            "<thead><tr>" + "".join(f"<th scope=\"col\">{text(header)}</th>" for header in headers) +
            "</tr></thead><tbody>" + "".join(
                "<tr>" + "".join(f"<td>{text(value)}</td>" for value in row) + "</tr>" for row in rows
            ) + "</tbody></table></div>"
        )

    body = table("Run and frozen baseline", ("Field", "Recorded value"), [
        ("Run ID", report["run_id"]), ("Dataset", report["dataset"]["dataset_version"]),
        ("Kind / purpose", f'{report["dataset"]["dataset_kind"]} / {report["dataset"]["acceptance_purpose"]}'),
        ("Pipeline provenance", report["pipeline_provenance"]),
        *report["baseline"].items(),
    ])
    body += table("Specialist assignments", ("Role", "Sandbox ID", "Source record IDs"), [
        (worker["role"], worker["sandbox_id"], ", ".join(worker["source_record_ids"]) or "None reported")
        for worker in sorted(report["workers"], key=lambda worker: worker["role"])
    ])
    body += table("Bounded software tasks", ("Role", "Task", "Acceptance criteria"), [
        (assignment["role"], assignment["task"], ", ".join(assignment["acceptance_criteria"]))
        for assignment in sorted(report["assignments"], key=lambda assignment: assignment["role"])
    ])
    body += table("Recorded deterministic checks", ("Check", "Passed", "Exit code", "Sandbox ID", "Output SHA-256"), [
        (check["name"], check["passed"], check["exit_code"], check["sandbox_id"], check["output_sha256"])
        for check in report["checks"]
    ])
    body += table("Accepted source hashes (code not executed)", ("Path", "SHA-256"), report["candidate_sources"].items())
    for title, value in (
        ("Published candidate", report["image"]), ("Separate human approval", report["human_approval"]),
        ("Recorded application observation", report["application_observation"]),
    ):
        body += table(title, ("Field", "Value"), value.items()) if value else f"<h2>{text(title)}</h2><p>Not supplied.</p>"
    body += table("Pinned receipt hashes", ("Receipt", "SHA-256"), report["receipt_sha256"].items())
    notes = [report["interpretation"], report["limitations"], *report["not_evidenced"]]
    if report["missing_stages"]:
        notes.append("Missing: " + ", ".join(report["missing_stages"]))
    body += "<h2>Limits of this evidence</h2>" + "".join(f"<p>{text(note)}</p>" for note in notes)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; '
        'base-uri \'none\'; form-action \'none\'">'
        '<title>Caldova recorded workflow evidence</title><style>'
        'body{font:16px/1.5 system-ui,sans-serif;margin:0;color:#17223b;background:#f6f8fc}'
        'main{max-width:1200px;margin:auto;padding:24px}h1,h2{line-height:1.2}'
        '.notice{padding:16px;border-left:5px solid #936200;background:#fff1ce}'
        'table{border-collapse:collapse;width:100%;background:white}caption{text-align:left;font-weight:600;padding:8px}'
        'th,td{text-align:left;vertical-align:top;border:1px solid #ced5e1;padding:10px;overflow-wrap:anywhere}'
        'th{background:#e8eef8}.table-wrap{overflow-x:auto}p{overflow-wrap:anywhere}'
        'a{color:#0645ad}.skip{display:block;padding:8px}footer{margin-top:24px}'
        '@media(max-width:600px){main{padding:12px}th,td{padding:6px;font-size:14px}}'
        '</style></head><body><a class="skip" href="#evidence">Skip to evidence</a><main>'
        '<h1>Caldova recorded workflow evidence</h1>'
        '<p class="notice"><strong>Evidence integrity verified, not release approval.</strong> '
        'Attendee readiness: false. Current live state checked: false. No tests or candidate code executed.</p>'
        f'<section id="evidence">{body}</section><footer>Offline receipt inspection; no external assets or telemetry workbook.</footer>'
        '</main></body></html>'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("result", "baseline-descriptor", "manifest"):
        parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
    for name in ("image-descriptor", "approval", "startup-receipt"):
        parser.add_argument("--" + name, type=Path)
        parser.add_argument("--" + name + "-sha256")
    parser.add_argument("--purpose", choices=(SYNTHETIC_PURPOSE, PUBLIC_PURPOSE), required=True)
    parser.add_argument("--format", choices=("json", "html"), default="json")
    args = parser.parse_args()
    report = inspect_evidence(
        result_path=args.result, result_sha256=args.result_sha256,
        descriptor_path=args.baseline_descriptor, descriptor_sha256=args.baseline_descriptor_sha256,
        manifest_path=args.manifest, manifest_sha256=args.manifest_sha256, purpose=args.purpose,
        image_path=args.image_descriptor, image_sha256=args.image_descriptor_sha256,
        approval_path=args.approval, approval_sha256=args.approval_sha256,
        startup_path=args.startup_receipt, startup_sha256=args.startup_receipt_sha256,
    )
    print(render_html(report) if args.format == "html" else json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
