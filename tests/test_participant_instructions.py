"""Exercise actual pasted participant blocks without Azure calls."""

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBSCRIPTION = "10000000-0000-0000-0000-000000000002"


class EgressChallengeTests(unittest.TestCase):
    def test_pasted_probe_reports_http_responses_without_disguising_transport_errors(self):
        source = (ROOT / "instructions" / "03-prepare-sandbox.md").read_text(encoding="utf-8")
        block = next(block for block in re.findall(r"```bash\n(.*?)\n```", source, re.S)
                     if "from urllib.request import urlopen" in block)
        code = re.fullmatch(r"python3 - <<'PY'\n(.*)\nPY", block, re.S).group(1)

        class Handler(BaseHTTPRequestHandler):
            denied_status = 403

            def do_GET(self):
                if self.path == "/network-error":
                    self.close_connection = True
                    return
                self.send_response(200 if self.path == "/allowed" else self.denied_status)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            for status, path in ((403, "/denied"), (200, "/denied"), (403, "/network-error")):
                with self.subTest(status=status, path=path):
                    Handler.denied_status = status
                    actual = code.replace("https://open.fda.gov/apis/", base_url + "/allowed")
                    actual = actual.replace("https://example.com/", base_url + path)
                    result = subprocess.run(
                        [sys.executable, "-c", actual], capture_output=True, text=True, timeout=10,
                    )
                    self.assertIn(f"{base_url}/allowed: HTTP 200", result.stdout)
                    if path == "/network-error":
                        self.assertNotEqual(result.returncode, 0)
                        self.assertNotIn("HTTP 403", result.stdout)
                        self.assertIn("Traceback", result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn(f"{base_url}{path}: HTTP {status}", result.stdout)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


@unittest.skipUnless(shutil.which("pwsh"), "Native PowerShell is required.")
class InstructionExportTests(unittest.TestCase):
    def test_export_keeps_source_section_numbers_and_pasted_commands_in_sync(self):
        def headings(text):
            inside_code = False
            result = []
            for line in text.splitlines():
                if re.match(r"^(?:> ?)?```", line):
                    inside_code = not inside_code
                elif not inside_code:
                    match = re.match(r"^(#{1,3}) (.+)$", line)
                    if match:
                        result.append((len(match[1]), match[2]))
            return result

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "skillable.md"
            completed = subprocess.run(
                ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
                 str(ROOT / "scripts" / "export-skillable-instructions.ps1"),
                 "-OutputPath", str(output)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manual = output.read_text(encoding="utf-8")
            self.assertEqual(manual, (ROOT / "instructions" / "skillable.md").read_text(encoding="utf-8"))
            exported_images = dict(re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", manual))
            exported_headings = headings(manual)
            for content in (manual, (ROOT / "instructions" / "facilitator.md").read_text(encoding="utf-8")):
                counters = [0, 0, 0]
                for level, title in headings(content):
                    with self.subTest(heading=title):
                        if level == 1 and title == "@lab.Title":
                            self.assertEqual(counters, [0, 0, 0])
                            counters[0] = 1
                            continue
                        counters[level - 1] += 1
                        counters[level:] = [0] * (3 - level)
                        prefix = ".".join(map(str, counters[:level])) + ("." if level == 1 else "")
                        self.assertTrue(title.startswith(prefix + " "), title)
            source_headings = []
            for path in (ROOT / "instructions").glob("*.md"):
                if path.name in ("skillable.md", "facilitator.md"):
                    continue
                source = path.read_text(encoding="utf-8")
                source_headings.extend(headings(source))
                for block in re.findall(r"(?m)^(?:> ?)?```powershell\n(.*?)\n(?:> ?)?```", source, re.S):
                    self.assertIn(block, manual, path.name)
                for label, target in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", source):
                    if target.startswith(("https://", "http://")):
                        continue
                    image = path.parent / target
                    self.assertTrue(image.is_file(), target)
                    self.assertEqual(image.read_bytes()[:8], b"\x89PNG\r\n\x1a\n", target)
                    self.assertTrue(exported_images[label].startswith("data:image/png;base64,"), target)
                    self.assertEqual(
                        base64.b64decode(exported_images[label].split(",", 1)[1], validate=True),
                        image.read_bytes(),
                    )
            self.assertCountEqual(exported_headings[2:], source_headings)


@unittest.skipUnless(shutil.which("pwsh"), "Native PowerShell is required.")
class ParticipantBlockTests(unittest.TestCase):
    def test_starter_block_requires_explicit_fallback_and_preserves_readiness_handoff(self):
        source = (ROOT / "instructions" / "01-open-research-portal.md").read_text(encoding="utf-8")
        block = re.findall(r"```powershell\n(.*?)\n```", source, re.S)[0]
        for action, missing_app in (("", False), ("fallback", False), ("unexpected", False), ("", True)):
            with self.subTest(action=action, missing_app=missing_app), \
                    tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "scripts").mkdir()
                (root / "data").mkdir()
                (root / "data" / "lab-images.json").write_bytes((ROOT / "data" / "lab-images.json").read_bytes())
                activation = root / "Caldova" / "venvs" / "application" / "Scripts" / "Activate.ps1"
                activation.parent.mkdir(parents=True)
                activation.write_text("", encoding="utf-8")
                (root / "scripts" / "stage-lab-data.ps1").write_text(
                    "param([switch]$ConfigureSession)\n"
                    "$env:LAB_DATA_MANIFEST='VERIFIED_LOCAL_MANIFEST'\n", encoding="utf-8")
                (root / "scripts" / "deploy-lab-starter.ps1").write_text(
                    "param($SubscriptionId,$ResourceGroupName,$ExpressEnvironmentName,$Region,$RegistryName,"
                    "[switch]$PinExisting,[switch]$AuthorizeDeployment)\n"
                    "if ($PinExisting) {\n"
                    + ("throw 'No existing starter in LAB722'\n" if missing_app else "'PINNED_EXISTING'; return\n")
                    + "}\n"
                    f"if ($SubscriptionId -cne '{SUBSCRIPTION}' -or $ResourceGroupName -cne 'LAB722' -or "
                    "$ExpressEnvironmentName -cne 'allocated-express' -or $Region -cne 'westus3' -or "
                    "-not $AuthorizeDeployment) { throw 'Starter scope was lost' }\n"
                    "'CREATED_ONCE'\n", encoding="utf-8")
                (root / "scripts" / "start-lab.ps1").write_text(
                    "param($ResourceGroupName,$Region,$Mode)\n"
                    "'{\"application_ready\":true,\"application_manifest_verified\":true,"
                    "\"frozen_data_verified\":true,\"outputs\":{\"marker\":\"VERIFIED_STARTER\"}}'\n",
                    encoding="utf-8")
                location = str(root).replace("'", "''")
                script = (
                    f"Set-Location '{location}'; $env:LOCALAPPDATA='{location}'\n"
                    f"$env:AZURE_SUBSCRIPTION_ID='{SUBSCRIPTION}'\n"
                    "$resourceGroupName='LAB722'; $region='westus3'\n"
                    "$labOutputs=@{EXPRESS_ENVIRONMENT_NAME='allocated-express'}\n"
                    "$readiness=$plan=$controllerArgs='STALE'; $env:LAB_DATA_MANIFEST=$null\n"
                    f"$global:StarterAction='{action}'; $global:Prompts=0\n"
                    "function Set-Clipboard { param($Value) }\n"
                    "function Start-Process { param($FilePath) }\n"
                    "function Read-Host { $global:Prompts++; "
                    "if ($global:Prompts -eq 1) { $global:StarterAction } else { '' } }\n"
                    "try {\n" + block + "\n'READINESS:' + $labOutputs.marker\n"
                    "} catch { 'REJECTED:' + $_.Exception.Message }\n"
                    "'LOCAL_DATA:' + $env:LAB_DATA_MANIFEST\n"
                    "'READINESS_CLEARED:' + ($null -eq $readiness)\n"
                    "'PLAN_CLEARED:' + ($null -eq $plan -and $null -eq $controllerArgs)\n"
                    "'PROMPTS:' + $global:Prompts\n"
                )
                result = subprocess.run(
                    ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("LOCAL_DATA:VERIFIED_LOCAL_MANIFEST", result.stdout)
                self.assertIn("PLAN_CLEARED:True", result.stdout)
                self.assertIn(f"PROMPTS:{2 if action == 'fallback' else 1}\n", result.stdout)
                self.assertEqual(result.stdout.count("CREATED_ONCE"), int(action == "fallback"))
                if action == "unexpected":
                    self.assertIn("REJECTED:Expected Enter or fallback.", result.stdout)
                    self.assertNotIn("READINESS:", result.stdout)
                elif missing_app:
                    self.assertIn("REJECTED:No existing starter in LAB722", result.stdout)
                    self.assertIn("READINESS_CLEARED:True", result.stdout)
                    self.assertNotIn("READINESS:", result.stdout)
                else:
                    self.assertIn("READINESS:VERIFIED_STARTER", result.stdout)
                    self.assertEqual(result.stdout.count("PINNED_EXISTING"), 1)

    def test_planning_requires_verified_starter_and_local_dataset_before_calling_controller(self):
        source = (ROOT / "instructions" / "02-configure-orchestrator.md").read_text(encoding="utf-8")
        block = re.findall(r"```powershell\n(.*?)\n```", source, re.S)[1]
        block = block.replace(
            r"Join-Path $env:LOCALAPPDATA 'Caldova\venvs\controller\Scripts\python.exe'",
            "'Invoke-ControllerFixture'",
        )
        for fault in ("starter-missing", "starter-incomplete", "manifest-blank", "manifest-missing",
                      "hash-missing", "purpose-missing", ""):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "Invoke-ControllerFixture").touch()
                manifest = root / "manifest.json"
                manifest.write_text("{}", encoding="utf-8")
                location = str(root).replace("'", "''")
                manifest_path = str(manifest).replace("'", "''")
                script = (
                    f"Set-Location '{location}'\n"
                    "$readiness=[pscustomobject]@{application_ready=$true;"
                    "application_manifest_verified=$true;frozen_data_verified=$true}\n"
                    f"$env:LAB_DATA_MANIFEST='{manifest_path}'\n"
                    "$env:LAB_DATA_MANIFEST_SHA256='a'*64\n"
                    "$env:LAB_STARTUP_PURPOSE='public-lab-development'\n"
                    f"$fault='{fault}'\n"
                    "switch ($fault) {\n"
                    "'starter-missing' { $readiness=$null }\n"
                    "'starter-incomplete' { $readiness.application_manifest_verified=$false }\n"
                    "'manifest-blank' { $env:LAB_DATA_MANIFEST=$null }\n"
                    "'manifest-missing' { $env:LAB_DATA_MANIFEST += '.missing' }\n"
                    "'hash-missing' { $env:LAB_DATA_MANIFEST_SHA256=$null }\n"
                    "'purpose-missing' { $env:LAB_STARTUP_PURPOSE=$null }\n"
                    "}\n"
                    "$plan=$controllerArgs='STALE'\n"
                    "$labOutputs=@{FOUNDRY_PROJECT_ENDPOINT='https://foundry.example';"
                    "FOUNDRY_MODEL_DEPLOYMENT_NAME='model';"
                    f"AZURE_SUBSCRIPTION_ID='{SUBSCRIPTION}';"
                    "SANDBOX_REGION='westus3';SANDBOX_GROUP_NAME='allocated-sandboxes'}\n"
                    "$resourceGroupName='LAB722'\n"
                    "function Read-Host { '' }\n"
                    "function Get-Command { param($Name,$CommandType); @{Source='aca-fixture'} }\n"
                    "function Invoke-ControllerFixture {\n"
                    "Write-Host 'CONTROLLER_CALLED'\n"
                    "$global:CapturedControllerArgs=@($args)\n"
                    "$global:LASTEXITCODE=0\n"
                    "'{\"plan\":{\"run_id\":\"verified-plan\",\"assignments\":[],"
                    "\"dataset_version\":\"fixture\",\"release_requires_human_approval\":true}}'\n"
                    "}\n"
                    "try {\n" + block + "\n'PLANNING:accepted'\n"
                    "} catch { 'PLANNING:rejected:' + $_.Exception.Message }\n"
                    "'PLAN_CLEARED:' + ($null -eq $plan)\n"
                    "'ARGS_CLEARED:' + ($null -eq $controllerArgs)\n"
                    "'CAPTURED:' + (ConvertTo-Json -Compress -InputObject $global:CapturedControllerArgs)\n"
                )
                result = subprocess.run(
                    ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual("CONTROLLER_CALLED" in result.stdout, not fault, result.stdout)
                if fault:
                    self.assertIn("PLANNING:rejected:", result.stdout)
                    self.assertIn("PLAN_CLEARED:True", result.stdout)
                    self.assertIn("ARGS_CLEARED:True", result.stdout)
                    self.assertNotIn("expected one argument", result.stdout + result.stderr)
                else:
                    self.assertIn("PLANNING:accepted", result.stdout)
                    captured = json.loads(next(
                        line.removeprefix("CAPTURED:") for line in result.stdout.splitlines()
                        if line.startswith("CAPTURED:")
                    ))
                    self.assertEqual(captured[captured.index("--manifest") + 1], str(manifest))

    def test_primary_preparation_requires_plan_and_local_dataset_without_creating_on_failure(self):
        source = (ROOT / "instructions" / "03-prepare-sandbox.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```powershell\n(.*?)\n```", source.split("<!-- pagebreak -->", 1)[0], re.S)
        capacity_blocks = [block for block in blocks if "$groupText = az rest" in block or
                           "$inventoryText = aca.exe sandbox list" in block]
        prerequisites = ("plan-missing", "manifest-blank", "manifest-missing", "purpose-missing")
        before_disk = (*prerequisites, "capacity-low", "capacity-paged", "source-failed")
        before_primary = (*before_disk, "capacity-changed", "disk-failed", "disk-name",
                          "foreign-disk", "repeat-disk-create")
        before_lifecycle = (*before_primary, "primary-name", "foreign-primary", "repeat-primary-create")
        successes = ("", "inventory-wrapped", "inventory-empty", "inventory-single")
        for fault in (*prerequisites, "capacity-low", "capacity-paged", "capacity-changed", "source-failed",
                      "disk-failed", "disk-name", "foreign-disk", "repeat-disk-create",
                      "primary-name", "foreign-primary", "repeat-primary-create", "verify-failed", *successes):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                execution_blocks = []
                for block in blocks:
                    if "aca.exe sandbox create " in block:
                        execution_blocks.extend(capacity_blocks)
                    execution_blocks.append(block)
                    if ((fault == "repeat-disk-create" and "aca.exe sandboxgroup disk create " in block) or
                            (fault == "repeat-primary-create" and "aca.exe sandbox create " in block)):
                        execution_blocks.append(block)
                root = Path(temporary)
                (root / "scripts").mkdir()
                (root / "manifest.json").write_text("{}", encoding="utf-8")
                (root / "primary.json").write_text(json.dumps({
                    "scope": {"resource_group": "LAB722"}, "primary_id": SUBSCRIPTION,
                    "dataset_version": "fixture", "uid": 10001, "workspace": "/opt/caldova-lab",
                }), encoding="utf-8")
                (root / "scripts" / "prepare-worker-baseline.ps1").write_text(r"""
param($Mode,$SubscriptionId,$ResourceGroup,$Region,$GroupName,$OutputDirectory,
    $DiskId,$PrimaryId,$SourceContextDirectory,$SourceContextManifestSha256,
    $FrozenManifest,$FrozenManifestSha256,$Purpose,[switch]$AsJson)
if ($SubscriptionId -ne $global:FixtureSubscription -or $ResourceGroup -cne 'LAB722' -or
    $Region -cne 'westus3' -or $GroupName -cne 'allocated-sandboxes') { throw 'Lost primary scope' }
if ($Mode -ceq 'VerifyPrimary') {
    Write-Host 'VERIFIER_CALLED'
    if ($global:PrimaryFixtureFault -ceq 'verify-failed') { throw 'Fixture integrity failure' }
    if ($DiskId -ne $global:FixtureDisk -or $PrimaryId -ne $global:FixturePrimary -or
        $SourceContextManifestSha256 -cne ('a'*64) -or $Purpose -cne 'public-lab-development') {
        throw 'Lost primary source or identity'
    }
    @{phase='primary-prepared';descriptor='primary.json';descriptor_sha256=('a'*64);
        primary_id=$PrimaryId;disk_id=$DiskId} | ConvertTo-Json
} else { throw 'The learner verifier must not provision resources' }
""", encoding="utf-8")
                location = str(root).replace("'", "''")
                script = (
                    f"Set-Location '{location}'\n"
                    "$plan=[pscustomobject]@{plan=@{run_id='verified-plan'}}\n"
                    "$env:LAB_DATA_MANIFEST=(Join-Path (Get-Location) 'manifest.json')\n"
                    "$env:LAB_DATA_MANIFEST_SHA256='a'*64\n"
                    "$env:LAB_STARTUP_PURPOSE='public-lab-development'\n"
                    "$env:LAB_PYTHON_EXECUTABLE='Invoke-ExporterFixture'\n"
                    f"$fault='{fault}'\n"
                    "switch ($fault) {\n"
                    "'plan-missing' { $plan=$null }\n"
                    "'manifest-blank' { $env:LAB_DATA_MANIFEST=$null }\n"
                    "'manifest-missing' { $env:LAB_DATA_MANIFEST += '.missing' }\n"
                    "'purpose-missing' { $env:LAB_STARTUP_PURPOSE=$null }\n"
                    "}\n"
                    "$resourceGroupName='LAB722'; $region='westus3'\n"
                    f"$global:FixtureSubscription='{SUBSCRIPTION}'\n"
                    "$global:FixtureDisk='10000000-0000-0000-0000-000000000003'\n"
                    "$global:FixturePrimary='10000000-0000-0000-0000-000000000004'\n"
                    "$global:PrimaryFixtureFault=$fault\n"
                    "$global:AcaCalls=[Collections.Generic.List[object]]::new()\n"
                    "$global:CapacityReads=0\n"
                    "$labOutputs=@{AZURE_SUBSCRIPTION_ID=$global:FixtureSubscription;"
                    "SANDBOX_REGION='westus3';SANDBOX_GROUP_NAME='allocated-sandboxes'}\n"
                    "$primaryDescriptorPath=$primaryDescriptorSha256='STALE'\n"
                    "function Read-Host { param($Prompt); "
                    "if ($Prompt -like '*developer disk*') { "
                    "if ($global:PrimaryFixtureFault -ceq 'disk-name') { $primaryDiskName } "
                    "else { $global:FixtureDisk } } "
                    "elseif ($global:PrimaryFixtureFault -ceq 'primary-name') { $primaryName } "
                    "else { $global:FixturePrimary } }\n"
                    "function Start-Process { param($FilePath); 'PORTAL_OPENED' }\n"
                    r"""
function az {
    $expectedId = "/subscriptions/$global:FixtureSubscription/resourceGroups/LAB722/providers/Microsoft.App/sandboxGroups/allocated-sandboxes"
    if (($args[0..3] -join ' ') -cne 'rest --method get --url' -or
        $args[$args.IndexOf('--url') + 1] -cne "https://management.azure.com${expectedId}?api-version=2026-02-01-preview" -or
        $args[$args.IndexOf('--subscription') + 1] -ne $global:FixtureSubscription) {
        throw 'Unexpected ARM operation or scope'
    }
    $global:LASTEXITCODE = 0
    $global:CapacityReads++
    $capacity = if ($global:PrimaryFixtureFault -ceq 'inventory-empty') { 4
    } elseif ($global:PrimaryFixtureFault -ceq 'inventory-single') { 5
    } elseif ($global:PrimaryFixtureFault -ceq 'capacity-low' -or
        ($global:PrimaryFixtureFault -ceq 'capacity-changed' -and $global:CapacityReads -gt 1)) { 8 } else { 9 }
    @{id=$expectedId;location='westus3';properties=@{maxSandboxCount=$capacity;provisioningState='Succeeded'}} |
        ConvertTo-Json -Depth 4
}
function Invoke-ExporterFixture {
    Write-Host 'EXPORT_CALLED'
    $global:LASTEXITCODE = 0
    if ($global:PrimaryFixtureFault -ceq 'source-failed') { $global:LASTEXITCODE=7; return }
    $destination = $args[[array]::IndexOf($args, '--destination') + 1]
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Set-Content (Join-Path $destination 'Dockerfile') 'FROM fixture'
    @{directory=$destination;source_revision='fixture';source_context_manifest_sha256=('a'*64)} |
        ConvertTo-Json
}
function aca.exe {
    $global:AcaCalls.Add(@($args))
    $global:LASTEXITCODE = 0
    $verb = $args[0..2] -join ' '
    if ($verb -ceq 'sandboxgroup disk create') {
        if ($global:PrimaryFixtureFault -ceq 'disk-failed') { $global:LASTEXITCODE=7 }
        'Fixture disk submitted'
    } elseif ($verb -ceq 'sandboxgroup disk list') {
        @{id=$global:FixtureDisk;name=$primaryDiskName} | ConvertTo-Json
    } elseif ($verb -ceq 'sandboxgroup disk get') {
        $name = if ($global:PrimaryFixtureFault -ceq 'foreign-disk') { 'another-attempt' } else { $primaryDiskName }
        @{id=$global:FixtureDisk;name=$name;status=@{state='Ready'}} | ConvertTo-Json -Depth 4
    } elseif ($args[0] -ceq 'sandbox' -and $args[1] -ceq 'list') {
        if ($args -contains '--selector') {
            ConvertTo-Json -InputObject @(@{id=$global:FixturePrimary;labels=@{name=$primaryName;role='primary';lab='LAB722'}}) -Depth 4
        } else {
            $inventory = @(
                if ($global:PrimaryFixtureFault -ceq 'inventory-single') {
                    @{id='10000000-0000-0000-0000-000000000011'}
                } elseif ($global:PrimaryFixtureFault -cne 'inventory-empty') {
                    11..15 | ForEach-Object { @{id=('10000000-0000-0000-0000-{0:d12}' -f $_)} }
                }
            )
            if ($global:PrimaryFixtureFault -ceq 'capacity-paged') {
                @{value=$inventory;nextLink='https://fixture.invalid/next'} | ConvertTo-Json -Depth 4
            } elseif ($global:PrimaryFixtureFault -ceq 'inventory-wrapped') {
                @{value=$inventory;nextLink=$null} | ConvertTo-Json -Depth 4
            } else {
                ConvertTo-Json -InputObject $inventory -Depth 4
            }
        }
    } elseif ($args[0] -ceq 'sandbox' -and $args[1] -ceq 'create') {
        'Created sandbox: ' + $global:FixturePrimary
    } elseif ($args[0] -ceq 'sandbox' -and $args[1] -ceq 'get') {
        $name = if ($global:PrimaryFixtureFault -ceq 'foreign-primary') { 'another-attempt' } else { $primaryName }
        @{id=$global:FixturePrimary;labels=@{name=$name;role='primary';lab='LAB722'}} |
            ConvertTo-Json -Depth 4
    } elseif ($verb -ceq 'sandbox lifecycle set' -or $verb -ceq 'sandbox lifecycle show' -or
        $verb -ceq 'sandbox egress show') {
        '{}'
    } elseif ($args[0] -ceq 'sandbox' -and $args[1] -ceq 'exec') {
        "10001`n/opt/caldova-lab"
    } else { throw "Unexpected learner command: $verb" }
}
"""
                    "try {\n" + "\n".join(execution_blocks) + "\n'PRIMARY:accepted'\n"
                    "} catch { 'PRIMARY:rejected:' + $_.Exception.Message }\n"
                    "'PRIMARY_CLEARED:' + ($null -eq $primaryDescriptorPath -and "
                    "$null -eq $primaryDescriptorSha256)\n"
                    "'CALLS:' + (ConvertTo-Json -Depth 4 -Compress -InputObject $global:AcaCalls.ToArray())\n"
                )
                result = subprocess.run(
                    ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual("EXPORT_CALLED" in result.stdout,
                                 fault not in (*prerequisites, "capacity-low", "capacity-paged"), result.stdout)
                self.assertEqual("VERIFIER_CALLED" in result.stdout, fault in (*successes, "verify-failed"), result.stdout)
                self.assertEqual("PORTAL_OPENED" in result.stdout, fault in successes, result.stdout)
                calls = json.loads(next(
                    line.removeprefix("CALLS:") for line in result.stdout.splitlines()
                    if line.startswith("CALLS:")
                ))
                if fault in prerequisites:
                    self.assertEqual(calls, [], result.stdout)
                for call in calls:
                    self.assertEqual(call[call.index("--subscription") + 1], SUBSCRIPTION)
                    self.assertEqual(call[call.index("--resource-group") + 1], "LAB722")
                    self.assertEqual(call[call.index("--group") + 1], "allocated-sandboxes")
                    self.assertEqual(call[call.index("--region") + 1], "westus3")
                self.assertEqual(sum(call[:3] == ["sandboxgroup", "disk", "create"] for call in calls),
                                 int(fault not in before_disk), result.stdout)
                self.assertEqual(sum(call[:2] == ["sandbox", "create"] for call in calls),
                                 int(fault not in before_primary), result.stdout)
                lifecycle = [call for call in calls if call[:3] == ["sandbox", "lifecycle", "set"]]
                self.assertEqual(len(lifecycle), int(fault not in before_lifecycle), result.stdout)
                if lifecycle:
                    self.assertEqual(lifecycle[0][lifecycle[0].index("--auto-delete") + 1], "disable")
                if fault in successes:
                    create = next(call for call in calls if call[:2] == ["sandbox", "create"])
                    self.assertEqual(create[create.index("--egress-rule") + 1], "open.fda.gov:Allow")
                    self.assertEqual(create[create.index("--egress-default") + 1], "Deny")
                    self.assertEqual(create[create.index("--traffic-inspection") + 1], "Full")
                if fault not in successes:
                    self.assertIn("PRIMARY:rejected:", result.stdout)
                    self.assertIn("PRIMARY_CLEARED:True", result.stdout)
                    if fault in ("disk-name", "primary-name"):
                        self.assertIn("Use the JSON id GUID, not", result.stdout)
                    if fault in ("capacity-low", "capacity-changed"):
                        self.assertIn("Fewer than four Sandbox slots", result.stdout)
                    if fault == "capacity-paged":
                        self.assertIn("Sandbox inventory is incomplete or paged", result.stdout)
                    if fault in ("repeat-disk-create", "repeat-primary-create"):
                        self.assertIn("already", result.stdout)
                else:
                    self.assertIn("PRIMARY:accepted", result.stdout)

    def test_explore_block_rejects_missing_readiness_or_url_before_launch(self):
        source = (ROOT / "instructions" / "01-open-research-portal.md").read_text(encoding="utf-8")
        block = re.findall(r"```powershell\n(.*?)\n```", source, re.S)[1]
        valid = {
            "application_ready": True, "application_manifest_verified": True,
            "frozen_data_verified": True,
            "outputs": {"CALDOVA_APPLICATION_IMAGE": "registry.example/starter@sha256:" + "a" * 64,
                        "CALDOVA_APPLICATION_URL": "https://app.example.azurecontainerapps.io"},
        }
        for receipt in (None, {}, {**valid, "outputs": {}}, valid):
            with self.subTest(receipt=receipt):
                literal = json.dumps(receipt).replace("'", "''")
                script = (
                    f"$readiness = '{literal}' | ConvertFrom-Json\n"
                    "function Start-Process { param($FilePath); 'OPENED:' + $FilePath }\n"
                    "try {\n" + block + "\n} catch { 'REJECTED:' + $_.Exception.Message }\n"
                )
                result = subprocess.run(
                    ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual("OPENED:" in result.stdout, receipt == valid)
                self.assertNotIn("Compare this image", result.stdout)

    def test_login_reprompts_blank_invalid_ids_and_can_use_selected_subscription(self):
        source = (ROOT / "instructions" / "00-welcome-and-readiness.md").read_text(encoding="utf-8")
        block, = re.findall(r"```powershell\n(.*?)\n```", source, re.S)
        for selected, answers in (
            ("", ["", "not-a-guid", SUBSCRIPTION]), (SUBSCRIPTION, [""]),
            ("00000000-0000-0000-0000-000000000000", ["", "00000000-0000-0000-0000-000000000000", SUBSCRIPTION]),
        ):
            with self.subTest(selected=selected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "scripts").mkdir()
                (root / "scripts" / "start-lab.ps1").write_text(
                    "param($ResourceGroupName,$Region,$Mode)\n"
                    "'{\"infrastructure_ready\":true,\"outputs\":{\"marker\":\"VERIFIED\"}}'\n",
                    encoding="utf-8",
                )
                actual = block.replace(r"C:\Users\LabUser\code\ignite26-LAB722", str(root))
                script = (
                    f"$selected = '{selected}'\n"
                    f"$answers = [Collections.Generic.Queue[string]]::new([string[]]({json.dumps(answers).replace('[', '@(', 1).replace(']', ')')}))\n"
                    "$global:Prompts=0\n"
                    "function az { $global:LASTEXITCODE = 0; "
                    "if ($args[0] -ceq 'login' -and $env:AZURE_CORE_LOGIN_EXPERIENCE_V2 -cne 'off') { "
                    "throw 'The Azure CLI subscription selector must not add another prompt' }; "
                    "if ($args -contains 'id') { $selected } }\n"
                    "function Read-Host { $global:Prompts++; if ($answers.Count) { $answers.Dequeue() } else { '' } }\n"
                    + actual + "\n'CHOSEN:' + $env:AZURE_SUBSCRIPTION_ID\n'PROMPTS:' + $global:Prompts\n"
                )
                result = subprocess.run(
                    ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("CHOSEN:" + SUBSCRIPTION, result.stdout)
                self.assertEqual(result.stdout.count("Enter a valid, nonempty"), len(answers) - 1)
                self.assertIn(f"PROMPTS:{len(answers)}\n", result.stdout)

    def test_portal_registration_keeps_verified_handoff_or_clears_stale_bindings(self):
        source = (ROOT / "instructions" / "03-prepare-sandbox.md").read_text(encoding="utf-8")
        block = next(block for block in re.findall(r"```powershell\n(.*?)\n```", source, re.S)
                     if "$registered = .\\scripts\\connect-lab-workers.ps1" in block)
        for fail, catch_up in ((False, False), (False, True), (True, False)):
            with self.subTest(fail=fail, catch_up=catch_up), \
                    tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "scripts").mkdir()
                primary = "10000000-0000-0000-0000-000000000009" if catch_up else SUBSCRIPTION
                descriptor = root / "baseline-descriptor.json"
                descriptor.write_text(json.dumps({
                    "primary_id": primary, "snapshot_id": "10000000-0000-0000-0000-000000000003",
                    "dataset_version": "fixture",
                }), encoding="utf-8")
                bindings = root / "bindings.json"
                bindings.write_text("[]", encoding="utf-8")
                receipt = {
                    "descriptor": str(descriptor), "bindings": str(bindings),
                    "manifest": str(root / "data-manifest.json"), "primary_id": primary,
                    "descriptor_sha256": hashlib.sha256(descriptor.read_bytes()).hexdigest(),
                }
                (root / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
                helper = (
                    "param($PrimaryDescriptorPath,$PrimaryDescriptorSha256,[switch]$AsJson,[switch]$CatchUp)\n"
                    "if ($PrimaryDescriptorPath -cne 'PINNED_PRIMARY' -or "
                    "$PrimaryDescriptorSha256 -cne ('a'*64) -or -not $AsJson) { throw 'Lost primary pin or JSON mode' }\n"
                )
                helper += "throw 'Simulated rejected registration'\n" if fail else "Get-Content receipt.json -Raw\n"
                (root / "scripts" / "connect-lab-workers.ps1").write_text(helper, encoding="utf-8")
                location = str(root).replace("'", "''")
                actual = block.replace("-AsJson", "-CatchUp -AsJson") if catch_up else block
                script = (
                    f"Set-Location '{location}'\n"
                    "function Read-Host { throw 'Registration must not pause for Enter' }\n"
                    "$primaryDescriptorPath='PINNED_PRIMARY'; $primaryDescriptorSha256='a'*64\n"
                    "$baselineDescriptorPath=$bindingsPath=$baselineDescriptorSha256="
                    "$validationSandboxId=$preparedManifestPath='STALE'\n"
                    "try {\n" + actual + "\n'REGISTRATION:accepted'\n"
                    "} catch { 'REGISTRATION:rejected:' + $_.Exception.Message }\n"
                    "'HANDOFF:' + (ConvertTo-Json -Compress -InputObject @{\n"
                    "descriptor=$baselineDescriptorPath; sha256=$baselineDescriptorSha256; bindings=$bindingsPath\n"
                    "primary=$validationSandboxId; manifest=$preparedManifestPath })\n"
                )
                completed = subprocess.run(
                    ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                handoff = json.loads(next(
                    line.removeprefix("HANDOFF:") for line in completed.stdout.splitlines()
                    if line.startswith("HANDOFF:")
                ))
                if fail:
                    self.assertIn("REGISTRATION:rejected:Simulated rejected registration", completed.stdout)
                    self.assertTrue(all(value is None for value in handoff.values()))
                else:
                    self.assertIn("REGISTRATION:accepted", completed.stdout)
                    self.assertEqual(handoff, {
                        "descriptor": receipt["descriptor"], "sha256": receipt["descriptor_sha256"],
                        "bindings": receipt["bindings"], "primary": primary, "manifest": receipt["manifest"],
                    })

    def test_worker_gate_accepts_both_line_endings_but_pins_unmodified_original_bytes(self):
        source = (ROOT / "instructions" / "04-run-agent-team.md").read_text(encoding="utf-8")
        block = re.findall(r"```powershell\n(.*?)\n```", source, re.S)[0]
        run_id = "10000000-0000-0000-0000-000000000003"
        result = json.dumps({"plan": {"run_id": run_id}, "evidence": "original"}, indent=2)
        for line_ending, changed in (("\n", False), ("\r\n", False), ("\r\n", True)):
            with self.subTest(line_ending=line_ending, changed=changed), \
                    tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = root / ".validation-workspaces" / "agent-runs" / run_id
                directory.mkdir(parents=True)
                saved = result.replace("original", "changed") if changed else result
                original_bytes = saved.replace("\n", line_ending).encode("utf-8")
                artifact = directory / "worker-result.json"
                artifact.write_bytes(original_bytes)
                (root / "stdout.json").write_bytes(result.encode("utf-8"))
                location = str(root).replace("'", "''")
                script = (
                    f"Set-Location '{location}'\n"
                    "function Read-Host { '' }\n"
                    "function Invoke-ControllerFixture { $global:LASTEXITCODE=0; "
                    "Get-Content -LiteralPath 'stdout.json' }\n"
                    "$controllerPython='Invoke-ControllerFixture'; $controllerArgs=@(); "
                    "$resultSha256='stale-hash'\n"
                    "try {\n" + block + "\n'GATE:accepted'\n"
                    "} catch { 'GATE:rejected:' + $_.Exception.Message }\n"
                    "'SHA:' + $resultSha256\n"
                )
                completed = subprocess.run(
                    ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                if changed:
                    self.assertIn("GATE:rejected:The saved result does not match", completed.stdout)
                    self.assertIn("SHA:\n", completed.stdout)
                    self.assertNotIn("stale-hash", completed.stdout)
                else:
                    self.assertIn("GATE:accepted", completed.stdout)
                    self.assertIn("SHA:" + hashlib.sha256(original_bytes).hexdigest(), completed.stdout)
                self.assertEqual(artifact.read_bytes(), original_bytes)

    def test_pasted_login_block_keeps_interactive_answers_and_cross_page_variables_separate(self):
        source = (ROOT / "instructions" / "00-welcome-and-readiness.md").read_text(encoding="utf-8")
        block, = re.findall(r"```powershell\n(.*?)\n```", source, re.S)
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            (fixture / "scripts").mkdir()
            (fixture / "scripts" / "start-lab.ps1").write_text(
                "param($ResourceGroupName,$Region,$Mode)\n"
                "'{\"infrastructure_ready\":true,\"outputs\":{\"marker\":\"VERIFIED_SCOPE\"}}'\n",
                encoding="utf-8",
            )
            block = block.replace(r"C:\Users\LabUser\code\ignite26-LAB722", str(fixture))
            prelude = (
                "function az { $global:LASTEXITCODE=0; "
                "if ($args[0] -eq 'login') { "
                "$answer=Read-Host 'SIMULATED_AZURE_LOGIN'; "
                "if ($answer -cne 'LOGIN_COMPLETE') { throw ('Queued commands entered the login prompt: [' + $answer + \"]\") } "
                "} }\n"
            )
            continuation = (
                'Write-Output ("NEXT_PAGE:" + $resourceGroupName + ":" + $region + ":" + '
                '$labOutputs.marker + ":" + $env:AZURE_SUBSCRIPTION_ID)\nexit\n'
            )
            result = subprocess.run(
                ["pwsh", "-NoLogo", "-NoProfile", "-Command", "-"],
                input=prelude + block + "\n\nLOGIN_COMPLETE\n" + SUBSCRIPTION + "\n" + continuation,
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Queued commands entered", result.stderr)
            self.assertIn(f"NEXT_PAGE:LAB722:westus3:VERIFIED_SCOPE:{SUBSCRIPTION}", result.stdout)
            self.assertIn("True", result.stdout)


if __name__ == "__main__":
    unittest.main()
