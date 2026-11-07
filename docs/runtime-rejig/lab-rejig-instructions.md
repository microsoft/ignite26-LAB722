# Azure Container Apps Lab for Ignite 2026 (LAB722)

## Scenario

Develop a revised version of the 75-minute Ignite lab around Caldova, the existing fictional pharmaceutical research application. Instead of using agents only to implement missing application features, explore an application that uses a Foundry agent at runtime to answer bounded research questions through tools and isolated code execution.

The central learning is the boundary between trusted application/tool code and untrusted model-generated code. Learners should be able to inspect how a request becomes a tool call, what code runs, where it runs, and why its result is accepted or rejected.

Approved simplification, November 6, 2026: no learner application sign-in, partner exercise or app-local tenants. Each allocation has one access-key-protected application and one fixed execution Sandbox. Use generated bounded Python rather than a fixed phase-count-only tool. Keep service authentication, actual execution receipts and minimal format/bounds checks; do not describe execution success as answer validation.

Apply the following service priorities and approximate content allocation as the starting point:
  - ACA Sandboxes: 50%.
  - ACA Express: 10%.
  - Foundry Agent Service: 20%.
  - Use as you see fit: 20%.

The lab should tell a complete narrative, mixing meaningful hands-on exercises with automation for repetitive setup. The intended AHA moment is that useful agent-generated analysis does not require trusting the generated code or giving it the application's credentials.

### Details

* Start from this candidate runtime flow:
  ```text
  Learner
    -> Express-hosted chat UI and API
    -> Foundry agent and model
    -> Foundry Toolbox
    -> authenticated, trusted MCP/tool backend
    -> ACA Sandbox executes generated analysis code
    -> validated results and source identifiers return through the agent to the UI
  ```
* Keep the distinction between responsibilities explicit:
  - Express hosts the user-facing application. The agent powers its conversational behavior; it is not itself the web frontend.
  - Foundry hosts reasoning and tool requests.
  - Toolbox provides the proposed tool-exposure and invocation layer, not code-execution isolation.
  - The trusted backend retains credentials, constrains execution and validates results.
  - Sandboxes isolate generated code. That code and its outputs remain untrusted and must not receive the backend's credentials.
* Begin with one front agent and a small set of bounded analysis tools. Do not assume that the existing three development specialists must become runtime agents.

* Keep the frozen dataset and its provenance visible. A candidate first task is grouping trial records by phase and returning chart data with the dataset version and source identifiers. Treat this as a software/research demonstration, not medical advice or a claim of complete or live research coverage. Once we're successful with the full implementation consider expanding the dataset beyond the current one.

* Make the following inspectable during the learner journey:
  - The user request, tool selection and generated code.
  - The actual Sandbox execution, including failures and returned results.
  - Filesystem isolation, lifecycle and allowed versus denied network access.
  - The distinction between the endpoint access key, Azure service identities and the non-root execution UID.
  - One correlated request's status, failure reason and elapsed time, shown in the existing UI or terminal.

* Use one application per learner allocation, protected by a facilitator-provided access key. No learner sign-in, Entra integration, tenant mapping, partner account or result-link authorization exercise is required. The key is an endpoint capability, not a learner identity. Keep it out of URLs, source, local storage and logs.

* Use a fixed execution Sandbox selected by trusted deployment configuration, not a model/tool argument. A second Sandbox demonstrates filesystem isolation only. Each request gets a fresh Foundry conversation; writable files persist within the allocation until the operator changes them.

* Before deciding the implementation scope, prove one authenticated round trip under actual lab identities and policies:
  **Express -> Foundry -> Toolbox -> trusted backend -> existing Sandbox -> validated response.**
Record authentication, runtime permissions, dataset delivery, execution bounds, result validation and capacity findings. The current VM-local stdio MCP bridge is not already a cloud-reachable HTTP service. Verify the hosting and identity path rather than assuming it can be attached unchanged.

* Reuse existing infrastructure where practical, but do not assume there are no ARM, connection, identity or policy changes. Distinguish application changes, project data-plane configuration and infrastructure changes in the resulting plan. Keep track and ideally minimize any required role-assignments as they require server-side work on Skillable's side which might be difficult to implement at this stage in the lab development process (we're late).

* Keep permissions out of the learner journey. Learners do not register applications, grant consent or assign roles. Preserve the existing four scoped service grants where possible. In generated-analysis mode the Sandbox group must have no assigned Azure identity; the trusted app keeps its separate managed identity. Clear the execution environment, disable privilege gain, bound time/output/process resources and reap detached analysis children. Any required provisioning permissions must still be confirmed with the lab platform.

* Limit the use of "black box" helpers and non-specific hash copy&paste actions. Feel free to use helpers for non-core activities but for learning activities please avoid/limit them.

* As part of your planning step you have a question budget of up to five questions.

### Additional context and open decisions (answered by me)

Add context here as the direction develops. These entries are placeholders, not approved requirements.
- Audience and assumed knowledge: IT professionals/SREs (primarily not developers)
- Desired research question and final user experience: I want to understand what's important and which principals when developing production-grade "tenatized" services.
- Required hands-on actions versus supplied automation: Automate everything outside of learning objectives.
- What learners must see in the UI, editor, terminal or portal: Note sure what's meant here.
- Tool interfaces, generated-code limits and result format: Note sure what's meant here.
- Skillable delivery, local development and infrastructure constraints: Continue both local and Skillable rails (automations should be azd compatible and a full ARM template should be generated as well). Instructions should follow the format and style that's currently present (numbering, crisp, following "C:\Users\simonjakesch\OneDrive - Microsoft\copilot\SKILLS\anti-ai-writing")
- Timing tradeoffs and material to retain from the current lab: Eliminate the approval and controller portions, focus on Azure components (as allocated in the service percentages).
- This document starts a separate exploration. Always be able to revert back to the `lab-ready-1` tag.
- Deploy the lab's infra and execute the lab using my local subscription (ACAPMS) in West US 3 and within two RGs (ig2026-lab-testing (development) and ig2026-lab-production (final prod-level confirmation)).




### Evaluation of success for Stage 1

Stage 1 should produce a decision-ready narrative and timed outline, with the service balance, learner actions and trust boundaries made explicit and compliant with the details and requests in this document. After approval implement the changes to both deploy locally and within the lab's Skillable environment.
