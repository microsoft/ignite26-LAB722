# Segment 5 - Build and publish (target: 6 minutes)

**Goal:** connect accepted source to a validated immutable image and separately approved development deployment. **Why:** a tag or model's recommendation cannot identify the exact approved artifact. **Services:** ACR Tasks and ACA Express. **Outcome:** recorded image/build/approval/application identities, or a newly validated result when the facilitator runs the authorized path.

Six minutes is an unmeasured delivery target, not a guarantee that a fresh remote build completes in that time. Guided delivery may inspect the already-completed build while the facilitator stages another authorized run; it must label that evidence as recorded.

## Recorded-evidence path

```powershell
$evidence.candidate_sources | Format-List
$evidence.image | Format-List registry, repository, digest, acr_run_id, reference
$evidence.human_approval | Format-List
$evidence.application_observation | Format-List
$evidence.pipeline_provenance
```

The accepted public result was validation-built with `--no-push`, then separately authorized for publication. Publication run `dsn` passed all eight public tests and produced digest `sha256:e219757d2f40dd83f5445ea661aa8f56e9ff53864d34127b74acc7570306bd38`. A later human confirmation bound the exact run, logical dataset identity and digest for development deployment.

Distinguish four boundaries: source-use authorization, candidate validation, publication authorization, and exact-image deployment approval. A `--no-push` build has no deployable digest. Build-time descriptors keep `human_approval=false`, `release_approved=false` and `deployed=false`; later approvals/observations are separate records, not rewritten history.

## Live-exercise path

Publication and deployment are facilitator operations until a generalized participant adapter is validated. The current candidate helper deliberately restricts registry/subscription/repository to the authorized maintainer scope; this is not a portable per-attendee publisher. Never enter maintainer IDs into an unrelated participant scope.

In the authorized maintainer environment only, the facilitator can stage an accepted result without cloud activity. All variables come from the newly accepted run and independently trusted pins:

```powershell
$packageArgs = @{
    ResultPath = $resultPath
    ResultSha256 = $resultSha256
    BaselineDescriptorPath = $baselineDescriptorPath
    FrozenArtifactDirectory = (Split-Path -Parent $env:LAB_DATA_MANIFEST)
    ManifestSha256 = $env:LAB_DATA_MANIFEST_SHA256
    ApprovedRunId = [guid] $runId
    Purpose = $env:LAB_STARTUP_PURPOSE
    RegistryName = $readiness.outputs.AZURE_CONTAINER_REGISTRY_NAME
    SubscriptionId = [guid] $readiness.outputs.AZURE_SUBSCRIPTION_ID
    Tag = ('participant-' + $runId)
}
$destination = Join-Path '.build-contexts' ('participant-stage-' + [guid]::NewGuid().ToString('N'))
$stage = .\scripts\build-agent-candidate.ps1 @packageArgs -Destination $destination -StageOnly
$stage | Format-List
```

`ApprovedRunId` selects the accepted source; it is **not human release approval**. Staging executes no candidate code on the host. It verifies original result bytes, baseline/protected source, all frozen files and accepted module hashes. The container is where candidate code and the dataset-specific suite execute.

The facilitator next runs the documented [candidate build and approval sequence](../scripts/README.md#agent-built-candidate). A non-`StageOnly` helper invocation stages into a **new** destination, runs container acceptance and publishes a new tag; it needs prior publication authorization. Do not overwrite or reuse the existing stage directory. Preserve the returned ACR run and exact digest, record separate image-bound approval, then authorize `deploy-research-preview.ps1` for the exact development image.

That deployment helper may create/refresh a repository-scoped pull credential and update the application. It is not a read-only action and must not be run merely because the model recommends release. Re-run pinned `Readiness` with the newly approved digest/reference state to establish the live image/data observation. Full API/runtime acceptance remains separate from this readiness sample.

Open `https://containerapps.azure.com/` in the authorized scope and compare the exact image/app/URL to the returned records. The public preview reads frozen local data: absence of a live safety API call is expected, and tirzepatide's empty report selection is not an error.

## Checkpoint

The accepted module hashes, dataset identity, build result, published digest, separate human approval and application observation all agree. The current public pipeline records `uncommitted-development`; development approval does not make it attendee-releasable or transform the ZIP into a committed pipeline.

| Symptom | Safe response |
|---|---|
| Build is incomplete or log streaming fails | Inspect the existing ACR run; do not queue another build merely to retrieve logs |
| Only a no-push result is available | No deployment; there is no published immutable digest |
| Approval refers to another run/dataset/digest | Stop; an old approval cannot authorize a new image |
| Image differs from the verified app | Preserve the mismatch; facilitator inspects the exact operation rather than switching tags or revisions |
