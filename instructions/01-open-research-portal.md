# Segment 1 - Open the research portal (target: 4 minutes)

**Goal:** distinguish the observable starter from a completed reference. **Why:** already-implemented code or a healthy page cannot prove an untouched baseline. **Services:** ACA Express and the frozen local data/API. **Outcome:** an exact URL/image/state observation, labeled recorded or checked now.

The retained public preview is a completed `reference`, not a participant starter. Do not relabel it, switch revisions or change environment variables to pass a starter checkpoint.

## Recorded-evidence path

```powershell
$evidence.application_observation | Format-List
$evidence.image | Format-List digest, reference
```

Record the observation time and `reference` state. The visible panel was already implemented when this observation was made. An actual starter returns `status=unavailable` with empty trial/report arrays; the prepared worker baseline separately proves that its two query functions are genuinely missing.

If network access is available, you may inspect the recorded public URL without changing it. This request checks current API data/state, not the active image or a new full acceptance run:

```powershell
$url = $evidence.application_observation.url
$metadata = Invoke-RestMethod "$url/api/metadata" -TimeoutSec 20
if ($metadata.manifest.dataset_version -cne $evidence.dataset.dataset_version -or
    $metadata.manifest.logical_sha256 -cne $evidence.dataset.logical_sha256) {
    throw 'The current API data differs from the recorded sample.'
}
$candidateId = [uri]::EscapeDataString($metadata.candidates[0].candidate_id)
$sample = Invoke-RestMethod "$url/api/research?candidate=$candidateId" -TimeoutSec 20
$sample | Select-Object status, dataset_version, limitations, fixture_warning
```

Change the trial topic in the UI and notice that safety-report candidate mentions remain condition-independent. Tirzepatide's selected public shard has no retained safety reports; empty coverage is not an error and does not establish comparative safety. A failed network request simply leaves the recorded observation available with its original time.

## Live-exercise path

Retain `$readiness` from Segment 0. The facilitator supplies a separately approved, pre-provisioned starter; opening the portal does not create an app or authorize image replacement.

1. Open `https://containerapps.azure.com/` in the supplied authorized identity/scope.
2. Select the exact app named by `$readiness.outputs.CALDOVA_APPLICATION_NAME`.
3. Compare the complete digest-pinned image to `$readiness.outputs.CALDOVA_APPLICATION_IMAGE`.
4. Open the report's URL and confirm the panel is unavailable while provenance/limitations remain visible.

```powershell
if (-not $readiness.application_ready -or
    $readiness.application.preview_state -cne 'starter') {
    throw 'The verified application is not a starter. Stop without changing it.'
}
$url = $readiness.outputs.CALDOVA_APPLICATION_URL
$metadata = Invoke-RestMethod "$url/api/metadata" -TimeoutSec 20
$candidateId = [uri]::EscapeDataString($metadata.candidates[0].candidate_id)
$sample = Invoke-RestMethod "$url/api/research?candidate=$candidateId" -TimeoutSec 20
if ($sample.status -cne 'unavailable' -or @($sample.trials).Count -ne 0 -or
    @($sample.safety_reports).Count -ne 0 -or
    $sample.dataset_version -cne $readiness.application.identity.dataset_version) {
    throw 'Starter state or data identity changed. Retain the response and stop.'
}
```

The starter's unavailable UI is not the missing-function source check. Segment 3 verifies the worker baseline's source, UID, protected files, policy and snapshot lineage independently.

## Checkpoint

You can explain why the recorded reference is useful demonstration evidence but cannot substitute for the new starter or worker-baseline verification.

| Symptom | Safe response |
|---|---|
| App is not listed | Facilitator resolves identity/subscription/group; do not create another app |
| A supposed starter shows evidence | Compare expected state/digest; stop rather than accepting completed code |
| UI and API disagree | Reload the same verified URL; persistent mismatch stops the live checkpoint |
| Recorded URL is unavailable | Continue recorded inspection with its timestamp; do not claim current health |
