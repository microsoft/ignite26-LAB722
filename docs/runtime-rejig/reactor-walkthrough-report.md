# LAB722 reactor walkthrough report

## Scope and result

**Historical first-allocation report.** The subsequent fresh-allocation recovery and completed technical exercises are recorded in [the latest friction report](../../lab-pamela-friction.md). The personal workstation entry is [the local azd walkthrough](lab-rejig-local-walkthrough.md). Resource/version IDs below belong to the first allocation, not a fresh deployment.

**November 7, 2026; branch `lab-reactor`; authorized allocation `ig2026-lab-learner`, westus3.** The owner authorized permanent provisioning after the Entra probes. The earlier no-audience/no-creation blocker is resolved.

The real path now works: frontend Express -> native Foundry hosted workflow -> managed Toolbox OpenAPI -> execution Express -> new task Sandbox -> independent result check -> exact deletion. Both demo owners completed useful work. The final rehearsal used service image v8, hosted image v7/native version 6 and Toolbox version 3. These are locally committed reactor changes, not a push, merge or tag movement. The learner entry is [the maintained guide](lab-rejig-learner-instructions.md); the root implementation/walkthrough contracts are unchanged.

## L1-L5 verdicts

| Outcome | Verdict | Observed evidence and limit |
|---|---|---|
| L1: service authentication and application ownership | **Passed** | Alice `6915f705-efb7-45c2-960d-c712f1fbdcc6` and Bob `92becf61-f752-4a22-9cd3-f0c93fde29c1` completed accepted phases work with distinct native sessions. Both directions of foreign run/artifact/conversation/cancel returned 403; owned conversation controls returned 200. Bob's identity-swapping prompt remained Bob-owned. Actual gateway execution with a forged owner/grant returned 403; anonymous POST returned 401. Genuine execute-grant swap/replay combinations are additionally covered offline, not represented as live token extraction. |
| L2: constrained code and actions | **Passed** | Sandbox-origin `urllib.request.urlopen` failed visibly with HTTP 403 under the actual `Deny`/`Full` resource policy. Limit run `26fba2c3-cf15-493b-8598-283365d81916` returned `timed_out`, exit -9, **30.084 seconds**, and deletion. Useful phases/safety work succeeded. A policy-specific traffic verdict is unavailable: full causal attribution of the network 403 is not claimed. |
| L3: interruption, retries and recovery | **Passed** | Controlled failure `9f633a14-d9df-46ce-8476-68d5620d848f` exited 19 and retained owned evidence after deletion. Completed/failed creation-key retries returned the same run and one evidence artifact. Alice's running limit `90c02b6d-dd63-4702-87a1-28f99197cab2` was cancelled and cleaned; its same-key retry returned the cancelled record. Bob's concurrent workflow still completed, and Alice recovered useful work with a new key. No durable restart restoration is claimed. |
| L4: independent acceptance and provenance | **Passed** | Final phases and two-worker results matched the frozen counts/source IDs; every receipt's run, UTF-8 code digest, native session and deletion were compared. Earlier live v7 execution `149eea4f-a637-4a89-ab2b-763c11fef736` exited zero but counted zero records: the unchanged independent checker rejected it. The final offline fixture also rejects PHASE3=77 and missing safety source IDs while accepting correct controls. That earlier wrong-result evidence is not mislabeled as a v8 malicious-worker run. |
| L5: budget, usage and change control | **Passed** | A second fresh Alice run returned 429 while her slot was reserved; Bob was admitted. Aggregate inventory observed **two Running task Sandboxes**, then zero. Bob's two-worker run `52d4b66a-8719-44f0-91cb-0907755ffa64` had two accepted receipts and **9.378 total Sandbox seconds**. Digests/versions and a concrete known-good-image revert procedure are recorded. Outer hosted usage returned null; model token totals/costs are unavailable. Revert is documented, not live-exercised. |

These verdicts cover the stated minimum technical exercises, not production readiness or every possible attack. Local fixtures and live checks are identified separately. Missing traffic diagnostics, model usage and durable state are not passing measurements.

## Actual resources and identities

| Component | Final state / identity |
|---|---|
| Frontend | `lab722-reactor-frontend`, service v8; UAMI object ID `486909ad-db2b-45e8-8ea0-86d7ac4c8a4a`; HTTPS UI, signed demo sessions and canonical public origin |
| Execution | `lab722-reactor-execution`, service v8; UAMI object ID `013f06e3-db04-4e4b-a1a7-7aed860f13af`; group-scoped Sandbox management |
| Native hosted agent | `reactor-orchestrator` **version 6 active**, endpoint enabled; platform-created ServiceIdentity `df4bfc73-c702-4506-9107-f2fe63e6b462`, separate managed blueprint |
| Toolbox / connection | `runtime-reactor` **version 3 default**; `reactor-execution` OpenAPI / ProjectManagedIdentity connection; repeated setup reused v3 |
| Actual execution bearer caller | Project MI `1db2558e-4f2e-4c02-ad7f-4cd79c5d7dcb`; tenant `72f988bf-86f1-41af-91ab-2d7cd011db47`; audience `api://b9b2ea56-35aa-4c34-b50f-4ccfffd1c6a6` |
| Dedicated API | Allocation-owned single-tenant application client ID `b9b2ea56-35aa-4c34-b50f-4ccfffd1c6a6`; token version 1; approved service-principal assignment requirement false; no client secret, demo Entra user or delegated Graph grant |
| Registry permissions | Project MI has scoped `AcrPull` on `acateam`; native runtime has project Foundry User. The unnecessary runtime AcrPull probe assignment was removed. Express pulls anonymously; no registry policy was changed. |
| Sandbox group | `lab722-hg4qnurp4clyw-sandboxes`, no usable group identity; approved snapshot `4f90fd07-005f-48f6-bb0a-a691a45af976` |

Alice/Bob are application accounts. Live native context returned the frontend UAMI's object ID as platform user for both, with different call/session IDs. No `x-ms-user-identity` impersonation was enabled; the current Foundry User role excludes that action. Displayed app owners are not delegated Entra credentials.

## Immutable delivery and checks

| Artifact / check | Final evidence |
|---|---|
| Service image v8 | `acateam.azurecr.io/lab722/reactor-services@sha256:48d6a42cd9d7bc87a551f2f05264fb8de6de0efef10bf3ec31e947ca96ff355a` |
| Hosted image v7 | `acateam.azurecr.io/lab722/reactor-hosted@sha256:2b3ef7ec815035dd5cbfe2c9905cbc5307efd46364bb2b149c91d6e2cb3cb289` |
| Windows runtime suite | `python -m unittest discover -s tests -p 'test_reactor_*.py'`: **44 tests, 43 passed + one Linux-root skip** |
| Linux service build | ACR `cj23`: **44 passed, no skips**, including the real private-note supervisor check |
| Native dispatcher test | Windows and ACR hosted build `cj22`: **1 passed**; real MAF dispatcher, external calls mocked, concurrent owned bindings and typed pending-to-complete results |
| Preserved supervisor baseline | Earlier Linux ACR `ds3`: 10 passed; not counted as a fresh v8 cloud transaction |
| Setup / infrastructure | Native helper was exercised for real registration and Toolbox reuse. Bicep, PowerShell parser and whitespace validation supplement cloud/HTTP checks; preview-type warnings are not cloud readiness. |

Frozen v2 has 168 trials, 38 safety reports and PHASE3=76. Source pin is `5c31dcd20478c1644b50eff7a7286b9c568094dd1e26427843afd23fc9dfe57c`; the maintained learner guide includes the manifest/DuckDB pins and every correlation comparison.

Private session artifacts retain the full owned receipts, checks and inventory: `reactor-live-first-task-20261107.json`, `reactor-live-acceptance-20261107.json`, `reactor-live-forged-execution-20261107.json`, `reactor-live-v7-owned-artifact-20261107.json`, `reactor-live-gateway-timeout-20261107.json`, `reactor-ending-sandbox-inventory-20261107.json`, `reactor-native-ending-sessions-20261107.json`, `reactor-cj23-20261107.log` and `reactor-cj22-20261107.log`. Passwords, tokens, grants and signed log URLs are not committed.

## Repairs discovered by real execution

| Boundary | Observed defect | Persistent correction |
|---|---|---|
| Async MI startup | Missing `aiohttp` prevented real transport startup | Pin dependency in both manifests; real credential-transport test |
| TLS ingress / login | Internal HTTP origin rejected external HTTPS login | Canonical `FRONTEND_PUBLIC_ORIGIN`; foreign-origin denial retained |
| Native tool mapping / privacy | MCP required `body`; error diagnostics echoed its grant | Actual operation `reactor___reactor_execute`; grant moved to verified redacted header |
| Native deployment | Reserved env/protocol mismatch and wrong image-pull principal | Preview opt-in, protocol 2.0.0, platform-injected reserved env, project-MI ACR pull and separate runtime role |
| Express configuration | Saved hosted URL did not update the running process; revision restart rejected | Verified app Stop/Start and HTTP configuration check |
| Native MAF dispatch | Handler `execute` replaced the framework dispatcher | Rename to `orchestrate`; execute the real dispatcher in Linux build tests |
| Native CLI create | Even `-o json` returned human `Created sandbox: ...` | Structured read-after-create by exact run/step selector; reject foreign labels before execution/deletion |
| Worker input / MCP output | Guessed frozen layout yielded zero; SDK returned typed text list | Exact worker schemas and one typed text Content result; independent checker kept rejecting wrong output |
| Long task transport | Gateway failed at 30s; execution finished and cleaned at ~34s | 20s HTTP handoff, declared 202, bounded runtime-only collection of the same task; no execution replay or new MCP endpoint |

The final long-limit run completed through that pending path, unlike the preserved failed pre-repair attempt. HTTP 200 is separately checked for Responses `status: completed`. The run grant never enters model input, generated code, browser output or the tool's JSON body; actual gateway error-header redaction was checked. Exhaustive platform telemetry retention auditing is not claimed.

## Walkthrough gate and ending state

**A:** original implementation review plus two targeted live-fix rereviews completed; final rereviews reported no significant issues. **B-C:** original instructional reviews and a fresh final learner-material check completed. That final check found one runtime-grant sequencing ambiguity: facilitator pre-creation of the logical agent and starter version was described but absent from the role-setup commands. The commands and actor responsibilities now explicitly prepare the runtime identity/grants before learners arrive; learners deploy a new version of that prepared agent. The reviewer confirmed the correction resolved the finding and found no other high-confidence learner-blocking defects. Maintained document relative links passed validation. **D:** one full API-assisted technical rehearsal completed in the intended Azure allocation after the documented repairs. It is not a claim that an uninformed learner followed the original unrepaired guide without help. **E:** original blind offline calibration detected 4/4 seeded defects with no misses/false alarms and accepted all correct controls.

At ending inventory, there were **zero reactor task Sandboxes**. The seed `938dfe19-6eed-4319-b380-1a710335bc4f` and fixed A `cec64c6c-c7d1-4ced-8518-16bfc23d154b` remained present and Stopped. Nine active sessions belonging to this reactor were stopped through the native API; zero remained active. Both Express apps and the enabled native endpoint remain available for the next prepared rehearsal. No old runtime, snapshot, unrelated worktree file or `lab-ready-1` tag was changed.

**Not exercised:** representative human comprehension/pacing, fresh Skillable tenant/platform delivery, production-scale load and live revert. The 75-minute duration remains an authoring target. The smallest remaining delivery action is a representative human walkthrough against the prepared learner allocation, with an explicit Skillable image/identity prerequisite check. No further tenant provisioning is needed for this verified allocation.
