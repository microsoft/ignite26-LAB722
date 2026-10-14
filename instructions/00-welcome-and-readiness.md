# Segment 0 - Welcome and readiness (target: 5 minutes)

**Goal:** choose recorded evidence or an authorized live exercise and identify the pinned inputs. **Why:** results from different runs, images or datasets cannot fill one acceptance chain. **Services:** the local evidence package, or scoped Azure CLI/ACA readiness for the live path. **Outcome:** an explicit execution path and recorded run/data identities.

The [Skillable panel manual](skillable.md) supplies the prepared Windows VM login and checkout steps. Azure identity, live startup triggers and output mapping still require the facilitator's verified handoff. No platform account is needed for the standalone recorded path. All segment timings are targets, not measured participant results.

## Task 1 - Review the request

Read [the lab overview](README.md). Caldova is fictional. Clinical and safety specialists implement two bounded query functions; governance checks the independently integrated result. All use the same frozen data and protected acceptance criteria.

Trial-topic filtering and candidate mentions in adverse-event reports are independent. Do not link trials to reports or interpret counts as causation, incidence, comparative safety or treatment advice. Record an actual GitHub issue if one is supplied; the accepted-result contract does not pin an issue identifier.

## Task 2 - Verify the recorded package (default path)

Open PowerShell 7.2+ at the repository root and retain these variables for subsequent segments:

```powershell
$evidenceDirectory = Join-Path (Get-Location).Path 'instructions\assets'
$bundleManifest = Get-Content -LiteralPath (Join-Path $evidenceDirectory `
    'development-evidence-manifest.json') -Raw | ConvertFrom-Json -AsHashtable
$expectedFiles = @('development-evidence.json', 'development-evidence.html')
if ($bundleManifest.files.Count -ne 2 -or
    @($bundleManifest.files.Keys | Where-Object { $_ -cnotin $expectedFiles }).Count) {
    throw 'Unexpected evidence file inventory.'
}
foreach ($name in $expectedFiles) {
    $path = Join-Path $evidenceDirectory $name
    $expected = $bundleManifest.files[$name]
    $actualHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-Item -LiteralPath $path).Length -ne $expected.bytes -or
        $actualHash -cne $expected.sha256) {
        throw "Recorded evidence changed: $name"
    }
}
$evidence = Get-Content -LiteralPath (Join-Path $evidenceDirectory `
    'development-evidence.json') -Raw | ConvertFrom-Json
$evidence | Select-Object status, run_id, worker_blockers, current_live_state_checked, attendee_ready
$evidence.dataset | Format-List
```

The bundle is an integrity-checked projection of the accepted development receipts, not a new test run or signed release. Its HTML is self-contained; it includes no candidate executable code, raw dataset, credentials or external assets. Checksums verify consistency with the supplied manifest, not the authenticity of an arbitrary download. Keep `recorded` beside the worksheet entries.

## Optional live readiness

Use only facilitator-supplied authentication and allocated scope. The harness/facilitator owns the [complete immutable app/data pins](../scripts/README.md#pinned-application-readiness); they are not extra participant deployment inputs. Do not select a maintainer subscription, infer your identity or provision infrastructure on this page.

The prepared VM includes the pinned four-file v2 dataset, not the raw source databases. The facilitator/harness can call `.\scripts\stage-lab-data.ps1 -ConfigureSession` to verify/reuse it and set the current process's existing data pins without Azure calls. This does not create worker Sandboxes or make an old v1 image compatible with v2.

```powershell
$resourceGroupName = Read-Host 'Allocated resource-group name'
$region = Read-Host 'Workload region'
$readiness = .\scripts\start-lab.ps1 -ResourceGroupName $resourceGroupName `
    -Region $region -Mode Readiness | ConvertFrom-Json
$readiness | Select-Object infrastructure_ready, application_ready, `
    application_manifest_verified, frozen_data_verified, baseline_ready, data_ready, attendee_ready
$readiness.pending_reasons
```

`Readiness` creates no resources, changes no image/credentials and performs no inference. It verifies six current infrastructure resources. With complete app pins it checks the scoped app/Express/registry image, HTTPS health, exact local frozen bytes, live manifest/original sources and one ready/unavailable sample.

Stop live execution if infrastructure, application, manifest or frozen-data verification fails. `baseline_ready=false` means this invocation did not inspect a worker baseline. `data_ready=false` and `attendee_ready=false` explicitly preserve the unfinished release/platform gates; a development reference cannot authorize an event release. The recorded path remains usable without changing those flags. A separately authorized facilitator rehearsal follows [the handoff checklist](facilitator.md), never an assumed event identity.

## Checkpoint

Record the execution path, run, dataset, manifest/logical hashes and pipeline provenance. Recorded v1 evidence honestly retains `uncommitted-development`; the new v2 manifest binds source bytes to its recorded full Git commit. Do not substitute the current checkout `HEAD` or combine either version's receipts.

| Symptom | Safe response |
|---|---|
| Bundled file checksum differs | Stop and obtain the intended materials version; do not rewrite the manifest |
| No application settings are supplied | `Readiness` remains infrastructure-only; use recorded evidence or have the facilitator supply trusted pins |
| Image/source/manifest differs | Retain the mismatch; no fixture fallback or new trust anchor |
| A submitted deployment times out | Facilitator inspects that scoped operation; timeout is not cancellation |
