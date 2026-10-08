# Segment 2 - Configure the orchestrator (15 minutes)

Configure one Microsoft Foundry orchestrator, attach its approved connections, and review the plan it creates for three specialist workers.

## Why this segment matters

The orchestrator reasons about the work but does not execute repository code itself. All code and data operations run through approved tools in isolated Sandboxes.

## Services used

- Microsoft Foundry Agent Service
- GitHub MCP connection
- Sandbox MCP connection

## Learning objectives

- Configure an orchestrator from a supplied starter definition.
- Apply tool and approval boundaries.
- Review a grounded plan before allowing execution.

## Starting state

- The attendee's Foundry project, API endpoint, and model deployment are available.
- Read-only GitHub access and a staged source fallback are configured.
- The Sandbox MCP endpoint is available.

## Task 1 - Configure tools and approvals

1. Open the supplied Foundry project.
2. Create the Caldova orchestrator from the starter definition.
3. Attach the prepared GitHub and Sandbox MCP connections.
4. Restrict the agent to the tools named in the lab.
5. Require approval for Sandbox creation, image publication, and deployment updates.

## Task 2 - Review the worker plan

1. Ask the orchestrator to summarize the feature request and acceptance criteria.
2. Ask it to assign work to the clinical-trials, drug-safety, and quality/governance roles.
3. Verify that each role has a bounded task and structured output contract.
4. Confirm that the plan uses deterministic tests for the release decision.
5. Approve creation of the primary Sandbox.

## Checkpoint

- The orchestrator can read the request.
- Only approved tools are available.
- Sensitive actions require approval.
- The three worker assignments match the supplied contracts.

## Troubleshooting

| Symptom | Check | Recovery |
|---|---|---|
| GitHub connection is unavailable | Check the connection status | Use the staged source bundle |
| Sandbox tool is missing | Confirm the prepared MCP connection | Reattach the supplied connection |
| Plan contains an unsupported medical conclusion | Check the orchestrator instructions | Use the supplied responsible-use instruction block |

## Segment outcome

The orchestrator has an approved plan and can create the isolated execution environment.
