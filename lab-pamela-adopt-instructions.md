# LAB722: adopt Pamela's agent workflow

## Assignment

Implement a concise, teachable lab on **`lab-reactor`** using Pamela Fox's example as reusable material. Use **two separate Express apps**: a front-end app for the UI/application API and an execution app for the offload API and dynamic ACA Sandbox lifecycle. Run the **orchestrator on Foundry hosted agents** and expose the execution API through **managed Toolbox using OpenAPI**. Use **service-based backend authentication**, with two demo users and application-enforced ownership. Address the five outcomes below within the approximately 24-hour delivery budget. Aim for a 75-minute learner experience; treat that duration as unmeasured until checked.

Read and apply [lab-learner-walkthrough.md](lab-learner-walkthrough.md). Its objectives are supplied by this document. Produce working changes and evidence, not another proposal.

## Start here; ask at most five questions

1. Inspect repository guidance, Git status, branches, current runtime code, learner guides, and available deployment evidence. Distinguish current implementation from historical designs.
2. Work only in the user's lab repository on `lab-reactor`. Continue that branch if it exists; otherwise create it from the verified current lab baseline. Preserve unrelated changes; use an isolated worktree if necessary. Never reset existing work, move `lab-ready-1`, or modify Pamela's upstream repository.
3. Make focused local commits. Keep the work on `lab-reactor`; do not merge, publish, or push unless already authorized.
4. Ask **up to five decision-changing questions total**, including subagents. Inspect context first, batch unresolved questions, and recommend defaults. Do not re-ask settled choices. Likely gaps are the baseline, authorized Azure scope, available workload identities/role assignments, and conflicting mandatory outcomes. Routine reversible choices are yours.
5. Use the already authorized lab environment and permissions. Historical resource IDs are not authorization. If access or an essential decision remains missing, finish independent work and report the exact blocker; never invent permission or a passing result.

## Scope and learning outcomes

Use one scenario: **two fictional customers share a research assistant, with separate private working data and results**. Reuse frozen public research data with harmless customer-specific notes or markers. Seed **Alice and Bob** as two application accounts with stable user IDs, different customer memberships, and separate test passwords. A fixed server-side account map is sufficient; use password hashes and maintained session/authentication helpers. Derive ownership from the validated login, not a browser selector or prompt. These are demo app identities; no Entra user provisioning or OAuth provider is required.

Begin with one bounded task so learners can follow the orchestrator and Sandbox lifecycle. Then add two complementary worker tasks and one review pass. Reuse Pamela's dynamic Sandbox pattern, visible progress, and useful workflow code; reuse the rejig's bounded execution and known-answer data where appropriate. Avoid generalized frameworks, dynamic customer onboarding, and elaborate dashboards.

| ID | Learning outcome | Minimum acceptance evidence |
| --- | --- | --- |
| L1 | Authenticate demo users and enforce application-level customer ownership over a service-authenticated backend. | Both users can perform authorized work. Application checks reject cross-customer run, result, conversation, and execution requests. Prompts and forged IDs cannot override ownership. Evidence distinguishes the app user from the validated service caller. |
| L2 | Constrain generated code and tool actions. | Useful execution succeeds; a prohibited action originating in the Sandbox and a resource-limit breach fail visibly. Hosted web search cannot establish Sandbox egress enforcement. |
| L3 | Handle partial failure, state, and retries. | Interrupt one step and demonstrate recovery or an explicit recovery path. Retrying creation of a harmless artifact/run record leaves exactly one intended result; abandoned resources are cleaned up. |
| L4 | Evaluate results independently and trace their origin. | A known-answer check rejects an incorrect result. Correlated evidence identifies inputs, tool execution, and output; model approval alone cannot pass acceptance. |
| L5 | Control capacity, usage, and changes. | Demonstrate a small concurrency/fan-out budget and cleanup. Record actual available usage, artifact/configuration versions, and a concrete revert procedure. Do not require production-scale load testing. |

Every outcome needs a learner action, visible evidence, a short explanation, and one prediction or transfer question. Report partial coverage explicitly; do not silently redefine an outcome.

## Architecture rules

**Call path:** browser → front-end Express app → Foundry hosted orchestrator → managed Toolbox → execution Express app → task Sandbox. Return results through the same boundaries. Toolbox provides the MCP-to-HTTP gateway; deploy the execution HTTP endpoint in the second Express app.

**Authentication decision settled:** use service identities between backend components and application authorization for the two demo users. End-user OAuth, Entra on-behalf-of delegation, and a custom identity provider are out of scope. Show user context as far through the flow as verified; do not present an app-supplied ID as a delegated user credential. Do not reopen this choice.

- **Front-end app (Express):** host demo login, the UI, hosted-orchestrator calls, and progress/results. Protect sessions, streams, cancellation, and management routes with maintained application middleware; verify Express capabilities instead of assuming Easy Auth. Keep operator actions unavailable to learners and Sandbox lifecycle code in the execution app.
- **Hosted orchestrator (Foundry hosted agents):** run planning, delegation, tool invocation, and result synthesis here. Adapt useful MAF workflow code to a supported hosted-agent protocol. Create request-aware workflow/tool clients without sharing mutable user context. Verify compatibility with pinned dependencies.
- **Managed Toolbox:** use the supported hosted-agent integration over MCP, forwarding the current request's platform call context. Register the execution app's HTTP operations through OpenAPI and a `ProjectManagedIdentity` connection. Use Toolbox's managed gateway; do not add a custom MCP server for offload.
- **Execution app (Express):** deploy separately, with its own endpoint and logs. Validate the caller's token, expected API audience, and permitted service identity/role; then authorize the requested run. Own Sandbox creation, execution, result collection, and cleanup. Reuse compatible lifecycle code; add submit/status handling only if measured task duration requires it.
- **Ownership:** keep a server-owned association between demo user, customer, run, Foundry session/conversation, Sandbox, and result. The service token authenticates the caller; app-user metadata alone grants no authority. Bind execution to an authorized run with a scoped, expiring backend-issued grant or equivalent trusted mechanism, injected by runtime code outside the model's control. Verify that integration hook before relying on it. The execution app checks the binding and selects permitted inputs; model-supplied user/customer/run IDs cannot override it. Protect retrieval and cancellation with the same ownership rules.
- **Dynamic Sandboxes:** verify and preserve Pamela's task-scoped creation/invocation pattern, now owned by the execution app. Apply filesystem, network, time, and output policies. Prefer keeping model/tool credentials outside generated code. Toolbox does not replace image-pull identity; explain any model authentication retained inside workers. Reconcile existing identity assumptions before reusing checks.
- **State and evidence:** preserve ownership across restarts or fail closed with an explicit recovery limitation. Give the apps distinct names; correlate the execution request, Sandbox creation, result collection, and cleanup. Scope files, caches, traces, and results. Keep passwords, tokens, run grants, and other customers' content out of diagnostics and generated code.

### Service identities and visible user context

| Boundary | Identity authenticated by the receiver |
| --- | --- |
| Front end → hosted agent | Front-end app's user-assigned managed identity. |
| Hosted agent → Toolbox | Hosted agent's runtime identity, using the native integration. |
| Toolbox → execution OpenAPI | **Foundry project's managed identity**, with the execution API's audience and permitted role. |
| Execution app → Sandbox management | Execution app's user-assigned managed identity, scoped to the required Sandbox resources. |

Keep each demo user's ID stable across requests and maintain separate owned agent sessions/conversations. Where authorized, send the server-derived app user ID through `x-ms-user-identity`; this requires the explicit `UserIdentityImpersonation/action` permission. Inspect the hosted runtime's resolved user context. The native Toolbox integration carries the per-request call ID for context resolution; it does not turn a demo account into an Entra user. Session IDs, call IDs, and user IDs have different meanings.

Add one compact identity view: demo user/customer, agent session, run/call/Sandbox IDs where available, and the service identity actually validated at each instrumented boundary. Label user context as **application-asserted** and caller identity as **service-authenticated**. Do not promise a built-in Toolbox user-ID display. If platform context propagation or diagnostics are unavailable, mark that boundary as unverified, retain application ownership checks, and show the evidence that exists. Different displayed IDs alone do not prove isolation.

## Execution order

### 1. Prove the identity path first

Use the first two hours as a feasibility checkpoint. Prove demo login, a service-authenticated hosted-agent call, a Toolbox OpenAPI call to the execution app, and an owned Sandbox/result. Run as both users; show the different run owners and actual service callers. Reject swapped customer/run/result/conversation IDs and unbound execution requests. Include allowed cases so an always-deny implementation cannot pass. Record exactly where user context is observable.

If this path is blocked, record the failing boundary and a concrete alternative. Use the question allowance when a decision is essential; continue unblocked work. Do not silently substitute shared-key access or self-hosting and call the requested architecture complete.

### 2. Build the smallest complete journey

First prove one hosted-orchestrator task with dynamic Sandbox creation, execution, result collection, and cleanup. Then add bounded collaboration, one controlled failure, an independent result check, and an operating budget. Verify authorization, retry safety, and cleanup at the API/tool level, including concurrent requests and reused foreign IDs. Confirm that one user's failure or cleanup cannot affect the other's run.

### 3. Teach hosted-agent creation and one task step by step

Make hosted-agent creation a hands-on learner activity. Supply infrastructure, workload role assignments, demo accounts, and starter code in the prepared lab environment, then use short checkpoints:

| Checkpoint | Learner action and visible evidence |
| --- | --- |
| Create the hosted orchestrator | Inspect its entry point, model configuration, and tools; create/deploy the hosted agent from the supplied starter. Verify readiness and record its agent/deployment reference. |
| Connect the front end | Identify both Express apps and their distinct endpoints. Configure the front-end app to invoke the hosted agent; verify that boundary. |
| Connect the execution tool | Inspect the OpenAPI operation, Toolbox registration, and project-managed-identity connection. Sign in as Alice, submit one small task, and locate the hosted-agent invocation and execution request. |
| Follow one micro-transaction | Follow Toolbox → execution app → dynamic Sandbox → result → cleanup. Inspect the app user, owned agent session, actual service caller, correlation IDs, and resource state. Repeat as Bob; explain which user values change and which service identities remain the same. |
| Expand and test | Add the second worker and review pass. Test customer isolation, execution limits, one failure/retry, independent answer checking, and the operating budget against L1–L5. |

Here, a **micro-transaction** means one bounded orchestrator task and its Sandbox lifecycle. Keep runtime creation dynamic; slow the teaching sequence through inspection checkpoints. Explain who calls whom, what each step receives/returns, and where authorization and limits are enforced. Give exact commands or UI actions, expected observations, and one short prediction/explanation at each checkpoint.

Keep background provisioning, role assignments, demo-account setup, historical IDs, and troubleshooting history in facilitator material. Keep hosted-agent creation and invocation in the learner path. Explain substantial helpers' inputs, changes, outputs, and independent verification. Apply the existing generic `lab-learner-walkthrough.md` unchanged.

### 4. Run the walkthrough gate

Apply the companion guide using fresh reviewer contexts. Supply the learner reviewer only the L1–L5 objective table, prerequisites, and delivered materials—not this implementation brief. Fix defects, then rerun affected checks. Complete one literal execution in the intended environment. Reserve one planned representative human walkthrough for final comprehension and pacing; report if omitted. Serious later changes may require targeted revalidation.

## Deliverables and completion

Keep these two handoff files together at the repository root. Update existing documentation locations rather than creating competing guides. Deliver:

- Implementation and repeatable setup for both Express apps, the hosted orchestrator, and Toolbox on `lab-reactor`.
- A concise learner guide and facilitator setup/recovery instructions.
- A one-page owner explanation: request path, identities, state, enforcement, and evidence; include three teach-back prompts to check understanding.
- Focused automated checks for L1–L5 and a compact walkthrough report.

Finish with branch/commit, learner entry point, changed files, commands/checks run, and an L1–L5 verdict of **passed / failed / blocked / not exercised** with evidence. State remaining limitations and the smallest next action. Distinguish source inspection, historical runs, and fresh live execution. Agent completion is not proof of human learning or production readiness.

## References to verify during implementation

- [Pamela's example](https://github.com/pamelafox/aca-sandboxes-multi-agent), reviewed at `89065e747e7858b7b2038daa8d8563426bcd9d2a`; record any newer baseline adopted.
- [Host Agent Framework in Foundry](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/framework-hosted-agents) and [hosted Toolbox integration](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/use-toolbox-hosted-agent).
- [OpenAPI tool integration](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/openapi) and [Toolbox authentication](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/tool-authentication).
- [App-user/session handling](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/isolate-sessions-per-user), [hosted-agent permissions](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agent-permissions), and [native Toolbox caller context](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/tools/foundry-toolbox).
- [Express capabilities](https://learn.microsoft.com/en-us/azure/container-apps/express-overview).
