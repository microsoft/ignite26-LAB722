# Lab rejig exploration

**Status: deferred exploration, not an approved implementation plan.**

Recorded November 4, 2026. Keep the existing lab approach in place while making separately requested improvements. This document does not authorize application, infrastructure, image, or lab-title changes.

## Why consider a different approach

The current lab uses Foundry agents during application development: specialists implement two missing query functions in isolated Sandboxes, independent checks accept their changes, and the learner builds and deploys an image to Container Apps Express. The running application itself does not use a Foundry agent.

A desktop coding agent would be a more natural baseline for some of that development work. A possible alternative is to teach a runtime application that uses governed tools and executes generated analysis code without trusting it.

## Proposed runtime experience

Keep Caldova's Express-hosted web application and frozen public dataset. Add a conversational research interface backed by a Foundry agent.

```text
Learner
  -> Express-hosted chat UI and API
  -> Foundry agent and model
  -> Foundry Toolbox
  -> authenticated, trusted MCP/tool backend
  -> ACA Sandbox running generated analysis code
  -> validated results and source identifiers returned through the agent to the UI
```

The agent powers the conversational experience; it is not itself the web frontend. Backend specialist agents could be exposed through tools, but a first experiment should use one front agent and a small set of bounded analysis tools rather than require a new multi-agent topology.

An example task is grouping the frozen trial records by phase and returning a chart with the dataset version and source identifiers. This remains a software/research demonstration, not medical advice or a claim about a complete or live dataset.

## What learners would inspect

- The user request, selected tool, generated analysis code, and actual execution result.
- The distinction between model instructions and enforced tool/execution boundaries.
- Sandbox filesystem isolation, lifecycle, and allowed versus denied network requests.
- The fixed dataset and the checks applied before results reach the application.

Toolbox governs tool exposure and invocation; it is not the code-execution isolation boundary. The trusted backend would retain credentials, constrain jobs, and validate results. Generated code and returned content remain untrusted. Sandbox execution must not receive the backend's credentials.

## Infrastructure assessment

The existing templates define a Foundry project/model, Express environment, Sandbox group, registry, and supporting identities. Reusing these looks plausible, but no end-to-end feasibility proof has been completed.

| Area | Assessment to revisit |
|---|---|
| Toolbox and agent definitions | Project-scoped data-plane artifacts; not a separate Toolbox ARM deployment |
| Backend connections | Authentication and project connections are separate concerns; connection resources can be ARM-backed |
| Tool hosting | The existing MCP bridge uses VM-local stdio; it cannot be attached unchanged as a cloud-reachable HTTP endpoint |
| Runtime identity | Learner grants do not automatically authorize a runtime service; scope its Foundry and Sandbox permissions explicitly |
| Express hosting | Consider adding HTTP MCP endpoints to the existing backend or a small companion service; verify the user-assigned runtime identity path |
| Networking | An authenticated public endpoint appears the smaller starting point; private MCP connectivity would add networking requirements |

Working assessment: potentially a small infrastructure delta, but a substantial application and learner-instruction redesign. Do not equate "Toolbox is data plane" with "no ARM, identity, or policy changes."

## First experiment when this is resumed

Prove one authenticated round trip under actual lab identities and policies:

**Express -> Foundry -> Toolbox -> trusted backend -> existing Sandbox -> validated response.**

Check endpoint authentication, service permissions, dataset delivery, generated-code isolation, result validation, and available Sandbox capacity. Keep reasoning in Foundry rather than assuming the Sandbox needs unrestricted model/network access.

Only after that succeeds should we decide the application changes, learner exercises, instruction updates, and minimum infrastructure changes. The existing infrastructure provisioning/access regressions are separate work and are not resolved by this proposal.

## References from the exploration

- [Foundry Toolbox](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox)
- [Foundry MCP tools](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol)
- [Foundry project connection resources](https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/accounts/projects/connections)
- [Container Apps Express](https://learn.microsoft.com/en-us/azure/container-apps/express-overview)
- Existing implementation: `src\research-portal\backend\app.py`, `src\sandbox-mcp\server.py`, and `infra\modules\`.
