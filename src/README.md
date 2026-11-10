# Application source

The current lab application lives in [reactor](reactor). Follow the [runtime architecture](../docs/architecture.md) and [deployment quickstart](../README.md#local-deployment-quickstart).

| File | Responsibility |
| --- | --- |
| [reactor/frontend.py](reactor/frontend.py) and [reactor/web/index.html](reactor/web/index.html) | Customer sign-in, research UI and hosted-agent invocation |
| [reactor/hosted.py](reactor/hosted.py) | Foundry-hosted research orchestration through the managed MCP Toolbox |
| [reactor/execution.py](reactor/execution.py) | Owned execution state and bounded specialist/QA operations |
| [reactor/agent_runtime.py](reactor/agent_runtime.py) | Actual specialist and QA agent loops inside Sandboxes |
| [reactor/sandboxes.py](reactor/sandboxes.py) | Task Sandbox creation, execution and cleanup |
| [reactor/ownership.py](reactor/ownership.py), [reactor/binding.py](reactor/binding.py), [reactor/service_auth.py](reactor/service_auth.py) | Customer/conversation ownership, run grants and managed-identity caller validation |
| [reactor/research.py](reactor/research.py), [reactor/evaluation.py](reactor/evaluation.py) | Frozen-data research contract and independent evaluation |
| [reactor/openapi.json](reactor/openapi.json) | Execution operations imported into `runtime-research` |
| [reactor/Containerfile](reactor/Containerfile), [reactor/HostedContainerfile](reactor/HostedContainerfile), [reactor/AgentContainerfile](reactor/AgentContainerfile) | Separate services, hosted orchestrator and preloaded specialist images |

`orchestrator/`, `workers/`, `developer-image/`, `research-portal/` and `runtime/` retain earlier implementation/build tools used by existing deployments, frozen-data checks and regression tests. They are not the current learner workflow. The legacy research portal includes an MIT-licensed dashboard adaptation from [Plus Admin Free](https://github.com/BootstrapDash/PlusAdmin-Free-Bootstrap-Admin-Template); its source copyright and permission notice remain with that implementation.

Use the [image catalog](../data/reactor-research-images.json) for the current immutable releases. Changing source does not update an already-published image or captured VM. Do not copy model, management or registry credentials into an image or snapshot.
