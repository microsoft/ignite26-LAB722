# 6. Meet the Agent team

The **orchestrator** is a persistent Microsoft Foundry agent named `caldova-orchestrator`. It assigns work to three specialists:

| Specialist | Task |
|---|---|
| Clinical trials | Implement `query_trials` in `trial_feature.py` |
| Drug safety | Implement `query_safety_reports` in `safety_feature.py` |
| Quality and governance | Review the combined result and report any blockers |

The two feature files are in `src\research-portal\backend`. The clinical specialist can change only the trial feature; the safety specialist can change only the safety feature. Neither can change the tests, source data, or frontend.

The **controller** is the supplied Python command-line program at `src\orchestrator\run.py`. You run it on the **lab VM**; the models run in **Foundry**. It uses **Model Context Protocol (MCP)** tools to send file-edit and test commands to the assigned **Sandboxes**, then collects the results. The Express application stays unchanged until you deploy an image.

Before running the team, review the plan. It should describe software changes, not medical recommendations. You make the separate human deployment decision after reviewing the image and target; an agent's recommendation is not approval.

## 6.1 Inspect the tasks and tools

Open the controller files in VS Code:

```powershell
. {
    $ErrorActionPreference = 'Stop'
    code .\src\orchestrator\contracts.py .\src\orchestrator\foundry.py .\src\orchestrator\sandbox.py
}
```

In `contracts.py`, find **APPROVED_TASKS**, which defines each specialist’s permitted assignment, and **Assignment.require_software_delivery_scope**, which rejects tasks that differ from that approved text. These checks prevent the agent from expanding or replacing the lab’s agreed software-development tasks.

In `sandbox.py`, find **WRITABLE_FILES** and **READABLE_FILES**, which control the files each specialist can access through the controller. Each implementor can change only its assigned feature file; tests remain read-only so the agent must fix the implementation rather than weaken the checks.

In `foundry.py`, find `self.tools`, which connects the Foundry agent to controlled Sandbox execution. **check_sandbox** verifies that commands can execute in the assigned Sandbox, while **dispatch_worker** runs an approved specialist assignment there. These tools turn the agent’s requests into bounded actions rather than unrestricted access.

In production systems the **tooling harness should always consist of enforced software boundaries, not just instructions asking a model to behave**. Leave them unchanged for this exercise.

<!-- pagebreak -->

# 7. Review the Agent Team's plan

## 7.1 Connect the controller to your lab resources

Use the prepared environment for the agent commands. The application environment you activated earlier remains in use for the other lab scripts.

This next block displays your model and Sandbox group, pauses, then uses the Foundry agent and calls the model to submit and plan our upcoming code changes. It does not create worker Sandboxes or edit application code. You will reuse its connection settings for the workers.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $plan = $controllerArgs = $null
    if (-not $readiness -or -not $readiness.application_ready -or
        -not $readiness.application_manifest_verified -or -not $readiness.frozen_data_verified) {
        throw 'Complete the starter application step with all three verification checks True before generating the plan.'
    }
    if ([string]::IsNullOrWhiteSpace($env:LAB_DATA_MANIFEST) -or
        -not (Test-Path -LiteralPath $env:LAB_DATA_MANIFEST -PathType Leaf) -or
        $env:LAB_DATA_MANIFEST_SHA256 -cnotmatch '^[a-f0-9]{64}$' -or
        $env:LAB_STARTUP_PURPOSE -cne 'public-lab-development') {
        throw 'The verified local dataset session is missing. Rerun the starter application helper in this PowerShell window before generating the plan.'
    }
    $controllerPython = Join-Path $env:LOCALAPPDATA 'Caldova\venvs\controller\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $controllerPython -PathType Leaf)) {
        throw 'The prepared controller environment is missing. Contact your instructor.'
    }
    $acaExecutable = (Get-Command aca -CommandType Application | Select-Object -First 1).Source
    $controllerArgs = @(
        '-m', 'src.orchestrator.run'
        '--project-endpoint', $labOutputs.FOUNDRY_PROJECT_ENDPOINT
        '--model', $labOutputs.FOUNDRY_MODEL_DEPLOYMENT_NAME
        '--subscription', $labOutputs.AZURE_SUBSCRIPTION_ID
        '--resource-group', $resourceGroupName
        '--region', $labOutputs.SANDBOX_REGION
        '--group', $labOutputs.SANDBOX_GROUP_NAME
        '--aca', $acaExecutable
    )
    $labOutputs | Select-Object FOUNDRY_MODEL_DEPLOYMENT_NAME, SANDBOX_GROUP_NAME | Format-List | Out-Host
    [void] (Read-Host 'Check your model and Sandbox group, then press Enter to generate the plan')
    $planText = & $controllerPython @controllerArgs --mode plan --manifest $env:LAB_DATA_MANIFEST
    if ($LASTEXITCODE -ne 0) { throw 'Planning failed. Keep the displayed failure.json path and contact your instructor.' }
    $plan = ($planText -join "`n") | ConvertFrom-Json
    $plan.plan.assignments | Format-List role, task, acceptance_criteria | Out-Host
    [void] (Read-Host 'Review the three assignments, then press Enter to inspect the release requirement')
    $plan.plan | Select-Object run_id, dataset_version, release_requires_human_approval
}
```
**Learning:**

Review the plan as a proposal that must satisfy the lab’s rules, not as permission to deploy. Check that it contains three assignments covering clinical-trials implementation, drug-safety implementation and governance review. Confirm that it preserves the fixed data and tests and requires human approval before release. **You are checking that the proposed work is complete, stays within scope and leaves release decisions with a human.**

Match each assignment to APPROVED_TASKS: **the approved contract—not the model’s response—defines what each specialist may do**. Identify the clinical specialist’s permitted feature file, and reject proposals to change the tests. The tests are fixed acceptance criteria in this lab; the agent must improve its implementation rather than weaken the checks used to judge it.

**Checkpoint:** you can explain each specialist's responsibility, why the model is not in charge of the plan and why we still have a human-in-the-loop and what they do.



**Optional Notes:**

Progress appears in the terminal while the JSON result is captured. Each run saves its result or `failure.json` under `.validation-workspaces\agent-runs\<run-id>`.

If Foundry returns **403**, stop and contact your instructor. For **429**, keep the saved failure and ask the instructor to check this model's actual rate limits and quota before retrying. A successful resource check does not establish Foundry data access or sufficient throughput.
