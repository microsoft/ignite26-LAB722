# Segment 2 - Configure the orchestrator (target: 15 minutes)

**Goal:** inspect or create a grounded three-role software plan. **Why:** planning must preserve source ownership and deterministic acceptance, not drift into clinical conclusions. **Services:** Microsoft Foundry Agent Service, Microsoft Agent Framework and the controller-owned stdio MCP bridge. **Outcome:** three bounded assignments, a pinned dataset identity and a separate human-execution boundary.

The implementation uses the Python SDK to provision or reuse the persistent `caldova-orchestrator` prompt agent. It is not a manual portal exercise attaching GitHub MCP and an HTTP Sandbox endpoint. The supplied source is staged read-only; the local controller launches the stdio Sandbox bridge and binds each remote operation to its assigned workspace.

## Recorded-evidence path

Continue in the terminal from Segment 0:

```powershell
$evidence.assignments | Format-List role, task, acceptance_criteria
$evidence.workers | Format-Table role, sandbox_id
$evidence.dataset | Format-List dataset_version, logical_sha256, acceptance_purpose
```

Read the exact responsibilities:

| Role | Permitted responsibility | Acceptance |
|---|---|---|
| `clinical-trials` | `query_trials(connection, candidate, condition)` in `src/research-portal/backend/trial_feature.py` | Trial records and citations; preserve all associated arrays |
| `drug-safety` | `query_safety_reports(connection, candidate)` in `src/research-portal/backend/safety_feature.py` | Normalization, citations and responsible use; never condition-filter safety mentions |
| `quality-governance` | Validate the independently integrated candidate and report blockers | Schema, acceptance, limitations and real egress evidence; never approve release |

Inspect `src\orchestrator\contracts.py`: the planner must keep the exact approved tasks and per-role checks. `ImplementationPlan` binds the run, dataset version and logical hash and requires human release approval. In `src\orchestrator\foundry.py`, the stored tool declarations and local implementations must match. An unrelated agent without the lab ownership marker is not silently overwritten.

## Live-exercise path

The facilitator must supply an already authenticated, supported Python controller runtime and `aca` on `PATH`, the read-only `$readiness` report from Segment 0, and the checksum-pinned local manifest. Do not install packages, infer an attendee identity or grant yourself roles in this segment.

The following creates/reuses a persistent agent and invokes planning; it is **not a read-only check** and requires facilitator authorization. Prepare one reusable argument array:

```powershell
$controllerPython = (Get-Command python -CommandType Application |
    Select-Object -First 1).Source
$acaExecutable = (Get-Command aca -CommandType Application |
    Select-Object -First 1).Source
$controllerArgs = @(
    '-m', 'src.orchestrator.run'
    '--project-endpoint', $readiness.outputs.FOUNDRY_PROJECT_ENDPOINT
    '--model', $readiness.outputs.FOUNDRY_MODEL_DEPLOYMENT_NAME
    '--subscription', $readiness.outputs.AZURE_SUBSCRIPTION_ID
    '--resource-group', $readiness.outputs.AZURE_RESOURCE_GROUP
    '--region', $readiness.outputs.SANDBOX_REGION
    '--group', $readiness.outputs.SANDBOX_GROUP_NAME
    '--aca', $acaExecutable
)
$planText = & $controllerPython @controllerArgs --mode plan --manifest $env:LAB_DATA_MANIFEST
if ($LASTEXITCODE -ne 0) { throw 'Planning failed. Preserve its diagnostics and stop.' }
$plan = ($planText -join "`n") | ConvertFrom-Json
$plan.plan.assignments | Format-List role, task, acceptance_criteria
$plan.plan | Select-Object run_id, dataset_version, logical_sha256, release_requires_human_approval
```

Match the manifest/dataset to the trusted startup pins, review all three assignments and reject any medical-analysis or expanded-write task. Planning does not allocate Sandboxes, approve publication or deploy an image. A later `workers` invocation creates its own run and plan; this displayed plan is a review of the contract, not a persisted authorization silently reused by another run.

**Windows ARM maintainer note:** the tested controller currently uses the existing Linux runtime and token-through-stdin WSL launcher, not the stdlib-only native environment. See [the facilitator handoff](facilitator.md); do not assume that every interpreter called `python` has the controller dependencies.

## Checkpoint

You can identify all three assignments, their exact ownership and the data/run identity. Explain why the persistent agent cannot independently select another worker's scope or authorize release.

| Symptom | Safe response |
|---|---|
| Foundry agent access is forbidden | Facilitator verifies project-scoped data-plane permission; management ownership is not enough |
| A controller import is missing | Stop and use the prepared supported runtime; do not install into an arbitrary shared interpreter |
| Plan adds clinical recommendations or unrelated files | Reject it and preserve the failed result; do not weaken the plan contract |
| MCP connection is missing | Inspect the supplied stdio bridge/runtime configuration, not a fictitious portal connection |
