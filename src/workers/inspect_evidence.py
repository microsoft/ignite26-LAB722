"""Inspect pinned workflow receipts without running candidate code or contacting Azure."""

import argparse
import base64
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
    logo = base64.b64encode(
        (ROOT / "src/research-portal/frontend/src/assets/caldova-logo.svg").read_bytes()
    ).decode("ascii")

    def text(value):
        return html.escape(str(value), quote=True)

    def table(title, headers, rows, anchor):
        wide = ' class="wide-table"' if len(headers) > 2 else ""
        return (
            f'<section class="evidence-section" id="{anchor}" aria-labelledby="{anchor}-heading">'
            f'<h2 id="{anchor}-heading">{text(title)}</h2>'
            f'<div class="table-wrap" role="region" aria-label="{text(title)} table" tabindex="0">'
            f"<table{wide}><caption>{text(title)}</caption>"
            "<thead><tr>" + "".join(f"<th scope=\"col\">{text(header)}</th>" for header in headers) +
            "</tr></thead><tbody>" + "".join(
                "<tr>" + "".join(f"<td>{text(value)}</td>" for value in row) + "</tr>" for row in rows
            ) + "</tbody></table></div></section>"
        )

    body = table("Run and frozen baseline", ("Field", "Recorded value"), [
        ("Run ID", report["run_id"]), ("Dataset", report["dataset"]["dataset_version"]),
        ("Kind / purpose", f'{report["dataset"]["dataset_kind"]} / {report["dataset"]["acceptance_purpose"]}'),
        ("Pipeline provenance", report["pipeline_provenance"]),
        *report["baseline"].items(),
    ], "run")
    body += table("Specialist assignments", ("Role", "Sandbox ID", "Source record IDs"), [
        (worker["role"], worker["sandbox_id"], ", ".join(worker["source_record_ids"]) or "None reported")
        for worker in sorted(report["workers"], key=lambda worker: worker["role"])
    ], "specialists")
    body += table("Bounded software tasks", ("Role", "Task", "Acceptance criteria"), [
        (assignment["role"], assignment["task"], ", ".join(assignment["acceptance_criteria"]))
        for assignment in sorted(report["assignments"], key=lambda assignment: assignment["role"])
    ], "tasks")
    body += table("Recorded deterministic checks", ("Check", "Passed", "Exit code", "Sandbox ID", "Output SHA-256"), [
        (check["name"], check["passed"], check["exit_code"], check["sandbox_id"], check["output_sha256"])
        for check in report["checks"]
    ], "checks")
    body += table("Accepted source hashes (code not executed)", ("Path", "SHA-256"),
                  report["candidate_sources"].items(), "sources")
    for title, value, anchor in (
        ("Published candidate", report["image"], "image"),
        ("Separate human approval", report["human_approval"], "approval"),
        ("Recorded application observation", report["application_observation"], "observation"),
    ):
        body += table(title, ("Field", "Value"), value.items(), anchor) if value else (
            f'<section class="evidence-section" id="{anchor}" aria-labelledby="{anchor}-heading">'
            f'<h2 id="{anchor}-heading">{text(title)}</h2><p class="empty-state">Not supplied.</p></section>'
        )
    body += table("Pinned receipt hashes", ("Receipt", "SHA-256"), report["receipt_sha256"].items(), "receipts")
    notes = [report["interpretation"], report["limitations"], *report["not_evidenced"]]
    if report["missing_stages"]:
        notes.append("Missing: " + ", ".join(report["missing_stages"]))
    body += (
        '<section class="evidence-section limits" id="limits" aria-labelledby="limits-heading">'
        '<h2 id="limits-heading">Limits of this evidence</h2>' +
        "".join(f"<p>{text(note)}</p>" for note in notes) + "</section>"
    )
    navigation = "".join(
        f'<a href="#{anchor}"><span class="nav-index" aria-hidden="true">{index:02}</span>{label}</a>'
        for index, (anchor, label) in enumerate((
            ("run", "Run overview"), ("specialists", "Specialists"), ("tasks", "Software tasks"),
            ("checks", "Recorded checks"), ("sources", "Accepted sources"), ("image", "Published image"),
            ("approval", "Human approval"), ("observation", "App observation"),
            ("receipts", "Receipt hashes"), ("limits", "Evidence limits"),
        ), start=1)
    )
    style = """/*!
Adapted from Plus Admin Free by BootstrapDash, revision
af87c16d3e861d40726603c73266f7082ceb1398 (demo_1 palette and light dashboard layout).
https://github.com/BootstrapDash/PlusAdmin-Free-Bootstrap-Admin-Template

MIT License

Copyright (c) 2020 BootstrapDash

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
:root{font-family:"Segoe UI",system-ui,sans-serif;color:#313131;background:#f8f9fb;line-height:1.5;--primary:#0033c4;--muted:#606b80;--border:#e8ebf1;--sidebar:236px}
*{box-sizing:border-box}body{margin:0}a{color:var(--primary);text-underline-offset:3px}
:focus-visible{outline:3px solid var(--primary);outline-offset:4px}[id]{scroll-margin-top:92px}
.skip{position:absolute;top:-80px;left:20px;padding:12px 18px;background:white;z-index:100}.skip:focus{top:8px}
.dashboard{display:grid;grid-template-columns:var(--sidebar) minmax(0,1fr);min-height:100vh}
.topbar{grid-column:1/-1;position:sticky;top:0;z-index:10;min-height:76px;display:flex;align-items:center;gap:24px;background:white;border-bottom:1px solid var(--border);padding-right:32px}
.brand{display:flex;align-items:center;min-width:var(--sidebar);padding:14px 22px;border-right:1px solid var(--border);text-decoration:none}
.brand-logo{display:block;width:190px;height:auto}
.header-context{font-size:13px;font-weight:600}.lab-label{margin-left:auto;color:var(--primary);font-size:12px;font-weight:700}.lab-label span{display:block;font-size:11px;color:var(--muted);font-weight:400}
.sidebar{background:white;border-right:1px solid var(--border);position:sticky;top:76px;align-self:start;height:calc(100vh - 76px);overflow-y:auto;padding:28px 16px}
.workspace-identity{padding:0 14px 24px;font-size:12px;font-weight:650}.workspace-identity span{display:block;color:var(--muted);font-size:11px;font-weight:400;margin-top:4px}
.nav-caption{text-transform:uppercase;letter-spacing:.1em;font-size:10px;color:var(--muted);padding:0 14px;margin:0 0 12px;font-weight:600}
nav{display:grid;gap:4px}nav a{display:flex;align-items:center;gap:12px;color:#3e4b5b;text-decoration:none;font-size:12px;border-radius:5px;padding:11px 12px}
nav a:hover,nav a:focus-visible{background:#edf2ff;color:var(--primary)}nav a:first-child{background:#1a55e3;color:white}
.nav-index{font-size:10px;opacity:.85}.sidebar-note{border-top:1px solid var(--border);padding:18px 12px 0;margin-top:24px;font-size:11px;color:var(--muted)}
.content{min-width:0}main{max-width:1500px;margin:auto;padding:32px}h1{font-size:28px;letter-spacing:-.03em;line-height:1.25;margin:0 0 10px;color:#232b3e}h2{font-size:17px;line-height:1.4;margin:0 0 18px}
p{overflow-wrap:anywhere}.eyebrow{text-transform:uppercase;letter-spacing:.11em;font-size:10px;font-weight:700;color:var(--muted);margin:0 0 7px}.intro{color:var(--muted);font-size:13px;margin:0}
.page-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:24px}.badge{font-size:11px;background:white;border:1px solid var(--border);padding:8px 12px;border-radius:4px;white-space:nowrap;color:#3e4b5b}
.notice{padding:14px 18px;border:1px solid #f0e2bd;border-left:3px solid #b17a15;border-radius:4px;background:#fff8e9;color:#76561d;font-size:12px;margin:0 0 22px}.notice strong{display:block;margin-bottom:4px}
.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-bottom:24px}.metric{background:white;border:1px solid var(--border);border-radius:5px;padding:22px;position:relative}
.metric>span,.metric small{display:block;font-size:11px;color:var(--muted)}.metric>span{font-weight:600;margin-bottom:8px}.metric strong{font-size:32px;font-weight:650;color:#242d45;line-height:1.4;display:block;margin-bottom:6px}.metric small{font-size:10px}.metric .text-metric{font-size:24px;line-height:1.87}
.evidence-section{padding:24px;background:white;border:1px solid var(--border);border-radius:5px;margin-bottom:22px;min-width:0}
.table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:4px}table{border-collapse:collapse;width:100%;background:white;table-layout:fixed}.wide-table{min-width:680px}
caption{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--border);padding:13px 16px;overflow-wrap:anywhere;font-size:12px}
th{background:#f5f7fb;color:#536079;font-size:10px;letter-spacing:.035em;font-weight:650}td:first-child{font-weight:600;color:#43506a}tbody tr:nth-child(even){background:#fcfcfe}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:#f5f8ff}
.limits{border-top:3px solid #1a55e3}.limits p{font-size:12px;color:var(--muted)}.empty-state{font-size:12px;color:var(--muted);padding:12px;background:#f8f9fb;border:1px dashed #d5dce8}
footer{max-width:1500px;margin:auto;padding:0 32px 24px;display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;color:var(--muted);font-size:10px}
@media(max-width:900px){.dashboard{grid-template-columns:minmax(0,1fr)}.topbar{padding:0 20px;gap:16px;min-height:68px}.brand{min-width:0;border:0;padding:14px 0}.brand-logo{width:160px}.header-context{display:none}.lab-label span{display:none}.sidebar{position:static;height:auto;border-right:0;border-bottom:1px solid var(--border);padding:14px 20px}.workspace-identity,.nav-caption,.sidebar-note{display:none}nav{grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}nav a{padding:8px 10px;font-size:11px}.nav-index{font-size:9px}main{padding:24px}.page-heading{align-items:start;flex-wrap:wrap}.metrics{gap:12px}.metric{padding:18px}.metric .text-metric{font-size:21px}.evidence-section{padding:20px}footer{padding:0 24px 24px}}
@media(max-width:600px){main{padding:20px 16px}h1{font-size:25px}.metrics{grid-template-columns:1fr}.metric{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:12px}.metric>span{align-self:end}.metric strong{grid-column:2;grid-row:1/3;align-self:center}.metric small{grid-column:1}.evidence-section{padding:18px}th,td{padding:11px 12px;font-size:11px}th{font-size:10px}footer{padding:0 16px 20px}}
@media print{.topbar,.sidebar,.skip{display:none}.dashboard{display:block}main{padding:0}.metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.table-wrap{overflow:visible}.wide-table{min-width:0}.evidence-section{break-inside:avoid}.notice{color:#313131}}
"""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; '
        'base-uri \'none\'; form-action \'none\'">'
        f'<title>Caldova recorded workflow evidence</title><style>{style}</style></head><body>'
        '<div class="dashboard"><a class="skip" href="#evidence">Skip to evidence</a>'
        '<header class="topbar"><a class="brand" href="#evidence">'
        f'<img class="brand-logo" src="data:image/svg+xml;base64,{logo}" alt="Caldova" width="1305" height="326"></a>'
        '<span class="header-context">Workflow evidence</span>'
        '<span class="lab-label">LAB722<span>Recorded run</span></span></header>'
        '<aside class="sidebar"><div class="workspace-identity">Caldova workspace'
        '<span>Research Preview Factory</span></div><p class="nav-caption">Evidence explorer</p>'
        f'<nav aria-label="Workflow navigation">{navigation}</nav>'
        '<p class="sidebar-note">Offline, read-only evidence.<br>No live operations or release approval.</p></aside>'
        '<div class="content"><main id="evidence" tabindex="-1"><div class="page-heading">'
        '<div><p class="eyebrow">Trace the recorded delivery</p>'
        '<h1>Caldova recorded workflow evidence</h1>'
        '<p class="intro">Follow the run, specialist work and separate publication receipts.</p></div>'
        '<span class="badge">Historical evidence</span></div>'
        '<p class="notice"><strong>Evidence integrity verified, not release approval.</strong> '
        'Attendee readiness: false. Current live state checked: false. No tests or candidate code executed.</p>'
        '<section class="metrics" aria-label="Recorded evidence summary">'
        f'<div class="metric"><span>Recorded specialists</span><strong>{len(report["workers"])}</strong>'
        '<small>Historical worker reports</small></div>'
        f'<div class="metric"><span>Recorded checks</span><strong>{len(report["checks"])}</strong>'
        '<small>Recorded results, not rerun</small></div>'
        '<div class="metric"><span>Current live state</span><strong class="text-metric">Not checked</strong>'
        '<small>This viewer is offline</small></div></section>'
        f'{body}</main><footer>Offline receipt inspection; no external assets or telemetry workbook.'
        '<span>Microsoft Ignite 2026 / LAB722</span></footer></div></div></body></html>'
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
