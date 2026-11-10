import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
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


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 required")
class LocalResearchPreparation(unittest.TestCase):
    def run_research(self, *, mismatch=False, hosted_failed=False):
        source = str(ROOT / "scripts" / "prepare-local-reactor.ps1").replace("'", "''")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scripts.mkdir()
            (root / "data").mkdir()
            shutil.copyfile(ROOT / "data" / "reactor-research-images.json",
                            root / "data" / "reactor-research-images.json")
            (scripts / "prepare-reactor-swarm.ps1").write_text("""
param($AllocationValues,$ImageCatalogPath,$PythonExecutable,$AlicePassword,$BobPassword)
$global:events.Add(@{kind='swarm';allocation=$AllocationValues;
    catalog=(Get-Content $ImageCatalogPath -Raw|ConvertFrom-Json)})
[pscustomobject]@{
    SubscriptionId=$AllocationValues.SubscriptionId;ResourceGroupName=$AllocationValues.ResourceGroupName
    ProjectEndpoint=$AllocationValues.ProjectEndpoint;HostedName='reactor-research-orchestrator'
    HostedVersion='7';HostedEndpoint='https://hosted.example/responses?api-version=v1'
    FrontendName='research-frontend';FrontendUrl='https://frontend.example';HostedConnected=$false
}
""", encoding="utf-8")
            (scripts / "connect-reactor-frontend.ps1").write_text("""
param($SubscriptionId,$ResourceGroupName,$FrontendName,$ProjectEndpoint,$AgentName,$HostedResponsesEndpoint)
$global:events.Add(@{kind='connect';frontend=$FrontendName;endpoint=$HostedResponsesEndpoint})
$global:connected=$true
""", encoding="utf-8")
            program = r"""
$ErrorActionPreference='Stop'
$ast=[System.Management.Automation.Language.Parser]::ParseFile('__SOURCE__',[ref]$null,[ref]$null)
foreach ($statement in $ast.EndBlock.Statements) {
    if ($statement -is [System.Management.Automation.Language.FunctionDefinitionAst]) {
        . ([scriptblock]::Create($statement.Extent.Text))
    }
}
$global:events=[Collections.Generic.List[object]]::new()
$global:connected=$false
$configFixture=@{
    AZURE_ENV_NAME='research';AZURE_SUBSCRIPTION_ID='11111111-1111-1111-1111-111111111111'
    AZURE_RESOURCE_GROUP='local-group';AZURE_LOCATION='westus3';LAB_USER_PRINCIPAL_ID='operator'
    FOUNDRY_ACCOUNT_NAME='account';FOUNDRY_PROJECT_NAME='reactor'
    FOUNDRY_PROJECT_ENDPOINT='https://account.services.ai.azure.com/api/projects/reactor'
    FOUNDRY_MODEL_DEPLOYMENT_NAME='gpt-5.2';EXPRESS_ENVIRONMENT_NAME='express'
    SANDBOX_GROUP_NAME='sandboxes';AZURE_CONTAINER_REGISTRY_NAME='localregistry'
    REACTOR_PYTHON='Invoke-FakePython'
}
function Read-LocalEnvironment { return $configFixture }
function Ensure-ReactorRole { param($Scope,$Principal,$Role,$PrincipalType) }
function Invoke-LocalNative {
    param($Executable,$Arguments)
    if ($Executable -eq 'aca') { return '[]' }
    if ($Executable -eq 'azd') {
        $global:events.Add(@{kind='state';arguments=$Arguments})
        return ''
    }
    if ($Arguments[0] -eq 'account') {
        return (@{id=$configFixture.AZURE_SUBSCRIPTION_ID;state='Enabled'}|ConvertTo-Json)
    }
    if ($Arguments[1] -eq 'import') {
        $global:events.Add(@{kind='import';arguments=$Arguments})
        return ''
    }
    if ($Arguments[2] -eq 'list') { return '[]' }
    if ($Arguments[2] -eq 'show') {
        $digest=(Get-Content '__ROOT__\data\reactor-research-images.json' -Raw|ConvertFrom-Json).hosted_image.Split('@')[1]
        if (__MISMATCH__) { $digest='sha256:wrong' }
        return (@{digest=$digest}|ConvertTo-Json)
    }
    throw "Unexpected native call: $Executable $Arguments"
}
function Invoke-ReactorArm {
    param($Method,$ResourceId,$Version,$Body)
    if ($ResourceId.EndsWith('/connections/reactor-allocated-registry')) {
        if ($Method -eq 'PUT') {
            $global:events.Add(@{kind='registry';body=$Body})
            return
        }
        return @{properties=@{authType='ManagedIdentity';target='localregistry.azurecr.io'
            metadata=@{ResourceId=($ResourceId.Split('/providers/Microsoft.CognitiveServices')[0] +
                '/providers/Microsoft.ContainerRegistry/registries/localregistry')}}}
    }
    if ($ResourceId.EndsWith('/registries/localregistry')) {
        return @{name='localregistry';tags=@{lab='LAB722';'azd-env-name'='research'}
            properties=@{loginServer='localregistry.azurecr.io'}}
    }
    return @{identity=@{principalId='project-principal'}}
}
function Invoke-FakePython {
    $global:LASTEXITCODE=0
    '{"audience":"api://dedicated-execution"}'
}
function Wait-LocalHosted {
    param($Name,$Version)
    $global:events.Add(@{kind='wait';name=$Name;version=$Version})
    if (__HOSTED_FAILED__) { throw 'Exact hosted version failed.' }
}
function Invoke-RestMethod {
    param($Uri)
    return @{hosted_configured=$global:connected}
}
$Mode='Research';$ServiceManagementReference=[securestring]::new()
$AlicePassword=$null;$BobPassword=$null
$main=($ast.EndBlock.Statements|Where-Object {
    $_ -isnot [System.Management.Automation.Language.FunctionDefinitionAst]
}|ForEach-Object {$_.Extent.Text}) -join "`n"
$main='$PSScriptRoot=''__ROOT__\scripts'';' + $main
$failure=''
try { . ([scriptblock]::Create($main)) } catch { $failure=$_.Exception.Message }
$values='__ROOT__\.build-contexts\research-research\learner-values.json'
@{failure=$failure;events=@($global:events.ToArray());saved=(Test-Path $values)}|
    ConvertTo-Json -Depth 20 -Compress
"""
            program = (program.replace("__SOURCE__", source)
                       .replace("__ROOT__", str(root).replace("'", "''"))
                       .replace("__MISMATCH__", "$true" if mismatch else "$false")
                       .replace("__HOSTED_FAILED__", "$true" if hosted_failed else "$false"))
            result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", program],
                                    text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout.splitlines()[-1])
            output["root"] = str(root)
            return output

    def test_research_mirrors_current_image_waits_then_connects_frontend_and_saves_root_state(self):
        result = self.run_research()
        self.assertEqual(result["failure"], "")
        kinds = [event["kind"] for event in result["events"]]
        self.assertEqual(kinds, ["import", "registry", "swarm", "wait", "connect", "state"])
        swarm = next(event for event in result["events"] if event["kind"] == "swarm")
        self.assertEqual(swarm["allocation"]["ExecutionApiAudience"], "api://dedicated-execution")
        catalog = json.loads((ROOT / "data" / "reactor-research-images.json").read_text())
        self.assertEqual(swarm["catalog"]["hosted_image"],
                         catalog["hosted_image"].replace("acateam.azurecr.io", "localregistry.azurecr.io"))
        self.assertEqual(swarm["catalog"]["agent_image"], catalog["agent_image"])
        self.assertEqual(swarm["catalog"]["service_image"], catalog["service_image"])
        wait = next(event for event in result["events"] if event["kind"] == "wait")
        self.assertEqual(wait["version"], "7")
        state = result["events"][-1]["arguments"]
        self.assertEqual(state[:5], ["-C", result["root"], "env", "set", "RESEARCH_PREPARED_STATE"])
        self.assertTrue(json.loads(state[5])["HostedConnected"])
        self.assertTrue(result["saved"])

    def test_mirror_digest_mismatch_stops_before_connection_or_deployment(self):
        result = self.run_research(mismatch=True)
        self.assertIn("digest differs", result["failure"])
        self.assertEqual([event["kind"] for event in result["events"]], ["import"])
        self.assertFalse(result["saved"])

    def test_failed_exact_version_does_not_connect_or_claim_readiness(self):
        result = self.run_research(hosted_failed=True)
        self.assertIn("Exact hosted version failed", result["failure"])
        self.assertNotIn("connect", [event["kind"] for event in result["events"]])
        self.assertNotIn("state", [event["kind"] for event in result["events"]])
        self.assertFalse(result["saved"])

    def test_saved_swarm_cannot_silently_reuse_a_different_hosted_image(self):
        catalog = json.loads((ROOT / "data" / "reactor-research-images.json").read_text())
        allocation = {
            "SubscriptionId": "subscription", "ResourceGroupName": "group", "Region": "westus3",
            "SandboxGroupName": "sandboxes", "ProjectEndpoint": "https://project.example",
            "FoundryAccountName": "account", "FoundryProjectName": "project",
            "ExpressEnvironmentName": "express", "ExecutionApiAudience": "api://execution", "Model": "model",
        }
        prepared = {
            **allocation, "ServiceImage": catalog["service_image"], "AgentImage": catalog["agent_image"],
            "HostedImage": catalog["hosted_image"], "FrontendName": "lab722-research-frontend",
            "ExecutionName": "lab722-research-execution", "HostedName": "reactor-research-orchestrator",
        }
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "prepared.json"
            for mismatch in (False, True):
                with self.subTest(mismatch=mismatch):
                    state.write_text(json.dumps({**prepared, "HostedImage":
                                                 "other.azurecr.io/image@sha256:wrong" if mismatch
                                                 else catalog["hosted_image"]}), encoding="utf-8")
                    script = str(ROOT / "scripts" / "prepare-reactor-swarm.ps1").replace("'", "''")
                    values = json.dumps(allocation).replace("'", "''")
                    program = (
                        f"$ErrorActionPreference='Stop'; $base='{values}'|ConvertFrom-Json -AsHashtable;"
                        f"& '{script}' -Mode Values -AllocationValues $base "
                        f"-PreparedStatePath '{str(state).replace(chr(39), chr(39)*2)}'|Out-Null"
                    )
                    result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", program],
                                            text=True, capture_output=True, timeout=30)
                    if mismatch:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("Prepared images differ", result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
