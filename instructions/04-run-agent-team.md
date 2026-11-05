# 12. Run the agent team

The workspaces are ready. Now authorize the specialists to implement and review the two features.

You are now asking the specialists to implement the starter application’s two missing query functions. Unlike the previous tool-execution check, this run allows actual changes to the assigned feature files.

The Python controller on your VM generates and validates a fresh plan similar to the one we saw earlier. Then it checks that each specialist is connected to its own registered Sandbox clone. The clinical-trials specialist implements the trial feature; the drug-safety specialist implements the safety feature. They use MCP tools to inspect permitted files, change their assigned source file and verify their implementation. The changes happen in the remote Sandboxes and not on your VM.

Once both implementations pass the controller’s checks, it copies only their two accepted feature files into the primary and governance sandboxes. The primary runs independent integration and application-acceptance tests against the combined code, preserving the existing tests and frozen data. Only after integration passes does the governance specialist review the combined candidate and its evidence.

This demonstrates why isolated development must be followed by controlled integration and independent verification: two individually passing workers do not automatically produce a working application. The outcome is candidate code and supporting evidence.

## 12.1 Start the workers

`--approve-plan` authorizes this worker run. It does **not** authorize an image build or deployment.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $result = $null
    $resultPath = $null
    $resultSha256 = $null
    $candidateImage = $null
    [void] (Read-Host 'Press Enter to authorize the two implementors, independent tests and final governance review')
    $resultText = & $controllerPython @controllerArgs --mode workers `
        --manifest $preparedManifestPath --bindings $bindingsPath `
        --validation-sandbox-id $validationSandboxId --approve-plan
    if ($LASTEXITCODE -ne 0) {
        throw 'Worker run failed. Keep the displayed failure.json; use the end-of-segment catch-up note, not a build.'
    }
    $resultJson = $resultText -join "`n"
    $result = $resultJson | ConvertFrom-Json
    $runId = $result.plan.run_id
    $runDirectory = Join-Path '.validation-workspaces\agent-runs' $runId
    $resultPath = Join-Path $runDirectory 'worker-result.json'
    $savedResultJson = [IO.File]::ReadAllText((Join-Path (Get-Location).Path $resultPath)).Replace("`r`n", "`n")
    if ($savedResultJson -cne $resultJson) {
        throw 'The saved result does not match this run output. Do not build.'
    }
    $resultSha256 = (Get-FileHash $resultPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "Worker result saved: $resultPath"
}
```

The run can take several minutes. Leave PowerShell running and watch the live **role**, **MCP tool name**, **phase** and elapsed-time updates. These show which specialist or validation step is active; the final JSON result is captured separately.

**While the workers run, [open Foundry](https://ai.azure.com/) and select your existing lab project, then Agents > caldova-orchestrator.** Inspect its configured model, instructions and tool definitions, including `dispatch_worker`. Connect what you see there with the activity reported in PowerShell: Foundry requests work, while the VM controller coordinates execution in the assigned Sandboxes. Inspect the existing configuration without changing it. Opening a separate playground conversation does not attach you to the running lab command.

This run performs actual implementation—not just the previous tool-execution check. The clinical-trials and drug-safety specialists use MCP tools to implement their assigned query functions in separate worker clones. Once their implementations pass the controller’s checks, it copies only the two accepted feature files into the primary and governance workspaces.

The primary then independently tests the combined application against the preserved tests and frozen data. Governance runs only after integration passes, reviewing the combined candidate and its evidence. This demonstrates why individually passing workers must still be followed by controlled integration, independent testing and review. It does not build an image or authorize deployment.

On failure, `failure.json` retains the role, Sandbox, error class, available request/status IDs, elapsed time and partial evidence. It is not an accepted worker result. Keep it and ask your instructor to inspect the existing run before retrying; do not edit the tests or broaden access.

<!-- pagebreak -->

# 13. Review the results

This is an **evidence-review checkpoint**, not another test run. The block reads the results collected by the previous worker command.

Confirm **no worker blockers** and **11 passing check categories**, each with `passed = True` and `exit_code = 0`. The block stops if these conditions are not met.

Match worker Sandbox IDs to `$bindings` and primary integration checks to `$validationSandboxId`. This shows that the combined application was tested independently of the workers’ development environments.

Finally, inspect the returned `trial_feature.py` against its assignment. A green table is **not release approval**; the build helper will revalidate the saved result and source identities.

## 13.1 Check the worker reports and tests

Review the collected evidence before authorizing an image build:

```powershell
. {
    $ErrorActionPreference = 'Stop'
    $result.workers | Format-List role, blockers | Out-Host
    [void] (Read-Host 'Inspect the worker blockers, then press Enter to review the independent checks')
    $checks = @($result.integration_evidence) + @($result.egress_evidence) + @($result.worker_evidence)
    $checks | Format-Table name, passed, exit_code, sandbox_id | Out-Host
    $blockers = @($result.workers | ForEach-Object { $_.blockers } | Where-Object { $null -ne $_ })
    if ($blockers.Count -ne 0 -or $checks.Count -ne 11 -or
        @($checks | Where-Object { -not $_.passed -or $_.exit_code -ne 0 }).Count) {
        throw 'The run has blockers or failed checks. Stop before building.'
    }
    [void] (Read-Host 'Match primary and worker Sandbox IDs, then press Enter to inspect the returned trial source')
    $result.candidate_sources.'src/research-portal/backend/trial_feature.py'.content
}
```

**Expected:** no blockers and **11 passing check categories**. Some categories share the same test execution; this is not 11 separate test suites.

| Evidence | What it demonstrates |
|---|---|
| Feature contracts in worker clones | Each implementation meets its assigned query contract |
| Acceptance tests in the primary | The combined application passes the eight public-data tests |
| Worker-report validation | Reports identify the correct run, role, Sandbox, and data |
| Network probes in the primary | An allowed destination returns HTTP 200; a denied destination returns HTTP 403 |


## 13.2 Inspect an implemented feature

The final part of the block displays the trial query returned by the team.

Find the candidate and condition filters and how values are passed to SQL. Compare the implementation with the clinical specialist's assignment. The next step builds the returned `content`, checked against its `sha256`.

**Checkpoint:** match one check's `sandbox_id` to `$validationSandboxId` (the primary) and another to a worker in `$bindings`. Explain why the two locations matter.

> **If you could not complete this segment:** keep the failed run's output. Skip **Build the application image** and **Deploy your image**, and open the catch-up note at the end of **Try the completed application**. Follow its commands to load the completed app, then continue with the application and recorded-example exercises.
