# Runtime analysis

This retained legacy application runs bounded generated or edited Python against the prepared public-data Sandbox. It is not the current research-swarm lab; start with the [current architecture](../../docs/architecture.md). This page documents only the older implementation.

**Access:** the page and `/health` are public; `/api/config`, `/api/analyze`, `/api/execute` and `/mcp` require `X-Lab722-Proof-Key`. A facilitator supplies the endpoint key privately. The browser clears the password input and retains the key only in tab memory. There is no learner sign-in, tenant selector or durable user/result ownership.

**Execution:** Ask Foundry follows Express API -> Foundry agent -> Toolbox -> authenticated MCP backend -> Sandbox. Run edited code follows Express API -> Sandbox without calling Foundry. `execute_python(run_id, code)` accepts only the active server-created run and executes once in the configured Sandbox. One request is active at a time; another receives HTTP 409.

The trusted root supervisor checks frozen data and identity availability, then runs code as UID/GID 65534 with a cleared environment, no-new-privileges, 30-second wall/15-second CPU limits, 256 MiB address space and 128 KiB combined output. It kills and reaps detached analysis children and checks the frozen files again. The Sandbox group must have no assigned Azure identity. These bounds are not validation of an arbitrary answer.

Actual stdout/stderr, exit status and the correlated receipt determine execution outcome, not the model summary. Valid finite JSON can produce a chart; other output remains visible text. Each Foundry request creates a fresh conversation, but `/workspace` files persist within the allocation. B is an independent snapshot-derived filesystem exercise, not a partner identity.

## Preparation and checks

Existing legacy allocations require their original deployment inputs and explicitly authorized resource scope; the retired walkthrough remains in Git history. Prepare A before app deployment and reuse a matching Toolbox instead of publishing another version. This is not the current root `azd` path. Learners do not deploy infrastructure or assign service grants.

`Containerfile` reuses the existing proof stack, pins its Python base/native CLI and runs `tests/test_runtime.py` before publication. Upload only an explicit source context containing this directory, `src/sandbox_process.py` and that focused test. Do not upload local environments, credentials or caches.

The approved test-allocation deployment passed generated-code/browser, direct execution, timeout, busy response, output, detached-child, read-only, egress and stop/resume checks on November 6, 2026. Fresh Skillable delivery and measured learner timing remain separate checks.
