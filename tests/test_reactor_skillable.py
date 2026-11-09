import base64
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 required")
class SkillableAccess(unittest.TestCase):
    def execute(self, *, foreign=False, existing=False, restricted=False, mixed_case=False,
                error_count=0, error_method="PATCH", error_status=404,
                error_target="applications", error_details="", empty_uri_reads=0,
                readback_mismatch="", foundation_case=""):
        source = (ROOT / "scripts" / "skillable-reactor2-access.ps1").read_text(encoding="utf-8-sig")
        replacements = {
            "@lab.CloudSubscription.Id": "11111111-1111-1111-1111-111111111111",
            "@lab.CloudSubscription.TenantId": "22222222-2222-2222-2222-222222222222",
            "@lab.CloudResourceGroup(ResourceGroup1).Name": "LAB722",
            "@lab.CloudPortalCredential(User1).Username": "learner@example.test",
            "@lab.CloudSubscription.AppId": "33333333-3333-3333-3333-333333333333",
            "@lab.CloudSubscription.AppSecret": "synthetic-input",
        }
        for old, new in replacements.items():
            source = source.replace(old, new)
        program = r"""
$ErrorActionPreference='Stop'
$writes=[Collections.Generic.List[object]]::new()
$calls=[Collections.Generic.List[object]]::new()
$sleeps=[Collections.Generic.List[int]]::new()
$armCalls=[Collections.Generic.List[object]]::new()
$deploymentCalls=[Collections.Generic.List[object]]::new()
$exportPaths=[Collections.Generic.List[string]]::new()
$accountReads=0
function Start-Sleep { param($Seconds) $sleeps.Add($Seconds) }
$sub='11111111-1111-1111-1111-111111111111'
$tenant='22222222-2222-2222-2222-222222222222'
$setup='44444444-4444-4444-4444-444444444444'
$outputs=@{}
foreach($pair in @{
 REACTOR2_HARNESS_VERSION='1';AZURE_SUBSCRIPTION_ID=$sub;AZURE_TENANT_ID=$tenant
 AZURE_RESOURCE_GROUP='LAB722';FOUNDRY_ACCOUNT_NAME='lab-ai';FOUNDRY_PROJECT_NAME='reactor'
 SANDBOX_GROUP_NAME='lab-sandboxes';AZURE_CONTAINER_REGISTRY_NAME='labacr'
 REACTOR2_FRONTEND_OBJECT_ID='55555555-5555-5555-5555-555555555555'
 REACTOR2_EXECUTION_OBJECT_ID='66666666-6666-6666-6666-666666666666'
 REACTOR2_PROJECT_OBJECT_ID='77777777-7777-7777-7777-777777777777'
}.GetEnumerator()){$outputs[$pair.Key]=@{Value=$pair.Value}}
$api=@{id='99999999-9999-9999-9999-999999999999';appId='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
 notes="Skillable allocation /subscriptions/$sub/resourceGroups/LAB722"
 signInAudience='AzureADMyOrg';api=@{requestedAccessTokenVersion=1}
 identifierUris=@();appRoleAssignmentRequired=$false}
function Connect-AzAccount { throw 'Pool credential login must not run.' }
function Get-AzContext {@{Subscription=@{Id=$sub};Tenant=@{Id=$tenant}}}
function Get-AzResourceGroupDeployment {$mockDeployments}
function Invoke-AzRestMethod {
 param($Method,$Path)
 $armCalls.Add(@{Method=$Method;Path=$Path})
 if($Path -match '/operations\?'){
  $content=@{value=@(@{properties=@{
   provisioningState='Failed'
   targetResource=@{resourceName=$accountName;resourceType='Microsoft.CognitiveServices/accounts';id=$accountId}
   statusMessage=@{error=@{code=$foundationCode;message=$foundationMessage}}
  }})}
  if($foundationCase -eq 'multiple-errors'){$content.value+=@{properties=@{provisioningState='Failed'}}}
 }else{
  $script:accountReads++
  $state='Succeeded'
  if($foundationCase -eq 'not-ready' -or
     ($foundationCase -eq 'wait-ready' -and $accountReads -lt 3)){$state='Accepted'}
  if($foundationCase -eq 'failed-account'){$state='Failed'}
  $purpose=if($foundationCase -eq 'foreign-owner'){'another-app'}else{'reactor2-skillable'}
  $content=@{id=$accountId;kind='AIServices';tags=@{lab='LAB722';purpose=$purpose}
   properties=@{provisioningState=$state}}
 }
 @{StatusCode=200;Content=($content|ConvertTo-Json -Depth 20)}
}
function Save-AzResourceGroupDeploymentTemplate {
 param($ResourceGroupName,$DeploymentName,$Path,[switch]$Force)
 $exportPaths.Add($Path)
 $hash=if($foundationCase -eq 'changed-export'){'different'}else{'9372070027890358331'}
 [IO.File]::WriteAllText($Path,(@{metadata=@{_generator=@{templateHash=$hash}}}|ConvertTo-Json -Depth 5))
}
function New-AzResourceGroupDeployment {
 param($ResourceGroupName,$Name,$Mode,$TemplateFile,$TemplateParameterObject)
 $deploymentCalls.Add(@{ResourceGroupName=$ResourceGroupName;Name=$Name;Mode=$Mode;Parameters=$TemplateParameterObject})
 if($foundationCase -eq 'recovery-fails'){throw 'Synthetic recovery deployment failed.'}
 [pscustomobject]@{ProvisioningState='Succeeded';Outputs=$outputs}
}
function Get-AzADUser {@{Id='88888888-8888-8888-8888-888888888888'}}
function Get-AzADServicePrincipal {@{Id=$setup}}
function Get-AzRoleAssignment {
 param($ObjectId,$Scope)
 if($reuse){
  $role=if($Scope -match 'sandboxGroups'){'c24cf47c-5077-412d-a19c-45202126392c'}
   elseif($Scope -match 'ContainerRegistry'){'7f951dda-4ed3-4680-a7ca-43fe172d538d'}
   else{'53ca6127-db72-4b80-b1b0-d745d6d5456d'}
  @{ObjectId=$ObjectId;Scope=$Scope;RoleDefinitionId=$role}
 }
}
function New-AzRoleAssignment {
 param($ObjectId,$RoleDefinitionId,$Scope)
 $record=@{ObjectId=$ObjectId;RoleDefinitionId=$RoleDefinitionId;Scope=$Scope
  RoleAssignmentId="$Scope/providers/Microsoft.Authorization/roleAssignments/$([guid]::NewGuid())"}
 $writes.Add($record);$record
}
function Get-AzResourceGroup {@{Tags=@{}}}
function Set-AzResourceGroup { throw 'Policy forbids resource-group writes.' }
function Get-AzAccessToken {@{Token='synthetic-token'}}
function Invoke-RestMethod {
 param($Uri,$Method,$Headers,$ContentType,$Body)
 $calls.Add(@{Method=$Method;Uri=$Uri;Body=$Body})
 if($Uri -match "/$errorTarget(?:/|$)" -and $Method -eq $errorMethod -and $remainingErrors -gt 0){
  $script:remainingErrors--
  $failure=[Exception]::new('Synthetic directory response')
  $failure|Add-Member -NotePropertyName Response -NotePropertyValue ([pscustomobject]@{StatusCode=$errorStatus})
  $record=[Management.Automation.ErrorRecord]::new(
   $failure,'GraphResponse',[Management.Automation.ErrorCategory]::InvalidOperation,$null)
  if($mockErrorDetails){$record.ErrorDetails=[Management.Automation.ErrorDetails]::new($mockErrorDetails)}
  throw $record
 }
 if($Uri -match 'applications\?' -and $Method -eq 'GET'){
  @{value=$(if($reuse){$api}else{@()})}
 }elseif($Uri -match 'servicePrincipals\?' -and $Method -eq 'GET'){
  @{value=$(if($reuse){$api}else{@()})}
 }elseif($Uri -match '/applications/' -and $Method -eq 'GET'){
  $readback=$api.Clone()
  if($remainingEmptyReads -gt 0){$script:remainingEmptyReads--;$readback.identifierUris=@()}
  switch($readbackMismatch){
   'foreign-uri' {$readback.identifierUris=@('api://foreign')}
   'application-id' {$readback.id='foreign'}
   'app-id' {$readback.appId='foreign'}
   'token-version' {$readback.api=@{requestedAccessTokenVersion=2}}
   'audience' {$readback.signInAudience='AzureADMultipleOrgs'}
   'notes' {$readback.notes='another allocation'}
  }
  $readback
 }
 elseif($Uri -match '/applications/' -and $Method -eq 'PATCH'){
  $api.identifierUris=@(($Body|ConvertFrom-Json).identifierUris)
 }
 elseif($Uri -match '/servicePrincipals/' -and $Method -eq 'GET'){
  $readback=$api.Clone()
  switch($readbackMismatch){
   'principal-id' {$readback.id='foreign'}
   'principal-app-id' {$readback.appId='foreign'}
   'principal-policy-null' {$readback.appRoleAssignmentRequired=$null}
  }
  $readback
 }elseif($Method -eq 'POST'){$api}
}
"""
        program += f"\n$reuse=${str(existing).lower()}\n"
        program += f"$remainingErrors={error_count}\n$errorMethod='{error_method}'\n$errorStatus={error_status}\n"
        program += f"$errorTarget='{error_target}'\n$mockErrorDetails='{error_details.replace(chr(39), chr(39) * 2)}'\n"
        program += f"$remainingEmptyReads={empty_uri_reads}\n$readbackMismatch='{readback_mismatch}'\n"
        program += f"$foundationCase='{foundation_case}'\n"
        program += r"""
$mockDeployments=@([pscustomobject]@{ProvisioningState='Succeeded';Outputs=$outputs})
if($foundationCase){
 $accountName='lab722-abcdefghijklm-ai'
 $accountId="/subscriptions/$sub/resourceGroups/LAB722/providers/Microsoft.CognitiveServices/accounts/$accountName"
 if($foundationCase -eq 'foreign-scope'){$accountId=$accountId.Replace('/LAB722/','/another-group/')}
 $foundationCode=if($foundationCase -eq 'wrong-error'){'AuthorizationFailed'}else{'RequestConflict'}
 $foundationMessage="Cannot modify resource with id '$accountId' because the resource entity provisioning state is not terminal. Please wait for the provisioning state to become terminal and then retry the request. "
 $mockDeployments=@('reactor2-core','reactor2-express','reactor2-sandboxes')|ForEach-Object {
  [pscustomobject]@{DeploymentName=$_;ProvisioningState='Succeeded';Outputs=@{};TemplateHash='other'}
 }
 if($foundationCase -eq 'peer-failed'){$mockDeployments[0].ProvisioningState='Failed'}
 $mockDeployments+= [pscustomobject]@{
  DeploymentName='67150610-41583-7044';ProvisioningState='Failed';Mode='Incremental'
  TemplateHash='9372070027890358331';Outputs=@{}
  Parameters=@{location=@{Value='westus3'};modelCapacity=@{Value=40}}
 }
 if($foundationCase -eq 'already-retried'){
  $mockDeployments+= [pscustomobject]@{DeploymentName='67150610-41583-7044-recovery'
   ProvisioningState='Running';Outputs=@{};TemplateHash='9372070027890358331'}
 }
}
"""
        if existing:
            program += "$api.identifierUris=@('api://aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')\n"
        if restricted:
            program += "$api.appRoleAssignmentRequired=$true\n"
        if foreign:
            program += "$outputs.AZURE_RESOURCE_GROUP.Value='another-group'\n"
        if mixed_case:
            program += r"""
$normalized=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
foreach($entry in $outputs.GetEnumerator()){
 $normalized[$entry.Key.ToLowerInvariant()]=$entry.Value
}
$outputs=$normalized
"""
        program += "\n$failure=$null\ntry { & {\n" + source + "\n} } catch {$failure=$_.Exception.Message}\n"
        program += """[pscustomobject]@{writes=@($writes);calls=@($calls);sleeps=@($sleeps);failure=$failure
 armCalls=@($armCalls);deploymentCalls=@($deploymentCalls);accountReads=$accountReads
 remainingExports=@($exportPaths|Where-Object {Test-Path -LiteralPath $_})}|ConvertTo-Json -Depth 20 -Compress\n"""
        result = subprocess.run(["pwsh", "-NoProfile", "-Command", program], capture_output=True, text=True, check=True)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_creates_only_scoped_grants_and_an_unprivileged_allocation_api(self):
        result = self.execute()
        self.assertIsNone(result["failure"])
        writes = result["writes"]
        self.assertEqual(len(writes), 8)
        self.assertFalse(any(w["ObjectId"] == "44444444-4444-4444-4444-444444444444" for w in writes))
        self.assertTrue(all(w["Scope"].startswith(
            "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/LAB722/providers/"
        ) for w in writes))
        self.assertEqual(len({(w["ObjectId"], w["Scope"], w["RoleDefinitionId"]) for w in writes}), 8)
        app_posts = [c for c in result["calls"] if c["Method"] == "POST" and c["Uri"].endswith("/applications")]
        self.assertEqual(len(app_posts), 1)
        body = json.loads(app_posts[0]["Body"])
        self.assertEqual(body["api"]["requestedAccessTokenVersion"], 1)
        self.assertNotIn("requiredResourceAccess", body)
        self.assertFalse(any("roleManagement" in c["Uri"] for c in result["calls"]))

    def test_account_conflict_waits_for_readiness_then_recovers_original_parameters_once(self):
        result = self.execute(foundation_case="wait-ready")
        self.assertIsNone(result["failure"])
        self.assertEqual(result["sleeps"], [15, 15])
        self.assertEqual(result["accountReads"], 3)
        self.assertEqual(result["deploymentCalls"], [{
            "ResourceGroupName": "LAB722", "Name": "67150610-41583-7044-recovery",
            "Mode": "Incremental", "Parameters": {"location": "westus3", "modelCapacity": 40},
        }])
        self.assertEqual(len(result["writes"]), 8)
        self.assertEqual(result["remainingExports"], [])

    def test_foundation_recovery_rejects_unrelated_or_ambiguous_failures(self):
        for case in ("wrong-error", "foreign-scope", "foreign-owner", "multiple-errors",
                     "peer-failed", "already-retried", "failed-account", "changed-export"):
            with self.subTest(case=case):
                result = self.execute(foundation_case=case)
                self.assertIsNotNone(result["failure"])
                self.assertEqual(result["deploymentCalls"], [])
                self.assertEqual(result["writes"], [])
                self.assertEqual(result["calls"], [])
                self.assertEqual(result["remainingExports"], [])

    def test_account_readiness_timeout_does_not_redeploy_or_grant_access(self):
        result = self.execute(foundation_case="not-ready")
        self.assertIn("did not become ready", result["failure"])
        self.assertEqual(result["accountReads"], 60)
        self.assertEqual(result["sleeps"], [15] * 59)
        self.assertEqual(result["deploymentCalls"], [])
        self.assertEqual(result["writes"], [])
        self.assertEqual(result["calls"], [])

    def test_failed_recovery_is_not_retried_and_preserves_no_export_file(self):
        result = self.execute(foundation_case="recovery-fails")
        self.assertIn("Synthetic recovery deployment failed", result["failure"])
        self.assertEqual(len(result["deploymentCalls"]), 1)
        self.assertEqual(result["writes"], [])
        self.assertEqual(result["calls"], [])
        self.assertEqual(result["remainingExports"], [])

    def test_exact_existing_assignments_and_api_are_not_created_again(self):
        result = self.execute(existing=True)
        self.assertIsNone(result["failure"])
        self.assertEqual(result["writes"], [])
        self.assertTrue(all(c["Method"] == "GET" for c in result["calls"]))

    def test_case_sensitive_cloud_output_dictionary_accepts_changed_name_casing(self):
        result = self.execute(mixed_case=True)
        self.assertIsNone(result["failure"])
        self.assertEqual(len(result["writes"]), 8)

    def test_foreign_foundation_output_rejects_before_role_or_graph_writes(self):
        result = self.execute(foreign=True)
        self.assertIn("output scope differs", result["failure"])
        self.assertEqual(result["writes"], [])
        self.assertEqual(result["calls"], [])

    def test_assignment_required_policy_fails_without_overriding_it(self):
        result = self.execute(existing=True, restricted=True)
        self.assertIn("assignment policy differs", result["failure"])
        self.assertTrue(all(c["Method"] == "GET" for c in result["calls"]))

    def test_successfully_written_uri_tolerates_only_bounded_empty_readback(self):
        result = self.execute(empty_uri_reads=2)
        self.assertIsNone(result["failure"])
        self.assertEqual(result["sleeps"], [5, 5])
        self.assertEqual(sum(c["Method"] == "PATCH" for c in result["calls"]), 1)
        for path in ("/applications", "/servicePrincipals"):
            self.assertEqual(sum(c["Method"] == "POST" and c["Uri"].endswith(path)
                                 for c in result["calls"]), 1)
        result = self.execute(empty_uri_reads=7)
        self.assertIn("identifierUris differs", result["failure"])
        self.assertIn("observed []", result["failure"])
        self.assertEqual(result["sleeps"], [5] * 6)

    def test_empty_readback_without_this_run_writing_uri_is_not_retried(self):
        result = self.execute(existing=True, empty_uri_reads=1)
        self.assertIn("identifierUris differs", result["failure"])
        self.assertEqual(result["sleeps"], [])
        self.assertTrue(all(c["Method"] == "GET" for c in result["calls"]))

    def test_foreign_readback_uri_fails_immediately_without_replacement(self):
        result = self.execute(readback_mismatch="foreign-uri")
        self.assertIn("identifierUris differs", result["failure"])
        self.assertIn("api://foreign", result["failure"])
        self.assertEqual(result["sleeps"], [])
        self.assertEqual(sum(c["Method"] == "PATCH" for c in result["calls"]), 1)

    def test_fixed_contract_mismatches_fail_before_empty_uri_retry_with_field_details(self):
        for mismatch, field in (
            ("application-id", "application.id"), ("app-id", "application.appId"),
            ("token-version", "application.api.requestedAccessTokenVersion"),
            ("audience", "application.signInAudience"), ("notes", "application.notes"),
            ("principal-id", "servicePrincipal.id"), ("principal-app-id", "servicePrincipal.appId"),
            ("principal-policy-null", "appRoleAssignmentRequired"),
        ):
            with self.subTest(mismatch=mismatch):
                result = self.execute(empty_uri_reads=1, readback_mismatch=mismatch)
                self.assertIn(field, result["failure"])
                self.assertIn("observed", result["failure"])
                self.assertEqual(result["sleeps"], [])

    def test_known_application_patch_and_readback_tolerate_definite_not_found(self):
        for method in ("PATCH", "GET"):
            with self.subTest(method=method):
                result = self.execute(error_count=2, error_method=method)
                self.assertIsNone(result["failure"])
                self.assertEqual(result["sleeps"], [5, 5])
                for path in ("/applications", "/servicePrincipals"):
                    self.assertEqual(sum(c["Method"] == "POST" and c["Uri"].endswith(path)
                                         for c in result["calls"]), 1)

    def test_persistent_not_found_is_bounded_and_reports_the_operation(self):
        result = self.execute(error_count=7)
        self.assertIn("PATCH applications/99999999", result["failure"])
        self.assertEqual(result["sleeps"], [5] * 6)
        self.assertFalse(any(c["Uri"].endswith("/servicePrincipals") for c in result["calls"]))

    def test_non_not_found_errors_stop_without_retrying(self):
        for status in (403, 500):
            with self.subTest(status=status):
                result = self.execute(error_count=1, error_status=status)
                self.assertIn("PATCH applications/99999999", result["failure"])
                self.assertEqual(result["sleeps"], [])

    def test_service_principal_retries_only_definite_missing_backing_application(self):
        details = json.dumps({"error": {"code": "Request_BadRequest", "details": [{
            "code": "NoBackingApplicationObject", "target": "appId",
            "message": "Application aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa is not visible",
        }]}})
        result = self.execute(error_count=2, error_method="POST", error_status=400,
                              error_target="servicePrincipals", error_details=details)
        self.assertIsNone(result["failure"])
        self.assertEqual(result["sleeps"], [15, 15])
        self.assertEqual(sum(c["Method"] == "POST" and c["Uri"].endswith("/applications")
                             for c in result["calls"]), 1)
        self.assertEqual(sum(c["Method"] == "POST" and c["Uri"].endswith("/servicePrincipals")
                             for c in result["calls"]), 3)

    def test_service_principal_missing_application_retries_are_bounded(self):
        result = self.execute(error_count=4, error_method="POST", error_target="servicePrincipals")
        self.assertIn("POST servicePrincipals", result["failure"])
        self.assertEqual(result["sleeps"], [15] * 3)

    def test_other_service_principal_failures_preserve_details_without_retry(self):
        for details in (
            "Non-JSON Graph error",
            json.dumps({"error": {"code": "Request_BadRequest", "message": "Policy rejection"}}),
            json.dumps({"error": {"code": "Request_BadRequest", "details": [{}]}}),
            json.dumps({"error": {"code": "Request_BadRequest", "details": [{
                "code": "NoBackingApplicationObject", "target": "appId", "message": "Another application",
            }]}}),
        ):
            with self.subTest(details=details):
                result = self.execute(error_count=1, error_method="POST", error_status=400,
                                      error_target="servicePrincipals", error_details=details)
                self.assertIn("POST servicePrincipals", result["failure"])
                self.assertIn(details, result["failure"])
                self.assertEqual(result["sleeps"], [])
        result = self.execute(error_count=1, error_method="POST", error_status=500,
                              error_target="servicePrincipals")
        self.assertIn("POST servicePrincipals", result["failure"])
        self.assertEqual(result["sleeps"], [])


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 required")
class SkillableLearnerSignIn(unittest.TestCase):
    def test_final_outputs_use_the_learners_writable_desktop(self):
        source = (ROOT / "scripts" / "run-reactor-skillable-vm.ps1").read_text(encoding="utf-8-sig")
        outputs = source[source.index("$desktop ="):]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            desktop = root / "Desktop"
            desktop.mkdir()
            program = r"""
class Environment {
 static [string] GetFolderPath([string]$name) {
  if($name -ne 'DesktopDirectory'){throw 'Shared desktop is not writable by the learner.'}
  return '__DESKTOP__'
 }
}
$ErrorActionPreference='Stop'
$root='__ROOT__'
$prepared=@{FrontendUrl='https://frontend.example.test'}
"""
            program = program.replace("__DESKTOP__", str(desktop).replace("'", "''"))
            program = program.replace("__ROOT__", str(root).replace("'", "''"))
            result = subprocess.run(["pwsh", "-NoProfile", "-Command", program + outputs],
                                    capture_output=True, text=True, check=True)
            self.assertIn("URL=https://frontend.example.test",
                          (desktop / "Reactor 2 research app.url").read_text(encoding="ascii"))
            self.assertEqual(json.loads((root / "learner-values.json").read_text(encoding="utf-8")),
                             {"FrontendUrl": "https://frontend.example.test"})
            self.assertIn("REACTOR2_SKILLABLE_READY https://frontend.example.test", result.stdout)

    def execute(self, *, account_type="user", signed_in=True, login_failure=False, wrong_scope=False):
        source = (ROOT / "scripts" / "run-reactor-skillable-vm.ps1").read_text(encoding="utf-8-sig")
        preflight = source[source.index("$accountText ="):source.index("$basePython =")]
        program = r"""
$ErrorActionPreference='Stop'
$SubscriptionId=[guid]'11111111-1111-1111-1111-111111111111'
$TenantId=[guid]'22222222-2222-2222-2222-222222222222'
$calls=[Collections.Generic.List[string]]::new()
$current=@{id="$SubscriptionId";tenantId="$TenantId";user=@{type=$initialType}}
function az {
 param([Parameter(ValueFromRemainingArguments)][string[]]$Arguments)
 $calls.Add(($Arguments -join ' '))
 $global:LASTEXITCODE=0
 if($Arguments[0] -eq 'login'){
  if($loginFails){$global:LASTEXITCODE=1;return}
  $script:hasAccount=$true
  $current.user.type='user'
 }elseif($Arguments[1] -eq 'set'){
  if($foreignScope){$current.tenantId='33333333-3333-3333-3333-333333333333'}
 }elseif($Arguments[1] -eq 'show'){
  if(-not $hasAccount){$global:LASTEXITCODE=1;return}
  $current|ConvertTo-Json -Compress
 }else{throw 'Unexpected Azure CLI operation'}
}
"""
        settings = (
            f"$initialType='{account_type}'\n"
            f"$hasAccount=${str(signed_in).lower()}\n"
            f"$loginFails=${str(login_failure).lower()}\n"
            f"$foreignScope=${str(wrong_scope).lower()}\n"
        )
        program = settings + program
        program += "\n$failure=$null\ntry {\n" + preflight + "\n} catch {$failure=$_.Exception.Message}\n"
        program += "[pscustomobject]@{calls=@($calls);failure=$failure}|ConvertTo-Json -Compress\n"
        result = subprocess.run(["pwsh", "-NoProfile", "-Command", program], capture_output=True, text=True, check=True)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_existing_user_selects_allocation_without_another_login(self):
        result = self.execute()
        self.assertIsNone(result["failure"])
        self.assertFalse(any(c.startswith("login ") for c in result["calls"]))
        self.assertIn("account set --subscription 11111111-1111-1111-1111-111111111111", result["calls"])

    def test_missing_login_or_service_principal_requires_user_device_sign_in(self):
        for settings in ({"signed_in": False}, {"account_type": "servicePrincipal"}):
            with self.subTest(**settings):
                result = self.execute(**settings)
                self.assertIsNone(result["failure"])
                self.assertIn(
                    "login --use-device-code --tenant 22222222-2222-2222-2222-222222222222 --output none",
                    result["calls"],
                )

    def test_failed_sign_in_stops_before_subscription_selection(self):
        result = self.execute(signed_in=False, login_failure=True)
        self.assertIn("sign-in failed", result["failure"])
        self.assertFalse(any(c.startswith("account set ") for c in result["calls"]))

    def test_foreign_selected_scope_is_rejected(self):
        result = self.execute(wrong_scope=True)
        self.assertIn("allocated learner user and subscription", result["failure"])


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 required")
class SkillableApiDiscovery(unittest.TestCase):
    def execute(self, *, teardown=False, foreign=False, partial=False, restricted=False,
                error_method="", error_target="", error_status=404):
        if teardown:
            source = (ROOT / "scripts" / "skillable-reactor2-teardown.ps1").read_text(encoding="utf-8-sig")
            source = source.replace("@lab.CloudSubscription.Id", "11111111-1111-1111-1111-111111111111")
            source = source.replace("@lab.CloudSubscription.TenantId", "22222222-2222-2222-2222-222222222222")
            source = source.replace("@lab.CloudResourceGroup(ResourceGroup1).Name", "LAB722")
        else:
            source = (ROOT / "scripts" / "initialize-reactor-skillable.ps1").read_text(encoding="utf-8-sig")
            source = source[source.index("$apiName ="):source.index("$stateDirectory =")]
        program = r"""
$ErrorActionPreference='Stop'
$SubscriptionId=[guid]'11111111-1111-1111-1111-111111111111'
$TenantId=[guid]'22222222-2222-2222-2222-222222222222'
$ResourceGroupName='LAB722'
$calls=[Collections.Generic.List[object]]::new()
$api=@{
 id='99999999-9999-9999-9999-999999999999'
 appId='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
 displayName="LAB722-Reactor2-$SubscriptionId-LAB722"
 notes="Skillable allocation /subscriptions/$SubscriptionId/resourceGroups/LAB722"
 signInAudience='AzureADMyOrg';api=@{requestedAccessTokenVersion=1}
 identifierUris=@('api://aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
}
$principal=@{id='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';appId=$api.appId;appRoleAssignmentRequired=$false}
function Get-AzContext {@{Subscription=@{Id="$SubscriptionId"};Tenant=@{Id="$TenantId"}}}
function Get-AzResourceGroup {throw 'Resource-group metadata must not be required.'}
function Set-AzResourceGroup {throw 'Policy forbids resource-group writes.'}
function Get-AzAccessToken {@{Token='synthetic-token'}}
function Invoke-HarnessCommand {
 param($Executable,$Arguments)
 $calls.Add(@{method='CLI';target=($Arguments -join ' ')})
 if($Arguments[0] -ne 'ad' -or $Arguments[2] -ne 'list'){throw 'Only directory reads are allowed.'}
 if($Arguments[1] -eq 'app'){ConvertTo-Json -InputObject @($api) -Depth 10 -Compress}
 else{ConvertTo-Json -InputObject @($principal) -Compress}
}
function Invoke-RestMethod {
 param($Uri,$Method='GET',$Headers)
 $calls.Add(@{method="$Method";target=$Uri})
 if($mockErrorMethod -and $Method -ieq $mockErrorMethod -and $Uri -match $mockErrorTarget){
  $failure=[Exception]::new('Synthetic Graph operation failed')
  $failure|Add-Member -NotePropertyName Response -NotePropertyValue ([pscustomobject]@{StatusCode=$mockErrorStatus})
  throw $failure
 }
 if($Method -eq 'Delete'){return}
 if($Uri -match 'applications\?'){@{value=@($api)}}
 elseif($Uri -match 'servicePrincipals\?'){@{value=@($principal)}}
 else{$api}
}
"""
        program += f"$mockErrorMethod='{error_method}'\n$mockErrorTarget='{error_target}'\n"
        program += f"$mockErrorStatus={error_status}\n"
        if foreign:
            program += "$api.notes='Another allocation'\n"
        if partial:
            program += "$api.identifierUris=@()\n"
        if restricted:
            program += "$principal.appRoleAssignmentRequired=$true\n"
        program += "\n$failure=$null\ntry { & {\n" + source + "\n} } catch {$failure=$_.Exception.Message}\n"
        program += "[pscustomobject]@{calls=@($calls);failure=$failure}|ConvertTo-Json -Depth 10 -Compress\n"
        encoded = base64.b64encode(program.encode("utf-16-le")).decode("ascii")
        result = subprocess.run(["pwsh", "-NoProfile", "-EncodedCommand", encoded],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_learner_discovers_exact_owned_api_using_only_directory_reads(self):
        result = self.execute()
        self.assertIsNone(result["failure"])
        self.assertEqual(len(result["calls"]), 2)
        self.assertTrue(all(c["method"] == "CLI" for c in result["calls"]))

    def test_learner_rejects_foreign_partial_or_restrictive_api(self):
        for settings in ({"foreign": True}, {"partial": True}, {"restricted": True}):
            with self.subTest(**settings):
                result = self.execute(**settings)
                self.assertIsNotNone(result["failure"])
                self.assertTrue(all(c["method"] == "CLI" for c in result["calls"]))

    def test_cleanup_handles_owned_partial_registration_without_resource_group_tags(self):
        result = self.execute(teardown=True, partial=True)
        self.assertIsNone(result["failure"])
        deletions = [c["target"] for c in result["calls"] if c["method"] == "Delete"]
        self.assertEqual(deletions, [
            "https://graph.microsoft.com/v1.0/servicePrincipals/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "https://graph.microsoft.com/v1.0/applications/99999999-9999-9999-9999-999999999999",
        ])

    def test_cleanup_never_deletes_a_foreign_registration(self):
        result = self.execute(teardown=True, foreign=True)
        self.assertIn("ownership", result["failure"])
        self.assertFalse(any(c["method"] == "Delete" for c in result["calls"]))

    def test_cleanup_tolerates_exact_objects_disappearing_without_retrying(self):
        for method, target in (("GET", "/applications/"), ("DELETE", "/applications/"),
                               ("DELETE", "/servicePrincipals/")):
            with self.subTest(method=method, target=target):
                result = self.execute(teardown=True, error_method=method, error_target=target)
                self.assertIsNone(result["failure"])
                attempted = [c for c in result["calls"]
                             if c["method"].upper() == method and target in c["target"]]
                self.assertEqual(len(attempted), 1)
                deletions = [c for c in result["calls"] if c["method"].upper() == "DELETE"]
                self.assertEqual(len(deletions), 0 if method == "GET" else 2)

    def test_cleanup_propagates_object_permission_and_server_errors(self):
        for method, target in (("GET", "/applications/"), ("DELETE", "/applications/"),
                               ("DELETE", "/servicePrincipals/")):
            for status in (403, 500):
                with self.subTest(method=method, target=target, status=status):
                    result = self.execute(teardown=True, error_method=method, error_target=target,
                                          error_status=status)
                    self.assertIn("Synthetic Graph operation failed", result["failure"])

    def test_cleanup_does_not_treat_missing_collections_as_success(self):
        for target in (r"/applications\?", r"/servicePrincipals\?"):
            with self.subTest(target=target):
                result = self.execute(teardown=True, error_method="GET", error_target=target)
                self.assertIn("Synthetic Graph operation failed", result["failure"])
                self.assertFalse(any(c["method"].upper() == "DELETE" for c in result["calls"]))


class SkillablePolicy(unittest.TestCase):
    def allowed(self, resource):
        policy = json.loads((ROOT / "infra" / "skillable" / "reactor2.access-policy.json").read_text())

        def evaluate(condition):
            if "allOf" in condition:
                return all(evaluate(item) for item in condition["allOf"])
            if "anyOf" in condition:
                return any(evaluate(item) for item in condition["anyOf"])
            if "not" in condition:
                return not evaluate(condition["not"])
            actual = resource.get(condition["field"])
            operation, expected = next((key, value) for key, value in condition.items() if key != "field")
            if operation == "lessOrEquals":
                return actual is not None and actual <= expected
            actual = str(actual).casefold()
            if operation == "in":
                return actual in [value.casefold() for value in expected]
            expected = expected.casefold()
            if operation == "equals":
                return actual == expected
            if operation == "notEquals":
                return actual != expected
            if operation == "contains":
                return expected in actual
            if operation == "like":
                self.assertLessEqual(expected.count("*"), 1)
                return re.fullmatch(".*".join(re.escape(part) for part in expected.split("*")), actual) is not None
            self.fail(f"Unsupported policy condition: {operation}")

        self.assertEqual(policy["then"]["effect"], "Deny")
        return not evaluate(policy["if"])

    def resource(self, kind, name, *, group="LAB722", full_name=None):
        return {
            "type": kind, "name": name, "fullName": full_name or name, "location": "westus3",
            "id": f"/subscriptions/example/resourceGroups/{group}/providers/{kind}/{name}",
        }

    def test_allows_allocated_reactor_apps_and_connections(self):
        for name in ("r2-front-hmetyzbtobp24", "r2-exec-hmetyzbtobp24"):
            with self.subTest(name=name):
                self.assertTrue(self.allowed(self.resource("Microsoft.App/containerApps", name)))
        for name in ("reactor-allocated-registry", "reactor-swarm-execution"):
            with self.subTest(name=name):
                self.assertTrue(self.allowed(self.resource(
                    "Microsoft.CognitiveServices/accounts/projects/connections", name,
                    full_name=f"lab722-hmetyzbtobp24-ai/reactor/{name}")))

    def test_denies_unrelated_apps_and_connection_boundaries(self):
        for name, group in (("other-app", "LAB722"), ("r2-front-test", "other-group")):
            with self.subTest(name=name, group=group):
                self.assertFalse(self.allowed(self.resource("Microsoft.App/containerApps", name, group=group)))
        kind = "Microsoft.CognitiveServices/accounts/projects/connections"
        for full_name, group in (
            ("lab722-test-ai/reactor/unrelated", "LAB722"),
            ("foreign-ai/reactor/reactor-allocated-registry", "LAB722"),
            ("lab722-test-ai/other-project/reactor-allocated-registry", "LAB722"),
            ("lab722-test-ai/reactor/reactor-allocated-registry", "other-group"),
        ):
            with self.subTest(full_name=full_name, group=group):
                self.assertFalse(self.allowed(self.resource(
                    kind, full_name.rsplit("/", 1)[1], group=group, full_name=full_name)))
        global_app = self.resource("Microsoft.App/containerApps", "r2-exec-test")
        global_app["location"] = "global"
        self.assertFalse(self.allowed(global_app))

    def test_preserves_original_model_and_registry_limits(self):
        kind = "Microsoft.CognitiveServices/accounts/deployments"
        model = self.resource(kind, "gpt-5.2")
        model.update({
            f"{kind}/model.name": "gpt-5.2", f"{kind}/sku.name": "GlobalStandard",
            f"{kind}/sku.capacity": 40,
        })
        self.assertTrue(self.allowed(model))
        model[f"{kind}/sku.capacity"] = 301
        self.assertFalse(self.allowed(model))
        model[f"{kind}/sku.capacity"] = 40
        model[f"{kind}/model.name"] = "other-model"
        self.assertFalse(self.allowed(model))
        kind = "Microsoft.ContainerRegistry/registries"
        registry = self.resource(kind, "lab722testacr")
        registry[f"{kind}/sku.name"] = "Basic"
        self.assertTrue(self.allowed(registry))
        registry[f"{kind}/sku.name"] = "Premium"
        self.assertFalse(self.allowed(registry))


if __name__ == "__main__":
    unittest.main()
