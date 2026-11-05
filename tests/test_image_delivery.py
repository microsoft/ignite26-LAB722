"""Portable image deployment tests; every Azure and HTTP operation is mocked."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBSCRIPTION = "10000000-0000-0000-0000-000000000002"
DIGEST = "sha256:" + "a" * 64


@unittest.skipUnless(shutil.which("pwsh"), "Native PowerShell is required.")
class ImageDeliveryTests(unittest.TestCase):
    def invoke(self, source="LabRegistry", fault="", overrides=None, private=False, starter=False, pin=False):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary) / "evidence.json"
            options = {
                "SubscriptionId": SUBSCRIPTION, "ResourceGroupName": "participant-rg",
                "RegistryName": "participantregistry", "ExpressEnvironmentName": "participant-express",
                "ImageDigest": DIGEST, "ImageSource": source, "AuthorizeDeployment": True,
            }
            if starter:
                options = {
                    "SubscriptionId": SUBSCRIPTION, "ResourceGroupName": "participant-rg",
                    "ExpressEnvironmentName": "participant-express", "AuthorizeDeployment": True,
                }
                if pin:
                    options.pop("ExpressEnvironmentName")
                    options.update(PinExisting=True, RegistryName="participantregistry")
            options.update(overrides or {})
            environment = {
                **os.environ, "IMAGE_TEST_ROOT": str(ROOT), "IMAGE_TEST_OPTIONS": json.dumps(options),
                "IMAGE_TEST_EVIDENCE": str(evidence), "IMAGE_TEST_FAULT": fault,
                "IMAGE_TEST_STARTER": "1" if starter else "",
                "IMAGE_TEST_PIN": "1" if pin else "",
                "IMAGE_TEST_SCRIPT": "deploy-lab-starter.ps1" if starter else "deploy-research-preview.ps1",
            }
            for key in ("LAB_REFERENCE_PULL_USERNAME", "LAB_REFERENCE_PULL_PASSWORD"):
                environment.pop(key, None)
            if private:
                environment.update(LAB_REFERENCE_PULL_USERNAME="lab722-caldova-research-pull",
                                   LAB_REFERENCE_PULL_PASSWORD="fictional-read-only-test-password")
            command = r"""
$ErrorActionPreference = 'Stop'
$global:Calls = [Collections.Generic.List[object]]::new()
$global:Http = [Collections.Generic.List[object]]::new()
$global:Request = $null
$global:Options = $env:IMAGE_TEST_OPTIONS | ConvertFrom-Json -AsHashtable
$global:Sub = $Options.SubscriptionId
$global:ImageTestPrefix = "/subscriptions/$Sub/resourceGroups/participant-rg/providers"
$global:EnvId = "$ImageTestPrefix/Microsoft.App/managedEnvironments/participant-express"
$global:AppId = "$ImageTestPrefix/Microsoft.App/containerApps/caldova-research"
$global:MapId = "$ImageTestPrefix/Microsoft.ContainerRegistry/registries/participantregistry/scopeMaps/caldova-research-pull"
$global:Image = 'docker.io/library/nginx:alpine'
if ($env:IMAGE_TEST_PIN) {
    $catalog = Get-Content (Join-Path $env:IMAGE_TEST_ROOT 'data\lab-images.json') -Raw | ConvertFrom-Json
    $global:Image = '{0}/{1}:{2}' -f $catalog.registry,$catalog.repository,$catalog.images.starter.tag
    if ($env:IMAGE_TEST_FAULT -eq 'pin-already-pinned') {
        $global:Image = "$($catalog.registry)/$($catalog.repository)@$($catalog.images.starter.digest)"
    }
    if ($env:IMAGE_TEST_FAULT -eq 'pin-wrong-image') { $global:Image = 'untrusted.invalid/other:starter' }
}
function global:az {
    $native = @($args | ForEach-Object { [string] $_ })
    $global:Calls.Add($native)
    $global:LASTEXITCODE = 0
    if ($native[0] -eq 'account' -and $native[1] -eq 'show') {
        $id = $Sub
        if ($env:IMAGE_TEST_FAULT -eq 'foreign-account') { $id = 'foreign' }
        return (@{id=$id;state='Enabled'} | ConvertTo-Json)
    }
    if ($native[0] -eq 'resource') {
        $registry = $native -contains '2023-07-01'
        if ($native -contains '2025-10-02-preview') {
            $environment = $EnvId
            if ($env:IMAGE_TEST_FAULT -eq 'foreign-portal-environment') { $environment += '-foreign' }
            if ($env:IMAGE_TEST_FAULT -eq 'pin-foreign-group') { $environment = $environment.Replace('/participant-rg/', '/foreign-rg/') }
            $metadata = @{id=$AppId;type='Microsoft.App/containerApps';location='westus3';environmentId=$environment}
            if ($env:IMAGE_TEST_FAULT -eq 'different-region-portal') { $metadata.location = 'westcentralus' }
            if ($native[[array]::IndexOf($native,'--query')+1] -like '*images:*') { $metadata.images = @($global:Image) }
            return ($metadata | ConvertTo-Json)
        }
        $id = if($registry){"$ImageTestPrefix/Microsoft.ContainerRegistry/registries/participantregistry"}else{$EnvId}
        if ($env:IMAGE_TEST_FAULT -eq 'foreign-registry' -and $registry) { $id += '-foreign' }
        $tags = @{lab='LAB722'}
        if ($env:IMAGE_TEST_FAULT -eq 'starter-untagged') { $tags = @{} }
        if ($env:IMAGE_TEST_FAULT -like '*portal*' -and -not $registry) { $tags = @{} }
        $mode = if ($env:IMAGE_TEST_FAULT -eq 'standard-portal') {'Standard'} else {'Express'}
        if ($env:IMAGE_TEST_FAULT -eq 'starter-standard') { $mode = 'Standard' }
        $location = if ($env:IMAGE_TEST_FAULT -eq 'starter-wrong-region') {'eastus'} else {'West US 3'}
        return (@{id=$id;name=$(if($registry){'participantregistry'}else{'participant-express'})
            type=$(if($registry){'Microsoft.ContainerRegistry/registries'}else{'Microsoft.App/managedEnvironments'})
            location=$(if($env:IMAGE_TEST_FAULT -eq 'different-region-portal'){'westcentralus'}elseif($env:IMAGE_TEST_STARTER -and -not $env:IMAGE_TEST_PIN){$location}else{'westus3'});tags=$tags
            properties=@{provisioningState='Succeeded';environmentMode=$mode;loginServer='participantregistry-hash.azurecr.io'}} |
            ConvertTo-Json -Depth 6)
    }
    if ($native[0] -eq 'containerapp' -and $native[1] -eq 'list') {
        if ($env:IMAGE_TEST_FAULT -eq 'inventory-denied') { $global:LASTEXITCODE=1; return '[]' }
        if ($env:IMAGE_TEST_FAULT -eq 'pin-missing-app') { return '[]' }
        if ($env:IMAGE_TEST_STARTER -and -not $env:IMAGE_TEST_PIN -and $env:IMAGE_TEST_FAULT -ne 'starter-existing') { return '[]' }
        $environmentId = $EnvId
        if ($env:IMAGE_TEST_FAULT -eq 'foreign-app') { $environmentId += '-foreign' }
        return (ConvertTo-Json -InputObject @(@{name='caldova-research';properties=@{environmentId=$environmentId}}) -Depth 6)
    }
    if ($native[0] -eq 'containerapp' -and $native[1] -eq 'create') {
        if ($env:IMAGE_TEST_FAULT -eq 'starter-create-failure') { $global:LASTEXITCODE=1; return '{}' }
        $image = $native[[array]::IndexOf($native,'--image')+1]
        return (@{id=$AppId;properties=@{environmentId=$EnvId;provisioningState='Succeeded'
            template=@{containers=@(@{image=$image})}}} | ConvertTo-Json -Depth 6)
    }
    if ($native[0] -eq 'acr' -and $native[1] -eq 'scope-map') {
        $map = @{name='caldova-research-pull';id=$MapId;actions=@(
            'repositories/caldova/research-portal/content/read',
            'repositories/caldova/research-portal/metadata/read')}
        if($native[2] -eq 'list'){return (ConvertTo-Json -InputObject @($map))}
        if($native[2] -eq 'show'){return ($map | ConvertTo-Json)}
    }
    if ($native[0] -eq 'acr' -and $native[1] -eq 'token') {
        if($native[2] -eq 'list'){
            return (ConvertTo-Json -InputObject @(@{name='caldova-research-pull';scopeMapId=$MapId}))
        }
        if($native[2] -eq 'credential'){
            return (@{username='fictional-lab-token';passwords=@(@{value='fictional-lab-password'})} | ConvertTo-Json -Depth 5)
        }
    }
    if ($native[0] -eq 'account' -and $native[1] -eq 'get-access-token') { return 'fictional-management-token' }
    if ($native[0] -eq 'containerapp' -and $native[1] -eq 'show') {
        if ($native -contains 'id') { return $AppId }
        return (@{fqdn='test.invalid';image=$global:Image} | ConvertTo-Json)
    }
    throw "Unexpected Azure command in offline test: $($native -join ' ')"
}
function global:azd { throw 'Portable deployment must not select an azd environment.' }
function global:Invoke-RestMethod {
    param($Method,$Uri,$Headers,$ContentType,$Body)
    $global:Http.Add(@{method=$Method;uri=$Uri})
    if ($Method -eq 'Post') { return [pscustomobject] @{value=@()} }
    return [pscustomobject] @{id=$AppId;location=$(if($env:IMAGE_TEST_FAULT -eq 'different-region-portal'){'westcentralus'}else{'westus3'});properties=@{
        environmentId=$EnvId;provisioningState='Succeeded';configuration=@{registries=@()}
        template=@{containers=@([pscustomobject] @{name='portal';image=$global:Image;env=@()})}}}
}
function global:Invoke-WebRequest {
    param($Method,$Uri,$Headers,$ContentType,$Body,$TimeoutSec,[switch]$SkipHttpErrorCheck)
    $global:Http.Add(@{method=$Method;uri=$Uri})
    if ($Method -eq 'Put') {
        $global:Request = $Body | ConvertFrom-Json -AsHashtable
        $global:Image = $Request.properties.template.containers[0].image
        return [pscustomobject] @{Headers=@{};StatusCode=200}
    }
    return [pscustomobject] @{StatusCode=200;Content=(@{
        status='healthy';preview_state=$(if($env:IMAGE_TEST_PIN){'starter'}else{'reference'});dataset_version='fictional-v2';dataset_kind='reviewed-public'} |
        ConvertTo-Json)}
}
function global:Start-Sleep { param($Seconds) }
try {
    & (Join-Path (Join-Path $env:IMAGE_TEST_ROOT 'scripts') $env:IMAGE_TEST_SCRIPT) @Options | ConvertTo-Json -Depth 10
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
finally {
    @{calls=@($global:Calls.ToArray());http=@($global:Http.ToArray());request=$global:Request} |
        ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $env:IMAGE_TEST_EVIDENCE -Encoding utf8
}
"""
            result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
                                    env=environment, capture_output=True, text=True, timeout=45)
            return result, json.loads(evidence.read_text(encoding="utf-8-sig"))

    def test_starter_fallback_creates_exact_public_image_once_in_existing_express_environment(self):
        result, evidence = self.invoke(starter=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        catalog = json.loads((ROOT / "data" / "lab-images.json").read_text())
        self.assertEqual(output["Image"],
                         f"{catalog['registry']}/{catalog['repository']}@{catalog['images']['starter']['digest']}")
        create, = [call for call in evidence["calls"] if call[:2] == ["containerapp", "create"]]
        self.assertEqual(create[create.index("--environment") + 1], output["ExpressEnvironmentId"])
        self.assertEqual(create[create.index("--target-port") + 1], "8080")
        self.assertEqual(create[create.index("--memory") + 1], "1Gi")
        self.assertTrue(all("--subscription" in call for call in evidence["calls"]))
        self.assertFalse(any(call[0] == "acr" for call in evidence["calls"]))
        self.assertEqual(evidence["http"], [])

    def test_starter_refuses_existing_app_wrong_environment_and_unapproved_creation(self):
        for fault, overrides in (
            ("starter-existing", {}), ("starter-standard", {}), ("starter-wrong-region", {"Region": "westus3"}),
            ("starter-untagged", {}), ("foreign-account", {}), ("inventory-denied", {}),
            ("", {"AuthorizeDeployment": False}),
        ):
            with self.subTest(fault=fault, overrides=overrides):
                result, evidence = self.invoke(starter=True, fault=fault, overrides=overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(call[:2] == ["containerapp", "create"] for call in evidence["calls"]))

    def test_starter_whatif_never_calls_azure(self):
        result, evidence = self.invoke(starter=True, overrides={"WhatIf": True})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(evidence["calls"], [])

    def test_starter_failed_submission_is_not_retried(self):
        result, evidence = self.invoke(starter=True, fault="starter-create-failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum(call[:2] == ["containerapp", "create"] for call in evidence["calls"]), 1)

    def test_starter_can_use_existing_environment_without_an_implicit_region_constraint(self):
        result, evidence = self.invoke(starter=True, fault="starter-wrong-region")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(call[:2] == ["containerapp", "create"] for call in evidence["calls"]), 1)

    def test_existing_starter_tag_is_pinned_without_creating_an_app(self):
        result, evidence = self.invoke(starter=True, pin=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        catalog = json.loads((ROOT / "data" / "lab-images.json").read_text())
        expected = f"{catalog['registry']}/{catalog['repository']}@{catalog['images']['starter']['digest']}"
        self.assertEqual(json.loads(result.stdout)["Image"], expected)
        self.assertEqual(evidence["request"]["properties"]["template"]["containers"][0]["image"], expected)
        self.assertFalse(any(call[:2] == ["containerapp", "create"] for call in evidence["calls"]))

    def test_existing_starter_rejects_foreign_or_unexpected_images_and_avoids_repinning(self):
        for fault in ("pin-foreign-group", "pin-wrong-image", "pin-already-pinned"):
            with self.subTest(fault=fault):
                result, evidence = self.invoke(starter=True, pin=True, fault=fault)
                self.assertEqual(result.returncode == 0, fault == "pin-already-pinned", result.stderr)
                self.assertIsNone(evidence["request"])
                self.assertFalse(any(call[:2] == ["containerapp", "create"] for call in evidence["calls"]))

    def test_existing_starter_missing_or_unreadable_inventory_stops_before_pin_or_creation(self):
        for fault in ("pin-missing-app", "inventory-denied"):
            with self.subTest(fault=fault):
                result, evidence = self.invoke(starter=True, pin=True, fault=fault)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(evidence["request"])
                self.assertFalse(any(call[:2] == ["containerapp", "create"] for call in evidence["calls"]))
                self.assertFalse(any("2025-10-02-preview" in call for call in evidence["calls"]))
                if fault == "pin-missing-app":
                    self.assertIn("The Express portal generates default app and resource-group names.", result.stderr)
                    self.assertIn("Set App Name to 'caldova-research'", result.stderr)
                    self.assertIn("select existing Resource Group 'participant-rg'", result.stderr)
                else:
                    self.assertNotIn("No unique", result.stderr)

    def test_participant_registry_uses_verified_login_server_and_only_explicit_subscription(self):
        result, evidence = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["Image"],
                         f"participantregistry-hash.azurecr.io/caldova/research-portal@{DIGEST}")
        self.assertFalse(output["ParticipantGeneratedCodeVerified"])
        for call in evidence["calls"]:
            self.assertIn("--subscription", call)
            self.assertIn(SUBSCRIPTION, call)
        self.assertEqual(evidence["request"]["properties"]["environmentId"],
                         f"/subscriptions/{SUBSCRIPTION}/resourceGroups/participant-rg/providers/Microsoft.App/managedEnvironments/participant-express")

    def test_shared_reference_is_explicit_pinned_and_never_writes_to_shared_registry(self):
        for source, registry, repository, private in (
            ("SimonRegistry", "simon.azurecr.io", "lab722-caldova-research", False),
            ("SimonRegistry", "simon.azurecr.io", "lab722-caldova-research", True),
            ("ReferenceRegistry", "acateam.azurecr.io", "lab722/caldova-research", False),
        ):
            with self.subTest(source=source, private=private):
                result, evidence = self.invoke(
                    source, private=private,
                    overrides={} if private else {"ReferenceAnonymousPull": True})
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)
                self.assertEqual(output["Image"], f"{registry}/{repository}@{DIGEST}")
                self.assertFalse(output["ParticipantGeneratedCodeVerified"])
                self.assertFalse(any(call[0] == "acr" for call in evidence["calls"]))
                self.assertNotIn("fictional-read-only-test-password", result.stdout + result.stderr)
                self.assertFalse(any("fictional-read-only-test-password" in call for call in evidence["calls"]))
                registries = evidence["request"]["properties"]["configuration"]["registries"]
                self.assertEqual(len(registries), 1 if private else 0)
                if private:
                    self.assertEqual(registries[0]["passwordSecretRef"], "caldova-reference-pull")

    def test_foreign_scopes_and_inventory_errors_fail_before_any_configuration_write(self):
        for fault in ("foreign-account", "foreign-registry", "foreign-app", "inventory-denied"):
            with self.subTest(fault=fault):
                result, evidence = self.invoke(fault=fault)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(evidence["request"])
                self.assertFalse(any(call[:3] == ["acr", "token", "credential"] for call in evidence["calls"]))

    def test_missing_private_pull_credentials_and_whatif_never_call_azure(self):
        result, evidence = self.invoke("SimonRegistry")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("read-only", result.stderr)
        self.assertEqual(evidence["calls"], [])
        result, evidence = self.invoke("SimonRegistry", overrides={"WhatIf": True})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(evidence["calls"], [])
        self.assertIsNone(evidence["request"])

    def test_explicit_portal_app_can_reuse_its_verified_untagged_express_environment(self):
        result, evidence = self.invoke(fault="untagged-portal", overrides={"PortalCreatedApplication": True})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(evidence["request"]["properties"]["environmentId"],
                         f"/subscriptions/{SUBSCRIPTION}/resourceGroups/participant-rg/providers/Microsoft.App/managedEnvironments/participant-express")
        for fault in ("foreign-portal-environment", "standard-portal"):
            with self.subTest(fault=fault):
                result, evidence = self.invoke(fault=fault, overrides={"PortalCreatedApplication": True})
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(evidence["request"])
        result, evidence = self.invoke(fault="untagged-portal")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(evidence["request"])

    def test_portal_deployment_accepts_a_separate_application_region(self):
        result, evidence = self.invoke(fault="different-region-portal", overrides={"PortalCreatedApplication": True})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(evidence["request"]["properties"]["environmentId"],
                         f"/subscriptions/{SUBSCRIPTION}/resourceGroups/participant-rg/providers/Microsoft.App/managedEnvironments/participant-express")


if __name__ == "__main__":
    unittest.main()
