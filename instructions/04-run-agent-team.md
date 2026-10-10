# Segment 4 - Run the agent team (target: 23 minutes)

**Goal:** accept only identity-bound, independently validated specialist changes. **Why:** parallel model sessions do not replace isolation, source fidelity or deterministic tests. **Services:** Foundry, Agent Framework, ACA Sandboxes and the stdio MCP bridge. **Outcome:** two accepted feature modules, three valid worker reports and complete independent evidence; still no image/deployment approval.

## Recorded-evidence path

```powershell
$evidence.workers | Format-Table role, sandbox_id
$evidence.worker_blockers
$evidence.checks | Format-Table name, passed, exit_code, sandbox_id
$evidence.candidate_sources | Format-List
```

The accepted sample has zero blockers and **11 named checks**. Five integrated application checks and the worker-schema check run in the independent primary. Three feature-contract checks bind to their assigned role clones. The allowed and denied egress evidence also comes from the primary. Several integrated categories share one acceptance-output hash; 11 categories do not mean 11 separate test runners.

Follow the controller sequence:

1. Verify bindings, baseline lineage, protected frozen inputs and configured policy.
2. Run clinical and safety implementors in distinct Sandboxes, each with one writable feature path.
3. Call the argument-free, controller-owned `verify_feature` tool. Validate full original records, shared associations, comma-containing terms, explicit empty cases and lexical/record ordering.
4. Transfer only the accepted two module bytes into the independent primary and governance clone.
5. Run the exact dataset-specific acceptance suite in the primary: **eight public source-derived checks**, or the original **nine unchanged synthetic checks** for that separate branch.
6. Run governance against the integrated candidate, then validate all three report identities and grounded source-record IDs.

The real egress checks required HTTP 200 from the allowed destination and HTTP 403 from the denied destination with TLS verification enabled. A DNS failure, TLS error or timeout is not proof of denied egress. The portal uses frozen data; live egress probes do not silently refresh or replace that data.

## Live-exercise path

Use the supported runtime/`$controllerArgs` from Segment 2 and the new verified bindings/primary/manifest from Segment 3. Review the exact tasks again before `--approve-plan`, which authorizes worker execution only. This operation writes the two assigned features in the authorized Sandboxes; it does not create clones, publish an image or update the app.

```powershell
$resultText = & $controllerPython @controllerArgs --mode workers `
    --manifest $preparedManifestPath --bindings $bindingsPath `
    --validation-sandbox-id $validationSandboxId --approve-plan
if ($LASTEXITCODE -ne 0) { throw 'Worker run failed. Preserve stderr and stop before packaging.' }
$resultJson = $resultText -join "`n"
$result = $resultJson | ConvertFrom-Json
$blockers = @($result.workers | ForEach-Object { $_.blockers } |
    Where-Object { $null -ne $_ })
if ($blockers.Count -ne 0) { throw 'Workers still report blockers.' }
$checks = @($result.integration_evidence) + @($result.egress_evidence) + @($result.worker_evidence)
if ($checks.Count -ne 11 -or @($checks | Where-Object { -not $_.passed -or $_.exit_code -ne 0 }).Count) {
    throw 'Deterministic evidence is missing or failed.'
}
$runId = $result.plan.run_id
$runDirectory = Join-Path '.validation-workspaces' ('participant-' + [guid]::NewGuid().ToString('N'))
[void] [IO.Directory]::CreateDirectory($runDirectory)
$resultPath = Join-Path $runDirectory 'accepted-result.json'
[IO.File]::WriteAllText($resultPath, $resultJson, [Text.UTF8Encoding]::new($false))
$resultSha256 = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash.ToLowerInvariant()
$checks | Format-Table name, passed, exit_code, sandbox_id
```

This quick display is not the release gate. The packaging/receipt inspectors revalidate exact identities, schema, check locations, source hashes and snapshot bindings; a plausible all-green table is insufficient by itself.

Repairs remain bounded in the same assigned session. Feature repair and identity-report repair share a three-attempt budget within a 600-second worker session. Report-only repair disables tools and may not rewrite valid code, data, tests, blockers or identities silently. Persistent mismatches fail before integration. Do not reset snapshots, recreate clones or rerun with broader ownership to hide a defect.

## Checkpoint

Explain which checks prove independent acceptance, which bind to workers and why the current data's homogeneous records still need isolated fictional shared-record conformance tests. Those extra software guards do not replace the actual public suite or alter the public dataset.

| Symptom | Safe response |
|---|---|
| Wrong run/role/Sandbox/dataset identity | Retain exact expected/received diagnostics; bounded report repair must correct the report without accepting another identity |
| Source arrays are narrowed or nondeterministic | Repair only the assigned feature in the same session; preserve tests and frozen source |
| Governance reports an unknown source ID | Ground it in the actual frozen tables, or honestly report none; do not use a run ID or candidate label as a citation |
| Throttling or dispatch timeout | Preserve partial diagnostics; facilitator checks effective capacity and authorized retry scope |
| Denied probe timed out | Treat denial as unproven, not passed; do not disable TLS |
