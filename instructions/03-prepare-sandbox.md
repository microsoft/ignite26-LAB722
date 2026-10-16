# Segment 3 - Prepare the Sandbox (target: 15 minutes)

**Goal:** establish one prepared primary, its snapshot and three distinct role clones. **Why:** matching frozen inputs and protected tooling make worker output comparable. **Services:** ACA Sandboxes and the prebuilt source/data bundle. **Outcome:** verified controller bindings, full frozen identity and a genuine missing-function baseline before new implementation.

Preparation uses the existing tested source importer and prebuilt toolchains. It does not download the 7.07 GiB raw database into a Sandbox, restore arbitrary packages over a widened allowlist or clone unpinned source.

For the new live path, the clean VM snapshot already carries the checkout and v2 dataset. The offline data-staging handoff is separate from this exercise: **you still explicitly prepare the primary, snapshot it and create the three role clones here**. Platform startup must not silently consume those steps.

## Recorded-evidence path

```powershell
$evidence.baseline | Format-List
$evidence.workers | Format-Table role, sandbox_id
$evidence.dataset | Format-List
```

The sample's baseline descriptor has mode `Reuse`: its pinned inputs were verified without resetting completed worker code. It is not proof that today's workers are still untouched starters. The preserved prepared snapshot precedes implementation; the controller transfers only the two assigned feature modules into the independent primary.

The verification boundary includes UID 10001, the fixed `/opt/caldova-lab` workspace, protected tests/data/frontend, Python/Node toolchains, snapshot lineage and explicit network/lifecycle settings. The retained public baseline was checked before snapshotting and cloning; later code-preserving reuse permits completed feature functions.

## Live-exercise path

The facilitator authorizes preparation only in an available group with **four free Sandbox slots**. Stopped Sandboxes still consume slots. Both retained maintainer groups are full; do not use their IDs, delete resources or raise capacity to complete this page.

With the complete harness-owned development pins from Segment 0 and authorization for allocation, run:

```powershell
$preparedText = .\scripts\start-lab.ps1 -ResourceGroupName $resourceGroupName `
    -Region $region -Mode Prepare
$prepared = $preparedText | ConvertFrom-Json
if (-not $prepared.baseline_ready -or -not $prepared.frozen_data_verified) {
    throw 'Primary/clone preparation did not establish a verified baseline.'
}
$baselineDescriptorPath = $prepared.outputs.CALDOVA_BASELINE_DESCRIPTOR_PATH
$bindingsPath = $prepared.outputs.CALDOVA_WORKER_BINDINGS_PATH
$preparedManifestPath = $prepared.outputs.CALDOVA_DATA_MANIFEST_PATH
$validationSandboxId = $prepared.outputs.CALDOVA_VALIDATION_SANDBOX_ID
$baselineDescriptor = Get-Content -LiteralPath $baselineDescriptorPath -Raw | ConvertFrom-Json
$bindings = Get-Content -LiteralPath $bindingsPath -Raw | ConvertFrom-Json
$bindings | Format-Table role, sandbox_id, snapshot_id, workspace
$baselineDescriptor | Select-Object primary_id, snapshot_id, source_revision, dataset_version
```

The helper verifies scope and capacity before import/allocation, stages exact frozen bytes, creates the primary, verifies genuine missing functions and protected inputs, snapshots it, creates three clones and verifies their lineage/policies. Snapshot clones inherit resources; do not add CPU/memory overrides to snapshot creation.

Open `http://sandboxes.azure.com/` and select the allocated group. Compare the exact primary/snapshot/clone IDs to the report. Inspect default-deny egress, the `open.fda.gov` allow entry, Full traffic inspection, 900-second Memory suspension and disabled auto-delete. Do not manually broaden these policies or reinstall dependencies.

`Prepare` does not deploy the application or authorize attendee data release. If it fails after a submitted import/allocation, the operation may still have completed: the facilitator inspects exact scoped metadata before recovery. Never repeat preparation blindly or adopt a failed import as successful. The retained test run required scoped recovery; a fresh complete preparation dry run is still unmeasured.

## Checkpoint

Each role has exactly one distinct clone of the same snapshot, plus a separate trusted primary. The supplied manifest/DB/original JSON/pipeline ZIP identities match the prepared descriptor, and a new live baseline reproduces genuinely missing functions before implementation.

| Symptom | Safe response |
|---|---|
| Capacity is full | Stop; facilitator supplies an explicitly authorized available scope |
| A hash, clone lineage or policy differs | Retain the mismatch; do not replace the trust anchor or choose another clone |
| Import timed out after submission | Inspect that exact operation and unique disk name; do not reimport automatically |
| A reused worker already has code | Treat it as completed state; reuse is not a missing-function test or permission to reset |
