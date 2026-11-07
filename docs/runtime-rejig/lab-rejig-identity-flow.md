# LAB722 reactor: owner explanation

## Request path and why it is separated

```text
Browser demo session
  -> frontend Express: login, owned UI/API, submit/status/cancel
  -> Foundry hosted Responses workflow: one worker, then two workers and review
  -> managed Toolbox MCP-to-OpenAPI gateway
  -> execution Express: service token + owned run grant, known-answer acceptance
  -> newly created task Sandbox: generated Python, result collection, exact deletion
```

Neither Express app exposes `/mcp`. The frontend has no Sandbox-management code. The execution service has no hosted-agent reasoning loop. Pamela's task-scoped create/invoke/collect/delete pattern is reused, not its original in-process WebSocket hosting.

## Identities and authority

| Receiver | Authenticated service | Application authorization |
|---|---|---|
| Frontend | Maintained signed demo session | Password-hashed Alice/Bob accounts; server-derived fixed memberships |
| Hosted agent | Frontend UAMI | Backend-issued binding in authenticated request metadata, never model input |
| Toolbox | Hosted runtime identity and native current-call headers | Fresh Toolbox connection owned by the request |
| Execution management API | Frontend UAMI, exact tenant/audience/object ID | Server-derived fixed demo principal; owned run/result/conversation/cancel |
| Execution offload API | Foundry project MI, exact tenant/audience/object ID | Expiring opaque grant bound to user/customer/run/conversation; single execution claim |
| Sandbox management | Execution UAMI with group-scoped Data Owner | Exact task resources selected by trusted backend, never a model-provided resource ID |

Alice (`user-alice`, `customer-alice`) and Bob (`user-bob`, `customer-bob`) are **application accounts**, not Entra users. User/customer values are **application-asserted**. A validated bearer caller is **service-authenticated**. The project's MI does not become Alice when Alice submits work.

The hosted workflow reads a binding from request metadata before the model runs. It generates only `{step, code}` proposals, then programmatically supplies the declared OpenAPI identity/grant fields to `FoundryToolbox.call_tool`. Model-provided grants, URLs and identity keys are discarded. We do not assume arbitrary MCP headers pass through the managed gateway.

Optional `x-ms-user-identity` delegation is not enabled or proven. It would require explicit impersonation permission. Hosted platform user/call/session values are shown only when returned; a service-resolved platform user is not described as a delegated demo user.

## State, enforcement and evidence

The execution app alone owns SQLite account hashes, run/ownership/idempotency records, hashed grants and result artifacts. The frontend holds a boot-specific signed cookie and owned progress, not a copied authority or browser-held run grant. Exact memberships are selected after login. Reusing a run key returns the original record and never replays ambiguous execution.

Each task restores the approved frozen snapshot, gets its own private fictional note and writable `/workspace`, and runs as UID 65534 with a cleared environment. Public data stays read-only. The supervisor enforces CPU/memory/process/output/wall bounds and reaps detached children. The Sandbox group must expose no usable Azure identity. Deny-all egress must be demonstrated from inside the Sandbox.

Receipts correlate run, task, Sandbox, snapshot, marker, code digest, frozen hashes, exit/status, stdout/stderr, elapsed time and deletion. The independent checker requires exact phase counts or safety count **and source IDs**. A model review explains the result but cannot change acceptance.

There are at most two active task Sandboxes, one reserved run per customer, and at most two workers per run. Capacity is not released until verified cleanup. Available usage is actual receipt Sandbox seconds and returned hosted token usage; it is not a dollar-cost estimate.

SQLite and frontend sessions are ephemeral in Express. On lost state, old runs/grants/results are not reconstructed or reassigned. New authority initialization refuses to proceed if reactor task resources remain. An existing ambiguous run needs owned cancellation and explicit reconciliation. There is no promised durable restart recovery.

**Current gate:** service API audience unavailable; tenant creation declined. The real hosted/gateway token, argument mapping and end-to-end ownership remain unverified. Local test identities are not live service-token evidence.

## Three teach-back prompts

1. Bob has Alice's run ID but no owned binding. Which two checks prevent retrieval and execution, and why is the project's MI token insufficient by itself?
2. A worker exits zero with the wrong count. Which service rejects it, and which evidence ties its stdout to the executed code and frozen input?
3. An app replica disappears while Sandbox creation is uncertain. Why must capacity remain reserved, and what exact resources may recovery delete?
