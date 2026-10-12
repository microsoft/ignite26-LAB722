# Segment 6 - Trace the evidence (target: 7 minutes)

**Goal:** audit the chain from the run and frozen inputs to the recorded image, human approval and application observation. **Why:** model confidence and a green portal are not a reproducible release decision. **Services:** the offline receipt viewer, ACR/ACA records and optionally a fresh read-only startup check. **Outcome:** an explainable integrity chain with explicit missing evidence and freshness limits.

There is no implemented Azure Monitor correlation workbook in this repository. This segment uses the real checksummed workflow receipts, not a promised dashboard or invented event/session identifiers. Infrastructure monitoring resources do not mean every desired event has been emitted.

## Recorded-evidence path

Open the self-contained viewer verified in Segment 0:

```powershell
Start-Process (Join-Path $evidenceDirectory 'development-evidence.html')
$evidence.receipt_sha256 | Format-List
$evidence.application_observation | Format-List
$evidence.not_evidenced
```

Follow one run through the viewer's tables: dataset/manifest/logical identity, source revision, baseline snapshot and independent primary, three role assignments, 11 check categories, two accepted source hashes, published image/ACR run, separate human approval, and timestamped application observation.

The bundled sample is a reduced, integrity-checked projection of the real development receipts. It does not contain candidate code, raw logs, the full source dataset or authentication material. Its timestamp records when the application was checked; opening the HTML does **not** check the application again.

## Inspect original receipts when supplied

The facilitator can supply the original result, baseline descriptor/prepared file, local four-file frozen package, image descriptor, separate approval and startup observation, with independent trust anchors. Run the stdlib-only inspector; optional later-stage receipts must each be supplied with their pin:

```powershell
$inspectionArgs = @(
    '.\src\workers\inspect_evidence.py'
    '--result', $resultPath, '--result-sha256', $resultSha256
    '--baseline-descriptor', $baselineDescriptorPath
    '--baseline-descriptor-sha256', $baselineDescriptorSha256
    '--manifest', $env:LAB_DATA_MANIFEST
    '--manifest-sha256', $env:LAB_DATA_MANIFEST_SHA256
    '--purpose', $env:LAB_STARTUP_PURPOSE
)
$summaryText = & python @inspectionArgs
if ($LASTEXITCODE -ne 0) { throw 'Receipt integrity or cross-run identity failed.' }
$summary = ($summaryText -join "`n") | ConvertFrom-Json
$summary.checks | Format-Table name, passed, exit_code, sandbox_id
$summary.missing_stages
```

This minimal invocation validates the accepted workflow but honestly lists later stages as absent. To include them, the facilitator appends `--image-descriptor`/`--image-descriptor-sha256`, `--approval`/`--approval-sha256`, and `--startup-receipt`/`--startup-receipt-sha256`. `--format html` produces the same validated projection for local viewing. A checksum calculated from an untrusted file is not an independent approval or trusted download verification.

The inspector performs no network operation or candidate execution, authenticates no approver, reruns no acceptance tests and grants no release. It rejects missing/modified/foreign identity pins and widened historical flags. Raw output hashes bind the recorded controller checks; the viewer does not possess/replay every raw output. GitHub issue IDs, Foundry session IDs and detailed token/timing telemetry are not stored in this accepted-result contract and remain explicitly unevidenced.

## Checkpoint

Use the worksheet to distinguish:

- Verified integrity of caller-pinned bytes vs a signed/authenticated authorization.
- Recorded check categories vs a new acceptance run.
- A timestamped application observation vs current live health.
- Named development approval vs attendee release.

| Symptom | Safe response |
|---|---|
| Optional stage is absent | Record it as missing; do not borrow a receipt from another run |
| Hash or image/run identity differs | Stop and retain the mismatch; do not hash the new file and call it approved |
| A live check cannot be made | Use recorded evidence with its time/freshness label, not a claim of current health |
| No token/session/workbook detail exists | State the limitation; monitoring resources alone cannot manufacture it |
