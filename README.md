## Before you're done

This repo has been created for your Microsoft Ignite 2026 session. Here's how to get it ready.

**Easiest path — use the agent (recommended):**

- Open GitHub Copilot Chat and say `help me initialize repo`. The agent will walk you through getting the README populated.
- When you're ready to publish, say `help me finalize repo`. The agent will clean up unused folders, validate everything, and remove this "Before you're done" section and other extra stuff that attendees don't need to see.
- Curious how it works? Read the [agent workflow](.github/AGENT-WORKFLOW.md).

**Doing it manually?**

Fill in the sections below yourself, then:

- Delete any placeholder folders you don't need (`data/`, `infra/`, etc.)
- Delete this "Before you're done" section
- Delete `.github/agents/`, `.github/tests/`, `.github/copilot-instructions.md`, and `.github/AGENT-WORKFLOW.md` — these are template tooling, not part of your published repo

**Folder conventions:**

- Attendee step-by-step guidance goes in `instructions/`. If you use MkDocs or a docs site instead, put it in `docs/` and link to it from this README.
- Reference material and background reading go in `docs/`.
- You can add a `.devcontainer/` folder if needed.

---

<a name="start-building"></a>

<p align="center">
<img src="img/banner-ignite-26.png" alt="Microsoft Ignite 2026" width="100%"/>
</p>

# [Microsoft Ignite 2026](https://ignite.microsoft.com)

## 🔥LAB722: Operate secure, multi-tenant agentic apps on Azure Container Apps
### Session description

Build a governed research workflow for Caldova, a fictional pharmaceutical company. Configure a Microsoft Foundry orchestrator, run specialist agents in isolated Azure Container Apps Sandboxes, prove outbound network controls, and publish a validated research application to Azure Container Apps Express. The lab is available as a guided session and as a self-paced experience with narrated segment videos.

### 🚀 Getting started

#### In a guided session

If you're following along during a live session:

1. Sign in to the provided lab environment and allow the automated deployment to continue.
2. Review the Caldova scenario and run the readiness check.
3. Open the [attendee instructions](instructions/README.md) and follow each timed segment.

#### On your own

If you're learning at your own pace:

1. Clone this repository
2. Review the prerequisites and deployment notes in the [attendee instructions](instructions/README.md)
3. Follow the same timed segments and use the linked videos when a presenter is not available

### 🎯 Learning outcomes

By the end of this session, you will be able to:

- Configure a Microsoft Foundry orchestrator that assigns bounded work to specialist agents and requires approval for sensitive actions.
- Prepare, snapshot, and clone Azure Container Apps Sandboxes while enforcing approved and denied outbound network destinations.
- Validate agent-produced application changes with deterministic evidence and publish the approved image to Azure Container Apps Express.

### 💻 Technologies used

- Azure Container Apps Sandboxes
- Azure Container Apps Express
- Microsoft Foundry Agent Service
- Azure Container Registry
- Azure Monitor Application Insights
- Azure Developer CLI (`azd`)
- Bicep and Azure Resource Manager templates
- GitHub and Model Context Protocol connections

### 📚 Continue your learning

Pick your next step based on your learning style:

| Resource | What you'll get |
|----------|-----------------|
| **[Ignite 2026 Next Steps](https://aka.ms/ignite26-next-steps)** | Additional session repos and materials from Microsoft Ignite 2026 |
| **[Microsoft AI Skills Navigator](https://aka.ms/ignite26-asn)** | Discover AI skills, learning paths, and resources for your next step |
| **[Microsoft Learn](https://aka.ms/ignite26-learn)** | Official documentation and guided learning paths on these topics |
| **[Microsoft Foundry Community](https://aka.ms/MicrosoftFoundryDiscord-Ignite26)** | Connect with other learners and experts in our Discord community |

### 🌟 Microsoft Learn MCP Server

<!-- Remove this section if the Microsoft Learn MCP Server is not relevant to the session. -->

The Microsoft Learn MCP Server gives your AI agent direct access to Microsoft's official documentation — grounded, up-to-date answers about the topics in this session.

**GitHub Copilot CLI** — Install with:

```shell
copilot plugin install microsoftdocs/mcp
```

**VS Code** — One-click install:  
[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_Microsoft_Learn_MCP-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=microsoft-learn&config=%7B%22type%22%3A%22http%22%2C%22url%22%3A%22https%3A%2F%2Flearn.microsoft.com%2Fapi%2Fmcp%22%7D)

For more information, visit the [Learn MCP Server repo](https://aka.ms/learnmcp).

### 👥 Content owners

<table>
<tr>
    <td align="center"><a href="https://github.com/simonjj">
        <img src="https://github.com/simonjj.png" width="100px;" alt="simonjj"/><br />
        <sub><b>simonjj</b></sub></a><br />
            <a href="https://github.com/simonjj" title="GitHub profile">📢</a>
    </td>
</tr></table>

### ⚖️ Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.

Any use of third-party trademarks or logos are subject to those third-party's policies.
