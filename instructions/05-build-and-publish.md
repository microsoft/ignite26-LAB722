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

The default live path builds the accepted agent source in **your allocated ACR**, not Simon's shared registry. Supply the explicit subscription/resource group/registry from readiness; the helper validates that current LAB722 scope before any build. Publication and exact-image deployment still need the facilitator's explicit authorization. Never enter maintainer IDs into an unrelated participant scope.

You can first stage an accepted result without cloud activity. All variables come from the newly accepted run and independently trusted pins:

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
    ResourceGroupName = $resourceGroupName
    Tag = ('participant-' + $runId)
}
$destination = Join-Path '.build-contexts' ('participant-stage-' + [guid]::NewGuid().ToString('N'))
$stage = .\scripts\build-agent-candidate.ps1 @packageArgs -Destination $destination -StageOnly
$stage | Format-List
```

`ApprovedRunId` selects the accepted source; it is **not human release approval**. Staging executes no candidate code on the host. It verifies original result bytes, baseline/protected source, all frozen files and accepted module hashes. The container is where candidate code and the dataset-specific suite execute.

Next follow the documented [portable build and approval sequence](../scripts/README.md#portable-image-and-data-delivery). A non-`StageOnly` helper invocation stages into a **new** destination, runs container acceptance and publishes a new tag; it needs prior publication authorization. Do not overwrite or reuse the existing stage directory/tag. Preserve the returned ACR run and exact digest, record separate image-bound approval, then call `deploy-research-preview.ps1` with the allocated scope, Express environment and `-AuthorizeDeployment`.

If the facilitator supplies a known-working reference digest and pull access, the optional `-ImageSource SimonRegistry` path deploys `simon.azurecr.io/lab722-$AppName@sha256:...`. Label the result **reference deployment**: it does not publish your agents' newly generated functions. No shared reference image is assumed present, and no learner write access to Simon's registry is required or granted.

That deployment helper may create/refresh a repository-scoped pull credential and update the application. It is not a read-only action and must not be run merely because the model recommends release. Re-run pinned `Readiness` with the newly approved digest/reference state to establish the live image/data observation. Full API/runtime acceptance remains separate from this readiness sample.

Open `https://containerapps.azure.com/` in the authorized scope and compare the exact image/app/URL to the returned records. The public preview reads frozen local data: absence of a live safety API call is expected, and tirzepatide's empty report selection is not an error.

## Recovery - Use the ready-made reference image

If your image build is blocked by tooling, build capacity or time, ask the facilitator for the **ready-made v2 reference digest** and confirmed pull access. Keep the failed run's evidence; do not repeatedly queue builds. If the facilitator has not supplied a published, tested image, use the recorded-evidence path instead of guessing a tag or digest.

After explicit deployment authorization, use the same allocated infrastructure and frozen v2 data:

```powershell
$referenceTarget = @{
    SubscriptionId = [guid] $readiness.outputs.AZURE_SUBSCRIPTION_ID
    ResourceGroupName = $resourceGroupName
    RegistryName = $readiness.outputs.AZURE_CONTAINER_REGISTRY_NAME
    ExpressEnvironmentName = $readiness.outputs.EXPRESS_ENVIRONMENT_NAME
}
$referenceDeployment = .\scripts\deploy-research-preview.ps1 @referenceTarget `
    -ImageSource SimonRegistry -AppName caldova-research `
    -ImageDigest $approvedReferenceDigest -PreviewState reference -AuthorizeDeployment
$referenceDeployment | Format-List
$env:LAB_APPLICATION_NAME = $referenceDeployment.AppName
$env:LAB_APPLICATION_IMAGE_SOURCE = 'SimonRegistry'
$env:LAB_APPLICATION_IMAGE_DIGEST = $approvedReferenceDigest
$env:LAB_APPLICATION_PREVIEW_STATE = 'reference'
$readiness = .\scripts\start-lab.ps1 -ResourceGroupName $resourceGroupName `
    -Region $region -Mode Readiness | ConvertFrom-Json
```

`$approvedReferenceDigest` is the facilitator's independently verified immutable digest, not one discovered from an untrusted endpoint. The private registry needs facilitator-provided read-only pull credentials in the current process; do not enter registry admin credentials, request writes in Simon's registry, or put passwords in commands, files or the VM snapshot. Stop if pull access was not supplied.

Record **ready-made reference** in the worksheet and continue inspecting the UI and reference evidence. This does not make your own source/build accepted, repair a failed agent run, or transfer another run's approval. Scope, permission, checksum and acceptance failures still require facilitator investigation. If your own image is later approved, return `LAB_APPLICATION_IMAGE_SOURCE` to `LabRegistry` and pin that different digest before checking readiness again.

## Checkpoint

For a participant-built image, accepted module hashes, dataset identity, build result, published digest, separate approval and application observation agree. For the optional reference, record its different provenance explicitly. Recorded v1 evidence retains its working-tree identity; v2 has its own committed pipeline and must produce a new image/run chain.

| Symptom | Safe response |
|---|---|
| Build is incomplete or log streaming fails | Inspect the existing ACR run; do not queue another build merely to retrieve logs |
| Only a no-push result is available | No deployment; there is no published immutable digest |
| Local tooling/build capacity prevents publication | With facilitator approval, use the ready-made v2 reference above; otherwise continue with explicitly recorded evidence |
| Reference digest or private pull access is missing | Stop and contact the facilitator; no guessed image, admin credential or implicit public pull |
| Approval refers to another run/dataset/digest | Stop; an old approval cannot authorize a new image |
| Image differs from the verified app | Preserve the mismatch; facilitator inspects the exact operation rather than switching tags or revisions |
