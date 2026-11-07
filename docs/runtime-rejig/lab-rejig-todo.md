# Lab rejig TODOs

Deferred changes for the runtime variant. Recording an item does not authorize implementation. Keep this backlog separate from the original `lab-ready-1` recovery snapshot.

## Separate the MCP backend from the learner-facing app

- [ ] Agree and implement a separate MCP backend instead of hosting `/mcp` in the learner-facing Express application.
-



**Reason:** the current app starts the Foundry request and also receives its tool call. The user does not want this dual-role, looped design.

**Decisions before implementation:** backend hosting, request/run correlation, authentication between components, fixed Sandbox binding, deployment order and any additional Azure role assignments. Keep the design and learner permissions simple.

**Acceptance:** the learner-facing app no longer serves the MCP endpoint; Foundry reaches the separate backend through its Toolbox; generated and edited-code execution still work; active-run checks, execution limits, fixed Sandbox scope and truthful execution receipts remain enforced. Document the resulting call chain and permission changes.
