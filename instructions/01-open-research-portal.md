# 4. Deploy the yet incomplete Caldova Research Portal with Express

The lab includes a fixed sample, **dataset v2**, with **168 clinical trials and 38 adverse-event reports**. Every agent uses the same files, so you can compare their results without changes to the underlying data.

Trial records come from an [AACT-derived dataset](https://aact.ctti-clinicaltrials.org/landing); adverse-event records come from an [openFDA drug adverse-event export](https://open.fda.gov/apis/drug/event/). These links explain the original sources; this lab uses selected, frozen records, not live API queries or a complete view of a drug's safety or effectiveness.

## 4.1 Create your application in the portal

You will deploy a public starter image we've prepared for you. It already contains the UI, runtime and fixed data, but its two research-query functions are genuinely missing. No registry account or image build is needed for this first deployment.

**Read these settings before running the helper.** The portal fills in a generated app name and a **new** resource group. You must replace both defaults; a running app with a different name or resource group will not be found by the lab.

1. Run the helper below to prepare your local data, copy the starter image and open the portal. Leave PowerShell waiting while you complete the form.
2. Sign in with your lab's Azure account. Select **Create** or **Create New App**, then **Express**, not Standard. Select **Docker Hub / Other** and use these settings:

| Setting | Value |
|---|---|
| App Name | Replace `container-app-...` with **`caldova-research`** |
| Subscription | Your allocated subscription from Resources |
| Resource Group | Select existing **`LAB722`**, not the generated `rg-...` or a new group |
| Region | **West US 3**, matching your lab infrastructure |
| Image | Paste the copied `acateam.azurecr.io/lab722/caldova-research:starter-v2-20261030` reference |
| Public access / external ingress | Enabled |
| Target port | `8080` |

3. Keep the default CPU and memory. Do not supply registry credentials or override the image's startup command.
4. Open **Review**. Check **App name = `caldova-research`**, **Resource group = `LAB722`**, your allocated subscription, the starter image and external ingress on port `8080` **before** submitting. If the review shows generated names, return to the form and correct them.
5. Select **Create** / **Deploy** and wait for the app to be running. Return to PowerShell and press **Enter** to authorize same-app digest pinning. This changes only the supplied image tag to its immutable digest; it does not create another app or move it.

The helper stages the local frozen dataset before opening the portal. After your confirmation, it pins and verifies the existing application. If portal creation itself is blocked, use the explicit fallback described below.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $images = Get-Content '.\data\lab-images.json' -Raw | ConvertFrom-Json
    $readiness = $plan = $controllerArgs = $null
    . "$env:LOCALAPPDATA\Caldova\venvs\application\Scripts\Activate.ps1"
    .\scripts\stage-lab-data.ps1 -ConfigureSession | Out-Null
    $starterImage = '{0}/{1}:{2}' -f $images.registry, $images.repository, $images.images.starter.tag
    $starterImage
    Set-Clipboard -Value $starterImage
    Start-Process 'https://containerapps.azure.com/apps'
    $starterAction = Read-Host 'When caldova-research is running in existing resource group LAB722, press Enter; if portal creation is blocked, type fallback'
    if ($starterAction -ceq 'fallback') {
        $starterTarget = @{
            SubscriptionId = [guid] $env:AZURE_SUBSCRIPTION_ID
            ResourceGroupName = $resourceGroupName
            ExpressEnvironmentName = $labOutputs.EXPRESS_ENVIRONMENT_NAME
            Region = $region
        }
        $starterImage | Out-Host
        $starterTarget | Format-List | Out-Host
        [void] (Read-Host 'Review the starter image and existing target above, then press Enter to create it once')
        .\scripts\deploy-lab-starter.ps1 @starterTarget -AuthorizeDeployment | Format-List | Out-Host
    }
    elseif ($starterAction -cne '') { throw 'Expected Enter or fallback. No starter fallback was run.' }
    .\scripts\deploy-lab-starter.ps1 `
        -SubscriptionId ([guid] $env:AZURE_SUBSCRIPTION_ID) -ResourceGroupName $resourceGroupName `
        -RegistryName $labOutputs.AZURE_CONTAINER_REGISTRY_NAME -PinExisting -AuthorizeDeployment |
        Format-List | Out-Host
    $env:LAB_APPLICATION_NAME = $images.application_name
    $env:LAB_APPLICATION_IMAGE_SOURCE = 'ReferenceRegistry'
    $env:LAB_APPLICATION_IMAGE_DIGEST = $images.images.starter.digest
    $env:LAB_APPLICATION_PREVIEW_STATE = 'starter'
    $env:LAB_APPLICATION_ENVIRONMENT_SOURCE = 'Portal'
    $readiness = $null
    $readiness = .\scripts\start-lab.ps1 -ResourceGroupName $resourceGroupName `
        -Region $region -Mode Readiness | ConvertFrom-Json
    if (-not $readiness.application_ready -or -not $readiness.application_manifest_verified -or
        -not $readiness.frozen_data_verified) { throw 'The starter image or data check failed.' }
    $labOutputs = $readiness.outputs
    $readiness | Select-Object application_ready, application_manifest_verified, frozen_data_verified
}
```

**Expected:** all three check values are `True`. The helper stages the same fixed data locally and verifies the exact running image digest, starter state and data. It checks that the app and its healthy Express environment are in your allocated subscription/resource group and in the same region as each other, then retains the actual target for later updates. This does not test the agents' Foundry or Sandbox access.

**If creation or verification fails**, stop here; do not continue to planning or Sandbox preparation. Keep the error and contact your instructor. If the app was created with generated names or a different resource group, preserve it and agree on recovery with your instructor. After the intended `caldova-research` exists in `LAB722`, rerun this helper and require all three checks to pass. It will not recreate an app or repin an already pinned starter. Do not select a different image, change permissions, or create a second app to hide the failure.

**Only if portal creation is blocked:** cancel the unsubmitted form. At the waiting PowerShell prompt, type **fallback**, inspect the printed starter image and existing allocated Express target, then press **Enter** to authorize creation. The CLI fallback uses the pinned digest and creates the starter **once** in that existing environment. It refuses any existing `caldova-research` and never creates an environment, changes roles or retries a failed submission.

<!-- pagebreak -->

# 5. Explore the Research Portal

The previous helper already compared the app's configured container-image digest with the supplied starter. This is a comparison of **container image identities**, not the website's visual appearance; you do not need to repeat it manually.

Open the verified application:

```powershell
. {
    $ErrorActionPreference = 'Stop'
    if (-not $readiness -or -not $readiness.application_ready -or
        -not $readiness.application_manifest_verified -or -not $readiness.frozen_data_verified -or
        -not $readiness.outputs -or
        [string]::IsNullOrWhiteSpace($readiness.outputs.CALDOVA_APPLICATION_IMAGE) -or
        [string]::IsNullOrWhiteSpace($readiness.outputs.CALDOVA_APPLICATION_URL)) {
        throw 'Complete the previous starter image/data verification successfully before opening the application.'
    }
    $url = $readiness.outputs.CALDOVA_APPLICATION_URL
    Start-Process $url
}
```

Select a **Research Candidate** and a **Trial Condition**. Notice the message **The research panel is not available in this preview**. The two query functions have not been implemented yet. Find the data-source and limitations information; it should remain visible even while the panel is unavailable.

The agents will fill in the missing trial and safety queries. Later, you will deploy their implementation and return to this same application.

**Checkpoint:** you can identify the missing functionality and the application that your team will update. If results are already populated, ask your instructor to check the starter rather than changing the application's state.
