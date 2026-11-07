# LAB722: Sandbox runtime analysis

## Before you begin

This separate runtime guide follows the simplified November 6 design. It does not replace the published developer lab or change `lab-ready-1`.

For the new `ig2026-lab-learner` allocation outside Skillable, first complete `lab-rejig-own-sub-instructions.md`. The maintainer table below is not that new allocation.

The facilitator supplies a running application URL, an access key, the prepared PowerShell terminal and the allocated Azure scope. There is no learner application sign-in, partner exercise or tenant selector. The key protects the endpoint; it does not identify a learner.

Foundry generates bounded Python and invokes `execute_python(run_id, code)` through a Toolbox. The trusted backend fixes the execution Sandbox. The UI shows the code, real stdout/stderr and execution receipt; it does not claim to validate arbitrary answers. Each request gets a new Foundry conversation, while writable files persist within the allocation.

Use only your allocated scope. Do not change role assignments, reveal connection secrets or delete resources. The table below is the current **maintainer test allocation**, not a set of values to reuse in Skillable.

| Setting | Rehearsal value |
|---|---|
| Subscription | Private Test Sub ACAPMS |
| Subscription ID | `30501c6c-81f6-41ac-a388-d29cf43a020d` |
| Resource group | `ig2026-lab-testing` |
| Express app | `lab722-runtime-analysis` |
| Application URL | `https://lab722-runtime-analysis.purpleground-bb4e10a0.westus3.azurecontainerapps.io` |
| Foundry account / project | `lab722-4fpje6f4ykpcg-ai` / `caldova` |
| Sandbox group | `lab722-4fpje6f4ykpcg-sandboxes` |
| Clean seed | `8a99e834-979a-420f-886e-3391198559e9` |
| Clean snapshot | `b871945e-2f69-4822-ae3f-a6fd310cb3ea` |
| Application/exercise Sandbox A | `6c7ef700-0834-4037-bf57-92c532c82e26` |
| Exercise Sandbox B | `8e6eae80-9b92-4c51-b10a-0f6ed42b7efe` |

The facilitator supplies equivalent values for another allocation. A/B demonstrate separate execution workspaces, not different users or customer tenants.

### Facilitator readiness

Before starting the learner timer, prepare the clean snapshot and app-bound A, deploy the tested runtime image and service connections, and verify one actual Foundry request. Supply the endpoint key privately. The learner terminal must already have PowerShell 7.3+, the pinned native ACA CLI and normal Azure authentication with permission for the allocated Sandbox operations. Supply portal/project visibility as part of the allocation; learners do not create identities or assign roles.

Provide B or leave one available slot for its creation. Do not allow simultaneous app runs and manual non-root probes in A. Leave deny-all egress, Full inspection, 900-second Memory suspension and auto-delete disabled after rehearsal. The retained test group is full, so its supplied A/B must be reused.

The maintainer deployment sequence is in `ignite26-LAB722\infra\README.md`, under **Single-allocation generated analysis**. A fresh Skillable allocation, its key-delivery channel and the learner-VM/profile capture still require platform-specific verification.

## Activity budget

These are authoring targets, not a measured Skillable completion time. Provisioning, image publication, the clean seed and service grants happen before the learner timer.

| Activity | Minutes |
|---|---:|
| Connect and identify the access boundary | 7.5 |
| Inspect Express and service connections | 7.5 |
| Inspect/create the snapshot-derived workspaces | 10 |
| Ask Foundry and inspect its generated code/result | 15 |
| Test filesystem, networking and an execution failure | 15 |
| Operate and inspect Sandbox lifecycle | 12.5 |
| Compare results and record enforced boundaries | 7.5 |
| Total | 75 |

## 1. Open and connect to the application

1. Open the facilitator-provided Caldova application URL. For the maintainer rehearsal, use the URL in the table above. Do not use the old `/proof` endpoint.
2. Enter the supplied key in **Facilitator-provided access key**, then select **Connect**.
3. Read the configuration: the fixed Sandbox ID, `execute_python`, dataset version and limits.
4. Refresh the page. The application key is no longer present in that tab; connect again. Do not put the key in a URL, browser local storage, a screenshot or a shared transcript.
5. Distinguish the key holder, your Azure portal user, the application's managed identity and the non-root Sandbox process. None is an app-local tenant identity.

The page itself is public. API operations and MCP calls require the key. Public page or health access does not establish permission to execute code.

## 2. Inspect the Azure service path

1. In Azure portal, confirm your allocated subscription/resource group and open the runtime Container App.
2. On **Overview**, inspect its URL, status, region and **Express** environment.
3. Inspect its managed identity and configuration without reading secrets. Port is **8080**, minimum replicas **0**, maximum **1**. Do not save a new revision.
4. In the supplied Foundry project, inspect the saved `lab722-runtime-analysis` agent and the two runtime connection targets. If the portal cannot display a property, use the prepared terminal's read-only resource inspection rather than repairing the form.
5. Compare these service hops:

   | Connection | Authentication | Target |
   |---|---|---|
   | `runtime-analysis-toolbox` | `ProjectManagedIdentity` | The project's `runtime-analysis-toolbox` MCP endpoint. |
   | `runtime-analysis-backend` | `CustomKeys` | The Express application's `/mcp` endpoint. |

The app identity calls Foundry and operates the Sandbox. The project identity authenticates to the Toolbox. The stored backend key authenticates the MCP call. Generated Python receives none of those credentials. In analysis mode, the Sandbox group has **no assigned Azure identity**.

## 3. Observe the application boundary

1. In the prepared PowerShell terminal, set your supplied URL:

   ```powershell
   $url = Read-Host 'Allocated application URL'
   Invoke-RestMethod -Uri "$url/health"
   ```

2. Request configuration without a key:

   ```powershell
   $response = Invoke-WebRequest -Uri "$url/api/config" -SkipHttpErrorCheck
   $response.StatusCode
   ```

   Expect **401**. This tests the endpoint-key boundary, not a different learner's result ownership.

3. Read the limits shown after **Connect**: **16 KiB** Python, **30 seconds** wall time, **15 seconds** CPU time, **256 MiB** analysis memory and **128 KiB** combined stdout/stderr. Only one app execution is active at a time; another request receives **409 sandbox_busy**, not a queued run.

## 4. Ask Foundry and inspect the actual result

1. In **Analysis request**, use:

   ```text
   Group the frozen trial records by phase. Return chart data and the source trial IDs used.
   ```

2. Select **Ask Foundry**. Follow the reported path:

   ```text
   Express API -> Foundry agent -> Toolbox -> authenticated MCP backend -> Sandbox
   ```

3. Inspect the Python in the editor. Which file does it read? How does it group records? Which identifiers does it return? This code was generated for the request, not supplied as a fixed inspection script.
4. Read the execution evidence: request ID, tool, agent version, Sandbox ID, execution marker, UID, exit code and elapsed time. Expect UID **65534**, a cleared environment and no-new-privileges.
5. Compare **actual stdout/result** with the **agent summary**. The summary is not independent validation. Optional charts are rendered only from numeric label/value rows in the actual JSON.
6. Compare phase counts and source IDs yourself. The frozen reference counts sum to **168**:

   | Phase | Count |
   |---|---:|
   | NA | 2 |
   | PHASE1 | 45 |
   | PHASE2 | 23 |
   | PHASE2/PHASE3 | 1 |
   | PHASE3 | 76 |
   | PHASE4 | 21 |

The frozen manifest SHA-256 is `99810e57a77cd3bc8b107287037e54fb2521795a96ec71d431fd585c03289f91`. The supervisor verifies all three frozen files before and after execution. No phase-count-specific validator repairs or accepts the generated answer.

## 5. Edit code and follow a real failure

1. Replace the editor code with:

   ```python
   raise SystemExit(19)
   ```

2. Select **Run edited code**. Expect status **failed** and actual exit **19**. The path says **Express -> Sandbox**: Foundry was not called.
3. Try a wall-clock timeout:

   ```python
   import time
   time.sleep(60)
   ```

   Expect **timed_out** after approximately 30 seconds of remote execution, plus service/CLI overhead. The remote supervisor enforces this even if the caller disconnects.
4. Try the output boundary:

   ```python
   print("x" * 200000)
   ```

   Expect **output_limit** and no more than 128 KiB captured output.
5. Return to the analysis request and ask another bounded question, such as counting trials in PHASE3. Inspect the new code and compare the actual source/result evidence. A fresh conversation does not reset existing `/workspace` files.

Plain stdout is also supported. A program such as `print("hello")` can complete without producing JSON or a chart. Formatting is not an answer-correctness gate.

## 6. Inspect the clean execution workspaces

Use the prepared local PowerShell terminal for these native ACA exercises. The earlier Microsoft-directory Cloud Shell device login was denied with error **53003**; do not repeat that flow or change directory policy. That finding does not determine the lab platform's own Azure login policy.

1. Open the prepared **PowerShell 7.3 or later** terminal, using its normal Windows native-argument handling. The Azure login and Sandbox permission must already be available; these commands do not register applications or grant roles.
2. Set the explicit scope and the supplied workspace IDs:

   ```powershell
   $aca = Join-Path $HOME '.aca\bin\aca.exe'
   $subscriptionId = Read-Host 'Allocated subscription ID'
   $resourceGroup = Read-Host 'Allocated resource group'
   $region = Read-Host 'Allocated region'
   $sandboxGroup = Read-Host 'Allocated Sandbox group'
   $scope = @('--subscription', $subscriptionId, '--resource-group', $resourceGroup,
       '--region', $region, '--group', $sandboxGroup)
   $seed = Read-Host 'Allocated clean seed ID'
   $snapshot = Read-Host 'Allocated clean snapshot ID'
   $a = Read-Host 'Prepared application Sandbox A ID'
   $b = Read-Host 'Sandbox B ID, or leave blank if not yet created'
   & $aca --version
   & $aca sandbox list @scope -o json
   & $aca sandbox get @scope --id $a -o json
   if ($b) { & $aca sandbox get @scope --id $b -o json }
   ```

3. Confirm A's `sourcesRef.snapshot.id` matches the supplied clean snapshot; check B too when it exists. Observe the separate instance IDs, CPU **2000m**, memory **4096Mi**, deny-all egress and **Full** inspection.
4. Observe the prepared policy: idle suspension **900 seconds**, mode **Memory**, auto-delete **disabled**.
5. A/B already exist in this rehearsal. Do not create duplicates: this group is at four-instance capacity. In a fresh allocation, **A must already be prepared and bound to the app**. If B is not supplied and the facilitator confirms one free slot, create B from the clean snapshot:

   ```powershell
   # Fresh allocation only: capture the returned ID as $b.
   & $aca sandbox create @scope --snapshot-id $snapshot `
       --label lab=LAB722 --label purpose=runtime-rehearsal-b `
       --egress-default Deny --traffic-inspection Full -o json
   if ($LASTEXITCODE -ne 0) { throw 'B creation failed; inspect the operation before retrying.' }
   $b = Read-Host 'Copy Sandbox B id from the returned resource'
   & $aca sandbox get @scope --id $b -o json
   ```

   Snapshot restores inherit CPU/memory resources; do not supply resource overrides. Confirm B's snapshot reference and configure it with the 900-second lifecycle command in section 9. Keep A's app binding unchanged. Creation from the supplied snapshot was verified during preparation; do not snapshot active A to create B.

## 7. Observe filesystem and process isolation

1. Use the prepared non-root interpreter with a cleared environment:

   ```powershell
   $prefix = 'runuser -u nobody -- env -i PATH=/opt/python/3/bin:/usr/bin:/bin HOME=/workspace /opt/python/3/bin/python3 -I'
   $code = @'
   import json,os,pathlib
   print(json.dumps({
       "uid":os.getuid(),
       "credential_environment_names":[k for k in os.environ if k.startswith(("AZURE_","IDENTITY_","MSI_","PROOF_"))],
       "files":sorted(p.name for p in pathlib.Path("/opt/lab722-data").iterdir())
   }))
   '@
   & $aca sandbox exec @scope --id $a -c "$prefix -c '$code'" -o json
   if ($LASTEXITCODE -ne 0) { throw 'Process inspection failed.' }
   ```

   Expect UID **65534**, no credential environment names in this child process, and the manifest, source-record JSON and DuckDB file. These manual commands are trusted operator probes. App-submitted/generated code additionally runs through the privileged supervisor's no-new-privileges, resource limits and process cleanup. The group must have no assigned Azure identity.

2. Write a marker in A's writable workspace:

   ```powershell
   $code = @'
   import json,pathlib
   p=pathlib.Path("/workspace/lab722-isolation.txt")
   p.write_text("LAB722 workspace A")
   print(json.dumps({"marker":p.read_text()}))
   '@
   & $aca sandbox exec @scope --id $a -c "$prefix -c '$code'" -o json
   if ($LASTEXITCODE -ne 0) { throw 'Marker write failed.' }
   ```

3. Look for the same path in B:

   ```powershell
   $code = @'
   import json,pathlib
   present=pathlib.Path("/workspace/lab722-isolation.txt").exists()
   assert not present
   print(json.dumps({"other_workspace_marker_present":present}))
   '@
   & $aca sandbox exec @scope --id $b -c "$prefix -c '$code'" -o json
   if ($LASTEXITCODE -ne 0) { throw 'Workspace isolation check failed.' }
   ```

   Expect **false**. The instances share the starting public data, not subsequent writable files. This tests separate filesystems, not API-level result ownership.

4. Attempt to open the frozen manifest for writing:

   ```powershell
   $code = @'
   import hashlib,json,pathlib
   p=pathlib.Path("/opt/lab722-data/data-manifest.json")
   before=hashlib.sha256(p.read_bytes()).hexdigest()
   denied=False
   try:
       with p.open("ab"):
           pass
   except PermissionError:
       denied=True
   after=hashlib.sha256(p.read_bytes()).hexdigest()
   assert denied and before==after
   print(json.dumps({"write_denied":denied,"manifest_unchanged":before==after}))
   '@
   & $aca sandbox exec @scope --id $a -c "$prefix -c '$code'" -o json
   if ($LASTEXITCODE -ne 0) { throw 'Read-only data check failed.' }
   ```

   Expect both fields **true**. The data directory is **0555** and its three files are **0444**, owned by root. UID 65534 cannot alter them; an Azure operator executing as root is a different trust boundary.

## 8. Test allowed and denied network access

1. Read the original policy. It must be deny-all with Full inspection before this exercise:

   ```powershell
   & $aca sandbox egress show @scope --id $a -o json
   ```

2. Prepare a short HTTPS HEAD probe:

   ```powershell
   $probe = @'
   import json,urllib.request,urllib.error
   results={}
   for host in ("example.com","example.net"):
       try:
           with urllib.request.urlopen(urllib.request.Request("https://"+host+"/",method="HEAD"),timeout=10) as r:
               results[host]=r.status
       except urllib.error.HTTPError as e:
           results[host]=e.code
   print(json.dumps(results))
   '@
   ```

3. Temporarily permit exactly `example.com`, run the probe, and restore deny-all even if execution fails:

   ```powershell
   try {
       & $aca sandbox egress set @scope --id $a --default Deny `
           --traffic-inspection Full --rule 'example.com:Allow' -o json
       if ($LASTEXITCODE -ne 0) { throw 'Temporary policy update failed.' }
       & $aca sandbox exec @scope --id $a -c "$prefix -c '$probe'" -o json
       if ($LASTEXITCODE -ne 0) { throw 'HTTPS probe failed.' }
   } finally {
       & $aca sandbox egress set @scope --id $a --default Deny `
           --traffic-inspection Full -o json
       if ($LASTEXITCODE -ne 0) { throw 'Policy restoration failed; notify the facilitator.' }
   }
   ```

   The verified result was **200** for `example.com` and **403** for `example.net`. A timeout or DNS error is not equivalent evidence of a policy denial.

4. Read back the policy and repeat the probe:

   ```powershell
   & $aca sandbox egress show @scope --id $a -o json
   & $aca sandbox exec @scope --id $a -c "$prefix -c '$probe'" -o json
   if ($LASTEXITCODE -ne 0) { throw 'Post-restoration probe failed.' }
   & $aca sandbox egress decisions @scope --id $a -o json
   ```

   Expect no allow rule and **403** for both hosts. The decision feed may arrive later than the requests. Do not leave the temporary allow rule in place.

## 9. Observe a failure and operate the lifecycle

1. Execute a deliberate failure and read the CLI exit status immediately:

   ```powershell
   & $aca sandbox exec @scope --id $a -c "$prefix -c 'raise SystemExit(19)'" -o json
   $exit = $LASTEXITCODE
   if ($exit -ne 19) { throw "Expected exit 19, received $exit." }
   "Remote and CLI exit: $exit"
   ```

   No output is not success. The remote command and native CLI both returned **19** in the rehearsal.

2. Change the idle interval to **600 seconds**, inspect it, then restore **900 seconds**:

   ```powershell
   try {
       & $aca sandbox lifecycle set @scope --id $a --auto-suspend enable `
           --idle-timeout-seconds 600 --mode Memory --auto-delete disable -o json
       if ($LASTEXITCODE -ne 0) { throw 'Idle policy update failed.' }
       & $aca sandbox get @scope --id $a -o json
   } finally {
       & $aca sandbox lifecycle set @scope --id $a --auto-suspend enable `
           --idle-timeout-seconds 900 --mode Memory --auto-delete disable -o json
       if ($LASTEXITCODE -ne 0) { throw 'Idle policy restoration failed.' }
   }
   ```

   Read the actual policy; setting a timer does not prove that idle suspension has occurred. For fresh instances, apply the restored 900-second command to B as well.

3. Stop A and inspect its state **before another exec**:

   ```powershell
   & $aca sandbox stop @scope --id $a --wait-timeout 120 -o json
   if ($LASTEXITCODE -ne 0) { throw 'Stop failed.' }
   & $aca sandbox get @scope --id $a -o json
   ```

   Expect **Stopped**. Native `exec` can automatically resume a stopped instance, so do not use it to observe the stopped state.

4. Resume A explicitly:

   ```powershell
   & $aca sandbox resume @scope --id $a --wait-timeout 120 -o json
   if ($LASTEXITCODE -ne 0) { throw 'Resume failed.' }
   & $aca sandbox get @scope --id $a -o json
   ```

   Expect **Running**, the same instance ID, 900-second idle suspension and disabled auto-delete.

5. Read the retained marker and manifest:

   ```powershell
   $code = @'
   import hashlib,json,pathlib
   marker=pathlib.Path("/workspace/lab722-isolation.txt").read_text()
   p=pathlib.Path("/opt/lab722-data/data-manifest.json")
   print(json.dumps({"marker":marker,"manifest_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}))
   '@
   & $aca sandbox exec @scope --id $a -c "$prefix -c '$code'" -o json
   if ($LASTEXITCODE -ne 0) { throw 'Retention check failed.' }
   ```

   Expect the marker you wrote and the same manifest identity observed in section 4. The actual rehearsal also checked all three frozen file hashes after resume.

6. In the application, run edited code that reads `/workspace/lab722-isolation.txt`. Confirm the same marker and a completed execution receipt after resume. The app supervisor also rechecks all three frozen files.

## 10. Record the boundaries

Record the Express user/service identity distinction, the Foundry tool and request ID, A/B instance IDs, the marker access results, the denied write, the HTTPS decisions, exit 19 and the observed lifecycle states.

Leave the seed, snapshot, proof app and both workspaces in place. Keep deny-all egress, a 900-second idle interval and auto-delete disabled. No cleanup command is part of this rehearsal.

The analysis app executes in A, fixed by deployment configuration. B demonstrates filesystem isolation. No sign-in, partner result access or tenant ownership is part of this version; see `lab-rejig-identity-flow.md` for the access-key and service-identity flow.

## Verification status

The simplified runtime was deployed and rehearsed on **November 6, 2026** in the maintainer test allocation. This is not a fresh Skillable or measured 75-minute learner run.

| Activity | Result |
|---|---|
| Final runtime image | ACR run `ds9` succeeded with ten focused checks; digest `sha256:d4243b283746a7bf7af1549c223ef0d7dbdc2a54708f5cc25fcc7d87d0ad1101`. |
| Final app deployment | `runtime-analysis-20261106-211819` succeeded; group identity disabled, existing four service grants and access key reused. |
| Portal resource inspection | Express/core resources were inspected in the earlier portal rehearsal; final analysis deployment was inspected through the scoped helper, not a repaired portal form. |
| Public health and missing-key boundary | HTTP 200 health and HTTP 401 configuration denial verified. |
| Generated request in the real browser | Run `767b9431-fe16-4769-8001-fd4c5b494297` completed through Foundry/Toolbox/MCP/Sandbox; six chart groups totaled 168 with source IDs. |
| Browser edited-code and follow-up actions | Exit 19 displayed as failed with no agent call; a new PHASE3 request completed in a different conversation and returned 76. |
| Browser key handling | Password input cleared; localStorage and sessionStorage remained empty. |
| Actual execution identity | UID 65534, cleared environment and no-new-privileges verified; injected identity endpoint denied token access with HTTP 401. |
| Toolbox bootstrap | Repeated setup reused analysis version 1; all six isolated proof-mode bootstrap checks passed. |
| Snapshot-derived workspaces | Prepared from the clean public-data snapshot; A's marker remained absent in B. No duplicate allocation. |
| Failure, timeout and concurrent request | Actual exit 19 surfaced as failed; remote timeout enforced at about 30 seconds; concurrent request returned HTTP 409. |
| Output and subprocess boundaries | Captured output bounded to 128 KiB; non-JSON/non-finite stdout preserved as text; detached child killed and reaped. |
| Frozen data and networking | App-executed write denied; HTTPS 200/403 under the temporary allow rule, then 403/403 after deny-all restoration. |
| Lifecycle and app retention | 600-second policy observed, then restored to 900/Memory with auto-delete disabled; Stopped/Running observed and app execution after resume retained the marker and verified frozen bytes. |
| Learner sign-in / partner result ownership | Removed from this design, not pending identity work. |
| Skillable allocation and timing | Not yet verified; 75 minutes remains an authoring budget. |

Sanitized maintainer receipts are retained in the session artifacts `runtime-analysis-live-results-20261106.json`, `runtime-analysis-final-browser-results-20261106.json`, `runtime-analysis-boundaries-results-20261106.json` and `runtime-analysis-lifecycle-results-20261106.json`. The browser run above records final-image execution; earlier fixed-proof evidence is historical, not acceptance of this new app.
