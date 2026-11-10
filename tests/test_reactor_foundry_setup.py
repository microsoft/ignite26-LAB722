import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch


spec = importlib.util.spec_from_file_location(
    "reactor_foundry_setup", Path(__file__).parents[1] / "scripts" / "setup-reactor-foundry.py"
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class HostedReuse(unittest.IsolatedAsyncioTestCase):
    async def check_reuse(self, exact_status):
        args = SimpleNamespace(
            command="hosted", name="reactor", project_endpoint="https://project.test",
            image="registry.test/hosted@sha256:" + "a" * 64,
            model="model", toolbox_endpoint="https://project.test/toolbox",
            operation="reactor_execute", describe=False, new_version=False,
        )
        definition = setup.definitions(args).as_dict()
        fingerprint = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
        listed = SimpleNamespace(
            version="4", status="active", metadata={"reactor_config_sha256": fingerprint}
        )
        exact = SimpleNamespace(version="4", status=exact_status)

        async def versions():
            yield listed

        agents = SimpleNamespace(
            list_versions=Mock(return_value=versions()),
            get_version=AsyncMock(return_value=exact),
            create_version=AsyncMock(),
        )
        project = AsyncMock()
        project.__aenter__.return_value = SimpleNamespace(agents=agents)
        credential = AsyncMock()
        with patch.object(setup, "AIProjectClient", return_value=project), \
                patch.object(setup, "AzureCliCredential", return_value=credential), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            await setup.run(args)
        agents.get_version.assert_awaited_once_with("reactor", "4")
        agents.create_version.assert_not_awaited()
        return json.loads(output.getvalue())

    async def test_aggregate_active_does_not_hide_failed_exact_version(self):
        with self.assertRaisesRegex(RuntimeError, "existing hosted version failed"):
            await self.check_reuse("failed")

    async def test_reused_version_reports_exact_provisioning_status(self):
        result = await self.check_reuse("creating")
        self.assertEqual(result["status"], "creating")
        self.assertTrue(result["reused"])

    async def check_explicit_creation(self, ignore_creation_metadata=False):
        args = SimpleNamespace(
            command="hosted", name="reactor", project_endpoint="https://project.test",
            image="registry.test/hosted@sha256:" + "a" * 64,
            model="model", toolbox_endpoint="https://project.test/toolbox",
            operation="reactor_execute", describe=False, new_version=True,
        )
        definition = setup.definitions(args).as_dict()
        fingerprint = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
        previous_metadata = {"lab": "LAB722", "reactor_config_sha256": fingerprint}
        previous = SimpleNamespace(version="4", metadata=previous_metadata)

        async def versions():
            yield previous

        async def create_version(name, *, definition, metadata):
            if ignore_creation_metadata or metadata == previous_metadata:
                return previous
            return SimpleNamespace(version="5", status="creating")

        agents = SimpleNamespace(
            list_versions=Mock(side_effect=lambda *a, **k: versions()),
            create_version=AsyncMock(side_effect=create_version),
        )
        project = AsyncMock()
        project.__aenter__.return_value = SimpleNamespace(agents=agents)
        with patch.object(setup, "AIProjectClient", return_value=project), \
                patch.object(setup, "AzureCliCredential", return_value=AsyncMock()), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            await setup.run(args)
        return json.loads(output.getvalue())

    async def test_explicit_creation_is_not_deduplicated_with_prepared_version(self):
        result = await self.check_explicit_creation()
        self.assertEqual(result["version"], "5")
        self.assertFalse(result["reused"])

    async def test_explicit_creation_rejects_existing_version_response(self):
        with self.assertRaisesRegex(RuntimeError, "returned the existing version"):
            await self.check_explicit_creation(ignore_creation_metadata=True)


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required for the deployment helper")
class HostedEndpointHandoff(unittest.TestCase):
    def test_portal_endpoint_queries_and_unconnected_input(self):
        helper = str(Path(__file__).parents[1] / "scripts" / "deploy-reactor.ps1").replace("'", "''")
        script = """
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile('HELPER', [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Helper parse failed' }
$nodes = @($ast.FindAll({
    param($n)
    $n -is [Management.Automation.Language.IfStatementAst] -and
    $n.Extent.Text.Contains('$HostedResponsesEndpoint.Query')
}, $true))
if ($nodes.Count -ne 1) { throw 'Expected one endpoint normalization block' }
$normalize = [scriptblock]::Create($nodes[0].Extent.Text)
$result = foreach ($inputUri in @(
    'https://project.test/responses',
    'https://project.test/responses?trace=1',
    'https://project.test/responses?api-version=v1&trace=1',
    $null
)) {
    $HostedResponsesEndpoint = if ($null -eq $inputUri) { $null } else { [uri]$inputUri }
    . $normalize
    @{ endpoint = if ($null -eq $HostedResponsesEndpoint) { $null } else { $HostedResponsesEndpoint.AbsoluteUri } }
}
ConvertTo-Json -InputObject @($result) -Compress
""".replace("HELPER", helper)
        result = subprocess.run(
            [shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [row["endpoint"] for row in json.loads(result.stdout)],
            [
                "https://project.test/responses?api-version=v1",
                "https://project.test/responses?trace=1&api-version=v1",
                "https://project.test/responses?api-version=v1&trace=1",
                None,
            ],
        )
