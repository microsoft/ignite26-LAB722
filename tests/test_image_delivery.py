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
    def invoke(self, source="LabRegistry", fault="", overrides=None, private=False):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary) / "evidence.json"
            options = {
                "SubscriptionId": SUBSCRIPTION, "ResourceGroupName": "participant-rg",
                "RegistryName": "participantregistry", "ExpressEnvironmentName": "participant-express",
                "ImageDigest": DIGEST, "ImageSource": source, "AuthorizeDeployment": True,
            }
            options.update(overrides or {})
            environment = {
                **os.environ, "IMAGE_TEST_ROOT": str(ROOT), "IMAGE_TEST_OPTIONS": json.dumps(options),
                "IMAGE_TEST_EVIDENCE": str(evidence), "IMAGE_TEST_FAULT": fault,
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
$global:Prefix = "/subscriptions/$Sub/resourceGroups/participant-rg/providers"
$global:EnvId = "$Prefix/Microsoft.App/managedEnvironments/participant-express"
$global:AppId = "$Prefix/Microsoft.App/containerApps/caldova-research"
$global:MapId = "$Prefix/Microsoft.ContainerRegistry/registries/participantregistry/scopeMaps/caldova-research-pull"
$global:Image = 'docker.io/library/nginx:alpine'
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
        $id = if($registry){"$Prefix/Microsoft.ContainerRegistry/registries/participantregistry"}else{$EnvId}
        if ($env:IMAGE_TEST_FAULT -eq 'foreign-registry' -and $registry) { $id += '-foreign' }
        return (@{id=$id;name=$(if($registry){'participantregistry'}else{'participant-express'})
            type=$(if($registry){'Microsoft.ContainerRegistry/registries'}else{'Microsoft.App/managedEnvironments'})
            location='westus3';tags=@{lab='LAB722'}
            properties=@{provisioningState='Succeeded';loginServer='participantregistry-hash.azurecr.io'}} |
            ConvertTo-Json -Depth 6)
    }
    if ($native[0] -eq 'containerapp' -and $native[1] -eq 'list') {
        if ($env:IMAGE_TEST_FAULT -eq 'inventory-denied') { $global:LASTEXITCODE=1; return '[]' }
        $environmentId = $EnvId
        if ($env:IMAGE_TEST_FAULT -eq 'foreign-app') { $environmentId += '-foreign' }
        return (ConvertTo-Json -InputObject @(@{name='caldova-research';properties=@{environmentId=$environmentId}}) -Depth 6)
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
    return [pscustomobject] @{id=$AppId;location='westus3';properties=@{
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
        status='healthy';preview_state='reference';dataset_version='fictional-v2';dataset_kind='reviewed-public'} |
        ConvertTo-Json)}
}
function global:Start-Sleep { param($Seconds) }
try {
    & (Join-Path $env:IMAGE_TEST_ROOT 'scripts\deploy-research-preview.ps1') @Options | ConvertTo-Json -Depth 10
}
finally {
    @{calls=@($global:Calls.ToArray());http=@($global:Http.ToArray());request=$global:Request} |
        ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $env:IMAGE_TEST_EVIDENCE -Encoding utf8
}
"""
            result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
                                    env=environment, capture_output=True, text=True, timeout=45)
            return result, json.loads(evidence.read_text(encoding="utf-8-sig"))

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

    def test_shared_reference_is_explicit_pinned_and_never_writes_to_simon_registry(self):
        for private in (False, True):
            with self.subTest(private=private):
                result, evidence = self.invoke(
                    "SimonRegistry", private=private,
                    overrides={} if private else {"ReferenceAnonymousPull": True})
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)
                self.assertEqual(output["Image"], f"simon.azurecr.io/lab722-caldova-research@{DIGEST}")
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


if __name__ == "__main__":
    unittest.main()
