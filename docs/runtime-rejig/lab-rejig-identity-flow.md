# LAB722 access flow

The user removed learner application sign-in and partner authorization on November 6, 2026. The earlier identity-agent handoff is superseded; no client registration, consent, redirect URI, second account or tenant mapping is needed for this version.

## Learner access

1. Open the allocated Caldova URL.
2. Enter the facilitator-provided access key and select **Connect**.
3. Submit a request or run edited Python in the allocation's fixed Sandbox.

The key is an endpoint capability, not a signed-in user or an app-local tenant. Keep it private. It is sent in an HTTPS header and held in tab memory, never in a URL or browser local storage. Refreshing the page clears that tab's key.

## Service access

```text
Browser access key -> trusted Express API
Express managed identity -> Foundry
Foundry project managed identity -> Toolbox
Toolbox connection key -> MCP backend
Express managed identity -> fixed Sandbox execution
```

The Sandbox group has no assigned Azure identity in analysis mode. Generated Python executes as UID 65534 with a cleared environment and no-new-privileges. The Azure service identity is not the Python process identity.

No cross-user or cross-tenant isolation is claimed inside one allocation. Writable Sandbox files are shared between successive requests there. A separate second Sandbox is used only to demonstrate filesystem isolation.

The facilitator still needs the platform's normal Azure provisioning and learner CLI access. Removing app sign-in does not grant Azure access or resolve an Azure Policy denial. Learners do not assign roles or alter directory policy.
