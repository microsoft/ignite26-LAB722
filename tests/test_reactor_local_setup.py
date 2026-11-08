import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import Mock, patch

import requests


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_reactor_api", ROOT / "scripts" / "prepare-reactor-api.py")
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)


class DedicatedApiPreparation(unittest.TestCase):
    def setUp(self):
        self.app = {
            "id": "app-object", "appId": "app-client",
            "notes": "LAB722 local reactor: subscription/local-group",
            "signInAudience": "AzureADMyOrg", "identifierUris": ["api://app-client"],
            "api": {"requestedAccessTokenVersion": 1},
        }
        self.principal = {"id": "principal", "appId": "app-client", "appRoleAssignmentRequired": False}

    def test_reuses_only_exact_owned_api_without_writes(self):
        graph = Mock()
        graph.call.side_effect = [
            {"value": [self.app]}, self.app, {"value": [self.principal]}, self.principal,
        ]
        result = API.prepare(graph, "subscription", "local-group", "private-input")
        self.assertEqual(result["audience"], "api://app-client")
        self.assertTrue(all(call.args[0] == "GET" for call in graph.call.call_args_list))

    def test_foreign_name_match_is_never_changed(self):
        graph = Mock()
        graph.call.return_value = {"value": [{**self.app, "notes": "another allocation"}]}
        with self.assertRaisesRegex(RuntimeError, "not this allocation"):
            API.prepare(graph, "subscription", "local-group", "private-input")
        self.assertEqual(graph.call.call_count, 1)

    def test_new_api_retries_only_definite_principal_404_once(self):
        graph = Mock()
        graph.call.side_effect = [
            {"value": []}, {**self.app, "identifierUris": []}, {}, self.app,
            {"value": []}, API.GraphError(404, "not_found"), self.principal, self.principal,
        ]
        sleep = Mock()
        API.prepare(graph, "subscription", "local-group", "private-input", sleep=sleep)
        sleep.assert_called_once_with(15)
        posts = [call for call in graph.call.call_args_list
                 if call.args == ("POST", "servicePrincipals")]
        self.assertEqual(len(posts), 2)
        self.assertTrue(all(call.kwargs["json"] == {"appId": "app-client"} for call in posts))

    def test_assignment_required_policy_is_not_overridden(self):
        graph = Mock()
        restricted = {**self.principal, "appRoleAssignmentRequired": True}
        graph.call.side_effect = [
            {"value": [self.app]}, self.app, {"value": [restricted]}, restricted,
        ]
        with self.assertRaisesRegex(RuntimeError, "policy differs"):
            API.prepare(graph, "subscription", "local-group", "")
        self.assertTrue(all(call.args[0] == "GET" for call in graph.call.call_args_list))

    def test_uncertain_transport_is_not_retried_or_leaked(self):
        credential = Mock()
        credential.get_token.return_value.token = "synthetic-bearer"
        with patch.object(API.requests, "request", side_effect=requests.Timeout("private-input")) as request:
            with self.assertRaisesRegex(RuntimeError, "uncertain") as error:
                API.Graph(credential).call("POST", "applications", json={"serviceManagementReference": "private-input"})
        self.assertEqual(request.call_count, 1)
        self.assertNotIn("private-input", str(error.exception))
        self.assertNotIn("synthetic-bearer", str(error.exception))


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 required")
class LocalEndpointHandoff(unittest.TestCase):
    def test_bodyless_arm_actions_send_json_content_type(self):
        path = str(ROOT / "scripts" / "prepare-local-reactor.ps1").replace("'", "''")
        program = f"""
$ErrorActionPreference='Stop'
$ast=[System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$null,[ref]$null)
$function=$ast.Find({{param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Invoke-ReactorArm'}},$true)
. ([scriptblock]::Create($function.Extent.Text))
$config=@{{AZURE_SUBSCRIPTION_ID='test'}}
function Invoke-LocalNative {{ return '{{"accessToken":"synthetic"}}' }}
function Invoke-RestMethod {{
    param($Uri,$Method,$Headers,$ContentType,$Body)
    @{{method=$Method;contentType=$ContentType;body=$Body}}
}}
Invoke-ReactorArm POST '/app/stop' '2026-03-02-preview' | ConvertTo-Json -Compress
"""
        result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", program],
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        request = json.loads(result.stdout)
        self.assertEqual(request["contentType"], "application/json")
        self.assertIsNone(request["body"])

    def test_registry_creation_retains_identity_fields_omitted_by_get(self):
        path = str(ROOT / "scripts" / "prepare-local-reactor.ps1").replace("'", "''")
        program = f"""
$ast=[System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$null,[ref]$null)
$function=$ast.Find({{param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'New-ReactorConnectionBody'}},$true)
. ([scriptblock]::Create($function.Extent.Text))
$body=New-ReactorConnectionBody 'acateam.azurecr.io' '' '/subscriptions/test/resourceGroups/registry/providers/Microsoft.ContainerRegistry/registries/acateam' 'project-principal'
$body | ConvertTo-Json -Depth 10 -Compress
"""
        result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", program],
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        properties = json.loads(result.stdout)["properties"]
        self.assertEqual(properties["credentials"]["clientId"], "project-principal")
        self.assertEqual(properties["credentials"]["resourceId"], properties["metadata"]["ResourceId"])

    def test_registry_creation_rejects_missing_project_identity(self):
        path = str(ROOT / "scripts" / "prepare-local-reactor.ps1").replace("'", "''")
        program = f"""
$ErrorActionPreference='Stop'
$ast=[System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$null,[ref]$null)
$function=$ast.Find({{param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'New-ReactorConnectionBody'}},$true)
. ([scriptblock]::Create($function.Extent.Text))
New-ReactorConnectionBody 'acateam.azurecr.io' '' '/registry' ''
"""
        result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", program],
                                text=True, capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires the actual project principal", result.stderr)

    def run_handoff(self, active_tasks=False, stop_fails=False, other_project=False):
        path = str(ROOT / "scripts" / "prepare-local-reactor.ps1").replace("'", "''")
        program = r"""
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile('__PATH__',[ref]$tokens,[ref]$errors)
if ($errors) { throw ($errors | Out-String) }
$PSScriptRoot=Split-Path -Parent '__PATH__'
foreach ($statement in $ast.EndBlock.Statements) {
    if ($statement -is [System.Management.Automation.Language.FunctionDefinitionAst]) {
        . ([scriptblock]::Create($statement.Extent.Text))
    }
}
$script:configFixture=@{
    AZURE_ENV_NAME='local'; AZURE_SUBSCRIPTION_ID='11111111-1111-1111-1111-111111111111'
    AZURE_RESOURCE_GROUP='local-group'; AZURE_LOCATION='westus3'
    FOUNDRY_ACCOUNT_NAME='account'; FOUNDRY_PROJECT_NAME='reactor'
    FOUNDRY_PROJECT_ENDPOINT='https://account.services.ai.azure.com/api/projects/reactor'
    FOUNDRY_MODEL_DEPLOYMENT_NAME='gpt-5.2'; EXPRESS_ENVIRONMENT_NAME='express'
    SANDBOX_GROUP_NAME='sandboxes'; REACTOR_PREPARED='true'
    REACTOR_PREPARED_PROJECT='/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/local-group/providers/Microsoft.CognitiveServices/accounts/account/projects/reactor'
    REACTOR_SERVICE_IMAGE='acateam.azurecr.io/lab722/reactor-services@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    REACTOR_FRONTEND_URL='https://frontend.example'; REACTOR_EXECUTION_URL='https://execution.example'
}
if (__OTHER__) { $script:configFixture.REACTOR_PREPARED_PROJECT += '-other' }
$script:events=[Collections.Generic.List[object]]::new()
$script:stopped=$false
$script:app=[pscustomobject]@{properties=[pscustomobject]@{
    provisioningState='Succeeded'; runningStatus='Running'
    template=[pscustomobject]@{containers=@([pscustomobject]@{
        name='frontend'; image=$script:configFixture.REACTOR_SERVICE_IMAGE
        env=@([pscustomobject]@{name='FRONTEND_PUBLIC_ORIGIN';value='https://frontend.example'},
              [pscustomobject]@{name='HOSTED_RESPONSES_ENDPOINT';value=''})
    })}
}}
function Read-LocalEnvironment { return $script:configFixture }
function Invoke-LocalNative {
    param($Executable,$Arguments)
    if ($Executable -eq 'az') {
        return (@{id=$script:configFixture.AZURE_SUBSCRIPTION_ID;state='Enabled'}|ConvertTo-Json)
    }
    if ($Executable -eq 'aca') {
        if (__ACTIVE__) { return '[{"id":"owned-active-task"}]' }
        return '[]'
    }
    if ($Executable -eq 'azd') { return '' }
    throw 'Unexpected native call'
}
function Invoke-ReactorArm {
    param($Method,$ResourceId,$Version,$Body)
    $script:events.Add(@{method=$Method;id=$ResourceId})
    if ($Method -eq 'GET') {
        $script:app.properties.runningStatus=if($script:stopped){'Stopped'}else{'Running'}
        return $script:app
    }
    if ($Method -eq 'PATCH') {
        $script:app.properties.template=$Body.properties.template
    }
    if ($ResourceId.EndsWith('/stop')) {
        if (__STOP_FAILS__) { throw 'Simulated Stop failure' }
        $script:stopped=$true
    }
    if ($ResourceId.EndsWith('/start')) { $script:stopped=$false }
}
function Start-Sleep { param($Seconds) }
function Invoke-WebRequest {
    param($Uri,[switch]$SkipHttpErrorCheck,$TimeoutSec)
    return [pscustomobject]@{StatusCode=200;Content='{"hosted_configured":true,"csrf":"synthetic"}'}
}
$Mode='Connect'
$HostedResponsesEndpoint=[uri]'https://account.services.ai.azure.com/api/projects/reactor/agents/reactor-orchestrator/endpoint/protocols/openai/responses?trace=keep'
$main=($ast.EndBlock.Statements|Where-Object {$_ -isnot [System.Management.Automation.Language.FunctionDefinitionAst]}|ForEach-Object {$_.Extent.Text}) -join "`n"
$main='$PSScriptRoot=Split-Path -Parent ''__PATH__'';' + $main
$failure=''
try { . ([scriptblock]::Create($main)) } catch { $failure=$_.Exception.Message }
@{failure=$failure;events=@($script:events.ToArray());env=$script:app.properties.template.containers[0].env}|ConvertTo-Json -Depth 10 -Compress
"""
        program = (program.replace("__PATH__", path)
                   .replace("__ACTIVE__", "$true" if active_tasks else "$false")
                   .replace("__STOP_FAILS__", "$true" if stop_fails else "$false")
                   .replace("__OTHER__", "$true" if other_project else "$false"))
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-Command", program],
            text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.splitlines(), result.stderr)
        return json.loads(result.stdout.splitlines()[-1])

    def test_connect_updates_only_frontend_and_preserves_query_and_origin(self):
        result = self.run_handoff()
        self.assertEqual(result["failure"], "")
        self.assertTrue(all("containerApps/lab722-reactor-frontend" in event["id"]
                            for event in result["events"]))
        env = {entry["name"]: entry["value"] for entry in result["env"]}
        self.assertEqual(env["FRONTEND_PUBLIC_ORIGIN"], "https://frontend.example")
        self.assertTrue(env["HOSTED_RESPONSES_ENDPOINT"].endswith("?trace=keep&api-version=v1"))
        self.assertTrue(result["events"][-1]["id"].endswith("/start"))

    def test_active_tasks_block_all_configuration_changes(self):
        result = self.run_handoff(active_tasks=True)
        self.assertIn("Reconcile existing owned tasks", result["failure"])
        self.assertEqual(result["events"], [])

    def test_stop_failure_still_restores_frontend_start(self):
        result = self.run_handoff(stop_fails=True)
        self.assertIn("Simulated Stop failure", result["failure"])
        self.assertTrue(result["events"][-1]["id"].endswith("/start"))

    def test_prepared_marker_cannot_be_reused_for_another_project(self):
        result = self.run_handoff(other_project=True)
        self.assertIn("different project", result["failure"])
        self.assertEqual(result["events"], [])


if __name__ == "__main__":
    unittest.main()
