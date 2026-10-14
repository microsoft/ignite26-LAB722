import copy
import importlib.util
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "src" / "developer-image" / "stage_candidate.py"
spec = importlib.util.spec_from_file_location("stage_candidate", HELPER)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class CandidatePackagingTests(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / ".build-contexts" / f".ct-{uuid4().hex[:8]}"
        self.root = self.workspace / "r"
        self.root.mkdir(parents=True)
        self.result_path = self.workspace / "accepted-result.json"
        self.descriptor_path = self.workspace / "baseline-descriptor.json"
        self.frozen = self.workspace / "frozen"
        self.frozen.mkdir()
        self.run_id = str(uuid4())
        self.primary_id = str(uuid4())
        self.snapshot_id = str(uuid4())
        self.roles = sorted(packager.ROLES)
        self.bindings = [
            {"role": role, "sandbox_id": str(uuid4()), "snapshot_id": self.snapshot_id,
             "workspace": "/opt/caldova-lab"} for role in self.roles
        ]
        files = set(packager.TRUSTED_FILES) | {
            "src/research-portal/frontend/src/main.tsx", "src/research-portal/frontend/src/styles.css",
        } | set(packager.MODULES.values())
        for name in files:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"raise RuntimeError('Synthetic trusted bundle must not execute locally')\n")
        for name in packager.BUILDER_FILES | {"scripts/build-agent-candidate.ps1", "scripts/lab-image-target.ps1"}:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        shutil.copyfile(ROOT / "src/workers/frozen_contract.py", self.root / "src/workers/frozen_contract.py")
        shutil.copyfile(ROOT / "data/pipeline/public_policy.py", self.root / "data/pipeline/public_policy.py")
        database = b"Exact synthetic artifact bytes; not a database rebuilt for a frozen run.\x00\xfe"
        (self.frozen / "caldova-research.duckdb").write_bytes(database)
        self.manifest = {
            "schema_version": "1.0", "dataset_version": "synthetic-packaging-test",
            "dataset_kind": "synthetic-development", "built_at": "2026-10-09T00:00:00Z",
            "pipeline_commit": "test-working-tree", "logical_sha256": "a" * 64,
            "database": {"path": "caldova-research.duckdb", "sha256": packager.sha256_bytes(database),
                         "bytes": len(database)},
            "record_counts": {table: 0 for table in packager.ROW_COUNTS},
            "sources": [{"source_id": "synthetic", "name": "Invented packaging test", "url": None,
                         "release": "test", "retrieved_at": None, "attribution": "Lab",
                         "license_notes": "Not clinical evidence."}],
            "review": None, "limitations": packager.LIMITATIONS,
        }
        packager.write_json(self.frozen / "data-manifest.json", self.manifest)
        self.manifest_sha = packager.file_sha256(self.frozen / "data-manifest.json")
        self.baseline = {
            "schema_version": "1.0", "source_revision": "synthetic-test-working-tree",
            "toolchains": {"python": "3.13.16", "node": "v24.21.0"},
            "dataset_version": self.manifest["dataset_version"], "dataset_kind": "synthetic-development",
            "database_sha256": self.manifest["database"]["sha256"],
            "data_manifest_sha256": self.manifest_sha, "editable_modules": packager.MODULES,
            "protected_files": {
                name: packager.file_sha256(self.root / name) for name in files - set(packager.MODULES.values())
            },
        }
        packager.write_json(self.workspace / "prepared-baseline.json", self.baseline)
        self.descriptor = {
            "schema_version": "1.0", "dataset_kind": "synthetic-development",
            "dataset_version": self.manifest["dataset_version"], "source_revision": self.baseline["source_revision"],
            "primary_id": self.primary_id, "snapshot_id": self.snapshot_id, "bindings": self.bindings,
            "artifacts": {"manifest": "data-manifest.json", "baseline": "prepared-baseline.json",
                          "bindings": "bindings.json"},
            "frozen_identity": {
                "database_sha256": self.manifest["database"]["sha256"], "logical_sha256": "a" * 64,
                "data_manifest_sha256": self.manifest_sha,
                "baseline_manifest_sha256": packager.file_sha256(self.workspace / "prepared-baseline.json"),
            },
        }
        packager.write_json(self.descriptor_path, self.descriptor)
        self.result = {
            "plan": {
                "schema_version": "1.0", "run_id": self.run_id,
                "dataset_version": self.manifest["dataset_version"], "logical_sha256": "a" * 64,
                "assignments": [
                    {"role": role, "task": "Synthetic software packaging task",
                     "acceptance_criteria": sorted(packager.ROLE_CHECKS[role])} for role in self.roles
                ],
                "release_requires_human_approval": True, "limitations": packager.LIMITATIONS,
            },
            "release_status": "requires-complete-release-evidence-and-human-approval",
            "workers": [
                {"schema_version": "1.0", "run_id": self.run_id, "role": binding["role"],
                 "sandbox_id": binding["sandbox_id"], "dataset_version": self.manifest["dataset_version"],
                 "logical_sha256": "a" * 64, "summary": "Synthetic accepted output",
                 "source_record_ids": [], "blockers": []} for binding in self.bindings
            ],
            "candidate_sources": {},
        }
        for field, checks in (
            ("integration_evidence", packager.INTEGRATION_CHECKS),
            ("egress_evidence", packager.EGRESS_CHECKS), ("worker_evidence", packager.WORKER_CHECKS),
        ):
            self.result[field] = []
            for name in sorted(checks):
                sandbox_id = self.primary_id
                if name.endswith("-feature-contract"):
                    sandbox_id = next(binding["sandbox_id"] for binding in self.bindings
                                      if binding["role"] == name.removesuffix("-feature-contract"))
                self.result[field].append({
                    "run_id": self.run_id, "name": name, "sandbox_id": sandbox_id,
                    "exit_code": 0, "passed": True, "output_sha256": "c" * 64,
                })
        for role, name in packager.MODULES.items():
            content = f"raise RuntimeError('Candidate {role} must never execute on the maintainer host')\n"
            self.result["candidate_sources"][name] = {
                "path": name, "content": content, "sha256": packager.sha256_bytes(content.encode("utf-8")),
            }
        self.original_result = copy.deepcopy(self.result)
        self.save_result()

    def tearDown(self):
        shutil.rmtree(self.workspace)

    def save_result(self):
        packager.write_json(self.result_path, self.result)

    def options(self, name="candidate"):
        return {
            "result_path": self.result_path, "result_sha256": packager.file_sha256(self.result_path),
            "baseline_descriptor_path": self.descriptor_path, "frozen_artifact_directory": self.frozen,
            "manifest_sha256": self.manifest_sha, "approved_run_id": self.run_id,
            "destination": self.root / ".build-contexts" / name, "repository_root": self.root,
        }

    def assert_blocked(self, name="blocked", **changes):
        options = {**self.options(name), **changes}
        with self.assertRaises((ValueError, FileNotFoundError)):
            packager.stage_candidate(**options)
        self.assertFalse(options["destination"].exists())
        self.assertFalse(list(options["destination"].parent.glob(".s-*")))

    def test_stages_only_exact_feature_bytes_and_frozen_bytes_without_touching_reference(self):
        reference = {name: (self.root / name).read_bytes() for name in self.baseline["protected_files"]}
        reference.update({name: (self.root / name).read_bytes() for name in packager.MODULES.values()})
        artifacts = {path.name: path.read_bytes() for path in self.frozen.iterdir()}
        staged = packager.stage_candidate(**self.options())
        destination = Path(staged["directory"])
        self.assertEqual(set(staged["candidate_sources"]), set(packager.MODULES.values()))
        for name, source in self.result["candidate_sources"].items():
            self.assertEqual((destination / name).read_bytes(), source["content"].encode("utf-8"))
            self.assertEqual(packager.file_sha256(destination / name), source["sha256"])
        for name, value in artifacts.items():
            self.assertEqual((destination / "data" / "artifacts" / "development" / name).read_bytes(), value)
            self.assertEqual((self.frozen / name).read_bytes(), value)
        for name, value in reference.items():
            self.assertEqual((self.root / name).read_bytes(), value)
            if name not in packager.MODULES.values():
                self.assertEqual((destination / name).read_bytes(), value)
        self.assertFalse(staged["human_approval"])
        self.assertFalse(staged["release_approved"])
        self.assertEqual(staged["status"], "staged-awaiting-container-validation")
        self.assertFalse((destination / "candidate-image.json").exists())
        packager.verify_context(destination, staged["provenance_sha256"])

    def test_missing_duplicate_foreign_failed_or_malformed_evidence_blocks_every_group(self):
        for field in ("integration_evidence", "egress_evidence", "worker_evidence"):
            for fault in ("missing", "duplicate", "foreign-name", "foreign-run", "foreign-sandbox",
                          "failed", "false", "boolean-exit", "string-passed", "bad-hash"):
                with self.subTest(field=field, fault=fault):
                    self.result = copy.deepcopy(self.original_result)
                    checks = self.result[field]
                    if fault == "missing":
                        checks.pop()
                    elif fault == "duplicate":
                        checks.append(copy.deepcopy(checks[0]))
                    else:
                        name, value = {
                            "foreign-name": ("name", "unknown-check"), "foreign-run": ("run_id", str(uuid4())),
                            "foreign-sandbox": ("sandbox_id", str(uuid4())), "failed": ("exit_code", 1),
                            "false": ("passed", False), "boolean-exit": ("exit_code", False),
                            "string-passed": ("passed", "true"), "bad-hash": ("output_sha256", "not-a-hash"),
                        }[fault]
                        checks[0][name] = value
                    self.save_result()
                    self.assert_blocked()

    def test_source_hash_path_allowlist_and_result_trust_anchor_are_enforced(self):
        name = packager.MODULES["clinical-trials"]
        for fault in ("hash", "path", "extra-module", "content", "unsupported-field", "result-anchor"):
            with self.subTest(fault=fault):
                self.result = copy.deepcopy(self.original_result)
                if fault == "hash":
                    self.result["candidate_sources"][name]["sha256"] = "d" * 64
                elif fault == "path":
                    self.result["candidate_sources"][name]["path"] = "../trial_feature.py"
                elif fault == "extra-module":
                    self.result["candidate_sources"]["src/research-portal/backend/app.py"] = \
                        copy.deepcopy(self.result["candidate_sources"][name])
                elif fault == "content":
                    self.result["candidate_sources"][name]["content"] += "\r\n"
                elif fault == "unsupported-field":
                    self.result["candidate_sources"][name]["approved"] = True
                self.save_result()
                changes = {"result_sha256": "e" * 64} if fault == "result-anchor" else {}
                self.assert_blocked(**changes)

    def test_missing_or_changed_frozen_artifact_blocks_without_rebuilding(self):
        database = self.frozen / self.manifest["database"]["path"]
        original = database.read_bytes()
        database.write_bytes(original + b"x")
        self.assert_blocked()
        database.write_bytes(b"x" * len(original))
        self.assert_blocked()
        database.unlink()
        self.assert_blocked()
        database.write_bytes(original)
        manifest = self.frozen / "data-manifest.json"
        manifest.write_bytes(manifest.read_bytes() + b" ")
        self.assert_blocked()

    def test_manifest_paths_schema_and_logical_identity_are_fail_closed(self):
        original_descriptor = copy.deepcopy(self.descriptor)
        original_manifest = copy.deepcopy(self.manifest)
        for fault in ("traversal", "absolute", "backslash", "unsupported-schema", "logical-identity"):
            with self.subTest(fault=fault):
                self.descriptor = copy.deepcopy(original_descriptor)
                self.manifest = copy.deepcopy(original_manifest)
                if fault == "unsupported-schema":
                    self.manifest["schema_version"] = "2.0"
                elif fault == "logical-identity":
                    self.manifest["logical_sha256"] = "e" * 64
                else:
                    self.manifest["database"]["path"] = {
                        "traversal": "../caldova-research.duckdb", "absolute": "/caldova-research.duckdb",
                        "backslash": r"foreign\caldova-research.duckdb",
                    }[fault]
                packager.write_json(self.frozen / "data-manifest.json", self.manifest)
                self.manifest_sha = packager.file_sha256(self.frozen / "data-manifest.json")
                self.descriptor["frozen_identity"]["data_manifest_sha256"] = self.manifest_sha
                packager.write_json(self.descriptor_path, self.descriptor)
                self.assert_blocked()

    def test_workers_and_clone_identity_must_match_the_accepted_run(self):
        for field, value in (
            ("blockers", ["Not accepted"]), ("run_id", str(uuid4())),
            ("sandbox_id", str(uuid4())), ("dataset_version", "foreign"),
            ("logical_sha256", "f" * 64), ("schema_version", "2.0"),
            ("source_record_ids", ["DUPLICATE", "DUPLICATE"]),
        ):
            with self.subTest(field=field):
                self.result = copy.deepcopy(self.original_result)
                self.result["workers"][0][field] = value
                self.save_result()
                self.assert_blocked()
        self.result = copy.deepcopy(self.original_result)
        self.save_result()
        self.descriptor["bindings"][0]["snapshot_id"] = str(uuid4())
        packager.write_json(self.descriptor_path, self.descriptor)
        self.assert_blocked()

    def test_unsupported_schema_malformed_json_and_false_approval_cannot_pass(self):
        for target, field, value in (
            ("plan", "schema_version", "2.0"), ("plan", "release_requires_human_approval", False),
            ("result", "release_status", "approved"), ("result", "release_approved", True),
        ):
            with self.subTest(target=target, field=field):
                self.result = copy.deepcopy(self.original_result)
                (self.result if target == "result" else self.result["plan"])[field] = value
                self.save_result()
                self.assert_blocked()
        self.result_path.write_bytes(b'{"plan": {}, "plan": {}}')
        self.assert_blocked()

    def test_changed_trusted_source_and_preexisting_destination_are_never_overwritten(self):
        path = self.root / "tests" / "test_research.py"
        path.write_bytes(b"changed trusted test")
        self.assert_blocked()
        destination = self.options()["destination"]
        destination.mkdir(parents=True)
        sentinel = destination / "retain.txt"
        sentinel.write_bytes(b"retain")
        with self.assertRaisesRegex(ValueError, "preexisting"):
            packager.stage_candidate(**self.options())
        self.assertEqual(sentinel.read_bytes(), b"retain")

    def test_copy_failure_does_not_publish_a_partial_stage(self):
        real_copy = shutil.copyfile
        calls = []

        def fail_during_copy(source, destination):
            calls.append(source)
            if len(calls) == 2:
                raise OSError("Controlled copy failure")
            return real_copy(source, destination)

        with patch.object(packager.shutil, "copyfile", side_effect=fail_during_copy):
            with self.assertRaisesRegex(OSError, "Controlled"):
                packager.stage_candidate(**self.options())
        self.assertFalse(self.options()["destination"].exists())
        self.assertFalse(list(self.options()["destination"].parent.glob(".s-*")))

    def test_context_mutation_is_rejected_and_host_cannot_run_container_validation(self):
        staged = packager.stage_candidate(**self.options())
        destination = Path(staged["directory"])
        extra = destination / "foreign.py"
        extra.write_bytes(b"foreign")
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            packager.verify_context(destination, staged["provenance_sha256"])
        extra.unlink()
        (destination / packager.MODULES["drug-safety"]).write_bytes(b"mutated")
        with self.assertRaisesRegex(ValueError, "checksum"):
            packager.verify_context(destination, staged["provenance_sha256"])
        with self.assertRaisesRegex(ValueError, "restricted"):
            packager.validate_container()

    def invoke_native(self, name, fault="", extra=None):
        script = self.root / "scripts" / "build-agent-candidate.ps1"
        call_log = self.workspace / f"{name}-native.jsonl"
        options = self.options(name)
        arguments = {
            "ResultPath": str(self.result_path), "ResultSha256": options["result_sha256"],
            "BaselineDescriptorPath": str(self.descriptor_path), "FrozenArtifactDirectory": str(self.frozen),
            "ManifestSha256": self.manifest_sha, "ApprovedRunId": self.run_id,
            "Destination": str(options["destination"]), "RegistryName": "lab7222tf3zuqwfs4huacr",
            "SubscriptionId": "30501c6c-81f6-41ac-a388-d29cf43a020d", "Tag": "offline-candidate-test",
        }
        arguments.update(extra or {})
        program = r"""
$ErrorActionPreference = 'Stop'
function global:az {
    $native = @($args)
    [IO.File]::AppendAllText($env:CANDIDATE_TEST_CALLS, (ConvertTo-Json -InputObject $native -Compress) + "`n")
    $global:LASTEXITCODE = 0
    $options = $env:CANDIDATE_TEST_OPTIONS | ConvertFrom-Json
    if ($native[0] -eq 'account') {
        $id = $options.SubscriptionId
        if ($env:CANDIDATE_TEST_FAULT -eq 'wrong-account') { $id = '10000000-0000-0000-0000-000000000001' }
        return (@{id=$id;state='Enabled'} | ConvertTo-Json)
    }
    if ($native[0] -eq 'resource') {
        $id = "/subscriptions/$($options.SubscriptionId)/resourceGroups/$($options.ResourceGroupName)/providers/Microsoft.ContainerRegistry/registries/$($options.RegistryName)"
        if ($env:CANDIDATE_TEST_FAULT -eq 'wrong-registry-scope') { $id += '-foreign' }
        return (@{id=$id;name=$options.RegistryName;type='Microsoft.ContainerRegistry/registries'
            tags=@{lab='LAB722'};properties=@{provisioningState='Succeeded';loginServer="$($options.RegistryName).azurecr.io"}} |
            ConvertTo-Json -Depth 5)
    }
    if ($native[0] -eq 'acr' -and $native[1] -eq 'repository' -and $native[2] -eq 'list') {
        if ($env:CANDIDATE_TEST_FAULT -eq 'empty-registry') { return '[]' }
        return '["caldova/research-portal"]'
    }
    if ($native[1] -eq 'repository') {
        if ($env:CANDIDATE_TEST_FAULT -eq 'tag-failure') { $global:LASTEXITCODE = 1; return }
        if ($env:CANDIDATE_TEST_FAULT -eq 'existing-tag') { return '["offline-candidate-test"]' }
        if ($env:CANDIDATE_TEST_FAULT -eq 'malformed-tags') { return '{"tags":[]}' }
        return '[]'
    }
    if ($native[1] -ne 'build') { throw 'Unexpected fake ACR operation' }
    $selectedDockerfile = [string] $native[[array]::IndexOf($native, '--file') + 1]
    $expectedDockerfile = [IO.Path]::GetFullPath((Join-Path ([string] $native[-1]) 'Dockerfile'))
    if (-not [IO.Path]::IsPathFullyQualified($selectedDockerfile) -or
        $selectedDockerfile -cne $expectedDockerfile -or
        -not (Test-Path -LiteralPath $selectedDockerfile -PathType Leaf)) {
        throw 'ACR --file must resolve to the existing absolute staged Dockerfile, not repository cwd.'
    }
    $provenance = Get-Content -Raw -LiteralPath (Join-Path ([string] $native[-1]) 'candidate-provenance.json') |
        ConvertFrom-Json
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $selectedDockerfile).Hash.ToLowerInvariant() -cne
        $provenance.context_files.Dockerfile) {
        throw 'The selected Dockerfile does not match the pinned staged bytes.'
    }
    if ($env:CANDIDATE_TEST_FAULT -eq 'build-failure') { $global:LASTEXITCODE = 1; return }
    $image = @{
        registry = "$($options.RegistryName).azurecr.io"
        repository = 'caldova/research-portal'; tag = 'offline-candidate-test'; digest = ('sha256:' + ('d' * 64))
    }
    if ($env:CANDIDATE_TEST_FAULT -eq 'bad-digest') { $image.digest = 'not-a-digest' }
    if ($env:CANDIDATE_TEST_FAULT -eq 'foreign-image') { $image.repository = 'foreign/image' }
    if ($env:CANDIDATE_TEST_FAULT -eq 'changed-context') {
        [IO.File]::WriteAllText((Join-Path $native[-1] 'foreign.txt'), 'changed')
    }
    @{ status = 'Succeeded'; runId = 'offline-acr-run'; outputImages = @($image) } | ConvertTo-Json -Depth 6
}
if ($env:CANDIDATE_TEST_FAULT -eq 'missing-dockerfile') {
    $global:candidateTrustedPython = (Get-Command python).Source
    function global:python {
        $native = @($args)
        & $global:candidateTrustedPython @native
        $exitCode = $LASTEXITCODE
        if ($native -contains '--verify-context') {
            $context = [string] $native[[array]::IndexOf($native, '--verify-context') + 1]
            Remove-Item -LiteralPath (Join-Path $context 'Dockerfile')
        }
        $global:LASTEXITCODE = $exitCode
    }
}
try {
    $options = $env:CANDIDATE_TEST_OPTIONS | ConvertFrom-Json -AsHashtable
    & $env:CANDIDATE_TEST_SCRIPT @options | ConvertTo-Json -Depth 20
}
catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
"""
        environment = {
            **os.environ, "CANDIDATE_TEST_SCRIPT": str(script), "CANDIDATE_TEST_CALLS": str(call_log),
            "CANDIDATE_TEST_FAULT": fault, "CANDIDATE_TEST_OPTIONS": json.dumps(arguments),
        }
        result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", program],
                                cwd=self.root, env=environment, capture_output=True, text=True, timeout=60)
        calls = [json.loads(line) for line in call_log.read_text().splitlines()] if call_log.exists() else []
        return result, calls, options["destination"]

    def test_native_stage_only_and_whatif_never_call_acr(self):
        for flag in ("StageOnly", "WhatIf"):
            with self.subTest(flag=flag):
                result, calls, destination = self.invoke_native(flag, extra={flag: True})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(calls, [])
                self.assertTrue((destination / "candidate-provenance.json").is_file())
                self.assertFalse((destination / "candidate-image.json").exists())

    def test_portable_publication_checks_the_current_registry_before_build_and_preserves_offline_staging(self):
        scope = {"SubscriptionId": str(uuid4()), "RegistryName": "participantregistry",
                 "ResourceGroupName": "participant-rg"}
        result, calls, destination = self.invoke_native("portable", extra=scope)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call[:2] for call in calls],
                         [["account", "show"], ["resource", "show"],
                          ["acr", "repository"], ["acr", "repository"], ["acr", "build"]])
        image = json.loads((destination / "candidate-image.json").read_text())["image"]
        self.assertTrue(image["reference"].startswith("participantregistry.azurecr.io/"))
        self.assertEqual(image["resource_group"], "participant-rg")
        result, calls, _ = self.invoke_native("portable-stage", extra={**scope, "StageOnly": True})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [])
        result, calls, _ = self.invoke_native("first-repository", "empty-registry", scope)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any(call[:2] == ["acr", "build"] for call in calls))
        self.assertFalse(any(call[:3] == ["acr", "repository", "show-tags"] for call in calls))
        for fault in ("wrong-account", "wrong-registry-scope"):
            result, calls, destination = self.invoke_native(fault, fault, scope)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(any(call[:2] == ["acr", "build"] for call in calls))
            self.assertFalse((destination / "candidate-image.json").exists())

    def test_native_evidence_failure_blocks_before_any_acr_operation(self):
        self.result["egress_evidence"][0]["passed"] = False
        self.save_result()
        result, calls, destination = self.invoke_native("failed-evidence")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])
        self.assertFalse(destination.exists())

    def test_native_build_selects_existing_staged_dockerfile_from_repository_cwd(self):
        self.assertFalse((self.root / "Dockerfile").exists())
        result, calls, destination = self.invoke_native("dockerfile-path")
        self.assertEqual(result.returncode, 0, result.stderr)
        build = calls[1]
        selected = Path(build[build.index("--file") + 1])
        self.assertTrue(selected.is_absolute())
        self.assertEqual(selected, destination / "Dockerfile")
        self.assertTrue(selected.is_file())
        provenance = json.loads((destination / "candidate-provenance.json").read_text())
        self.assertEqual(packager.file_sha256(selected), provenance["context_files"]["Dockerfile"])

    def test_native_missing_stage_dockerfile_blocks_before_build(self):
        result, calls, destination = self.invoke_native("missing-dockerfile", "missing-dockerfile")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1, result.stderr)
        self.assertEqual(calls[0][:3], ["acr", "repository", "show-tags"])
        self.assertFalse((destination / "candidate-image.json").exists())
        self.assertIn("staged Dockerfile is missing", result.stderr)

    def test_native_build_contract_and_digest_bound_descriptor_with_fake_acr_only(self):
        result, calls, destination = self.invoke_native("native-success")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 2)
        build = calls[1]
        self.assertEqual(build[:2], ["acr", "build"])
        for name, value in (
            ("--registry", "lab7222tf3zuqwfs4huacr"), ("--repository", "caldova/research-portal"),
        ):
            selected = calls[0] if name == "--repository" else build
            self.assertEqual(selected[selected.index(name) + 1], value)
        self.assertEqual(build[build.index("--platform") + 1], "linux/amd64")
        self.assertEqual(build[build.index("--target") + 1], "candidate")
        self.assertEqual(str(build[build.index("--timeout") + 1]), "1200")
        self.assertIn("--no-logs", build)
        self.assertEqual(build[-1], str(destination))
        self.assertFalse(set(build) & {"--token", "--password", "--username", "--debug", "--verbose"})
        descriptor = json.loads((destination / "candidate-image.json").read_text())
        self.assertEqual(descriptor["image"]["digest"], "sha256:" + "d" * 64)
        self.assertEqual(descriptor["candidate_sources"], {
            name: value["sha256"] for name, value in self.result["candidate_sources"].items()
        })
        self.assertEqual(descriptor["frozen_identity"], self.descriptor["frozen_identity"])
        self.assertEqual(descriptor["run_id"], self.run_id)
        self.assertEqual(descriptor["image"]["acr_run_id"], "offline-acr-run")
        self.assertFalse(descriptor["human_approval"])
        self.assertFalse(descriptor["release_approved"])
        self.assertFalse(descriptor["deployed"])

    def test_native_failures_never_publish_an_image_descriptor(self):
        for fault in ("tag-failure", "existing-tag", "malformed-tags", "build-failure",
                      "bad-digest", "foreign-image", "changed-context"):
            with self.subTest(fault=fault):
                result, calls, destination = self.invoke_native(fault, fault)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertFalse((destination / "candidate-image.json").exists())
                expected = 1 if fault in {"tag-failure", "existing-tag", "malformed-tags"} else 2
                self.assertEqual(len(calls), expected, result.stderr)

    def test_native_argument_validation_rejects_foreign_scope_and_invalid_tag_before_cloud(self):
        for name, changes in (
            ("registry", {"RegistryName": "foreignregistry"}),
            ("subscription", {"SubscriptionId": str(uuid4())}),
            ("tag", {"Tag": "invalid tag"}),
            ("run", {"ApprovedRunId": str(uuid4())}),
        ):
            with self.subTest(name=name):
                result, calls, destination = self.invoke_native(f"invalid-{name}", extra=changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])
                self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
