[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $EnvironmentName,

    [string] $SandboxId,

    [string] $Disk = 'ubuntu',

    [string] $AllowedUrl = 'https://open.fda.gov/apis/',

    [string] $DeniedUrl = 'https://example.com/',

    [switch] $CreateSnapshot,

    [switch] $CreateClone
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($CreateClone -and -not $CreateSnapshot) {
    throw 'CreateClone requires CreateSnapshot.'
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

$acaPath = Join-Path $HOME '.aca\bin\aca.exe'
if (-not (Test-Path -LiteralPath $acaPath)) {
    throw "The aca CLI was not found at '$acaPath'."
}

$allowedUri = [Uri] $AllowedUrl
$deniedUri = [Uri] $DeniedUrl
if ($allowedUri.Scheme -ne 'https' -or $deniedUri.Scheme -ne 'https') {
    throw 'AllowedUrl and DeniedUrl must use HTTPS.'
}

azd env select $EnvironmentName | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Unable to select azd environment '$EnvironmentName'."
}

$values = azd env get-values --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read azd environment '$EnvironmentName'."
}

$resourceGroup = $values.AZURE_RESOURCE_GROUP
$sandboxGroup = $values.SANDBOX_GROUP_NAME
$region = $values.SANDBOX_REGION
$subscriptionId = $values.AZURE_SUBSCRIPTION_ID

if ([string]::IsNullOrWhiteSpace($resourceGroup) -or
    [string]::IsNullOrWhiteSpace($sandboxGroup) -or
    [string]::IsNullOrWhiteSpace($region) -or
    [string]::IsNullOrWhiteSpace($subscriptionId)) {
    throw 'The azd environment is missing Sandbox deployment outputs.'
}

& $acaPath config set `
    --subscription $subscriptionId `
    --resource-group $resourceGroup `
    --sandbox-group $sandboxGroup `
    --region $region | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Unable to configure aca for '$EnvironmentName'."
}

& $acaPath doctor
if ($LASTEXITCODE -ne 0) {
    throw 'aca doctor failed.'
}

$allowRule = '{0}:Allow' -f $allowedUri.Host
$createdSandboxPattern = '(?m)^Created sandbox:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s*$'

if ([string]::IsNullOrWhiteSpace($SandboxId)) {
    $createOutput = & $acaPath sandbox create `
        --disk $Disk `
        --cpu 2000m `
        --memory 4096Mi `
        --label lab=LAB722 `
        --label "rollout=$EnvironmentName" `
        --egress-default Deny `
        --egress-rule $allowRule `
        --traffic-inspection Full `
        -o json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Sandbox creation failed: $($createOutput -join "`n")"
    }

    $createText = $createOutput -join "`n"
    $idMatch = [regex]::Match($createText, $createdSandboxPattern)

    if (-not $idMatch.Success) {
        throw "The Sandbox ID was not present in the create response: $createText"
    }

    $SandboxId = $idMatch.Groups[1].Value
}

& $acaPath sandbox lifecycle set `
    --id $SandboxId `
    --auto-suspend enable `
    --idle-timeout-seconds 900 `
    --mode Memory | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Sandbox lifecycle configuration failed for '$SandboxId'."
}

& $acaPath sandbox egress set `
    --id $SandboxId `
    --default Deny `
    --rule $allowRule `
    --traffic-inspection Full | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Sandbox egress configuration failed for '$SandboxId'."
}

$allowedAbsoluteUri = $allowedUri.AbsoluteUri
$deniedAbsoluteUri = $deniedUri.AbsoluteUri
$validationCommand = @"
set -e
curl --fail --silent --show-error -o /dev/null -w 'allowed_status=%{http_code}\n' '$allowedAbsoluteUri'
if curl --fail --silent --show-error --max-time 15 '$deniedAbsoluteUri' >/dev/null 2>&1; then
  echo denied_request_unexpectedly_succeeded
  exit 42
fi
echo denied_request_blocked
"@
$validationCommand = $validationCommand.Replace("`r", '')

& $acaPath sandbox exec --id $SandboxId -c $validationCommand
if ($LASTEXITCODE -ne 0) {
    throw "Sandbox egress validation failed for '$SandboxId'."
}

$snapshotId = $null
$cloneId = $null

if ($CreateSnapshot) {
    & $acaPath sandbox exec `
        --id $SandboxId `
        -c "printf '%s\n' '$SandboxId' > /tmp/lab722-snapshot-marker"
    if ($LASTEXITCODE -ne 0) {
        throw "Writing the snapshot marker failed for '$SandboxId'."
    }

    $snapshotName = "$EnvironmentName-baseline"
    $snapshotOutput = & $acaPath sandbox snapshot `
        --id $SandboxId `
        --name $snapshotName `
        -o json
    if ($LASTEXITCODE -ne 0) {
        throw "Snapshot creation failed for '$SandboxId'."
    }

    $snapshot = ($snapshotOutput -join "`n") | ConvertFrom-Json
    if ($snapshot.sandboxId -ne $SandboxId) {
        throw "The snapshot does not reference source Sandbox '$SandboxId'."
    }

    $snapshotId = [guid]::Parse($snapshot.id).ToString()

    if ($CreateClone) {
        $cloneOutput = & $acaPath sandbox create `
            --snapshot-id $snapshotId `
            --label lab=LAB722 `
            --label "rollout=$EnvironmentName" `
            --label worker=smoke-clone `
            --egress-default Deny `
            --egress-rule $allowRule `
            --traffic-inspection Full `
            -o json 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Clone creation failed: $($cloneOutput -join "`n")"
        }

        $cloneText = $cloneOutput -join "`n"
        $cloneMatch = [regex]::Match($cloneText, $createdSandboxPattern)

        if (-not $cloneMatch.Success) {
            throw "The clone Sandbox ID was not present in the response: $cloneText"
        }

        $cloneId = $cloneMatch.Groups[1].Value
        & $acaPath sandbox lifecycle set `
            --id $cloneId `
            --auto-suspend enable `
            --idle-timeout-seconds 900 `
            --mode Memory | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Clone lifecycle configuration failed for '$cloneId'."
        }

        $cloneValidationCommand = @"
set -e
test "`$(cat /tmp/lab722-snapshot-marker)" = '$SandboxId'
echo LAB722_SNAPSHOT_FILE_VERIFIED
$validationCommand
echo LAB722_CLONE_READY
"@
        $cloneValidationCommand = $cloneValidationCommand.Replace("`r", '')

        & $acaPath sandbox exec --id $cloneId -c $cloneValidationCommand
        if ($LASTEXITCODE -ne 0) {
            throw "Clone filesystem or egress validation failed for '$cloneId'."
        }
    }
}

& $acaPath sandbox egress decisions --id $SandboxId
if ($LASTEXITCODE -ne 0) {
    throw "Reading egress decisions failed for '$SandboxId'."
}

[pscustomobject] @{
    SandboxId = $SandboxId
    SnapshotId = $snapshotId
    CloneSandboxId = $cloneId
    SandboxGroup = $sandboxGroup
    Region = $region
}
