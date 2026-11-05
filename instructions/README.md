# 2. Build a research app with an agent team

Caldova, a fictional pharmaceutical company, needs a research panel that shows clinical trials and adverse-event reports. First, deploy its starter application with Container Apps Express. Its two data-query functions are missing: your job is to use an agent team to implement them, check the results, and deploy the completed application.

You will use **Microsoft Foundry** to coordinate the agents, **Azure Container Apps Sandboxes** to isolate their work, and **Azure Container Apps Express** to run the application.

## 2.1 What you will do

| Activity | Minutes |
|---|---:|
| Sign in and check your environment | 5 |
| Deploy and explore the starter with Express | 7 |
| Review the agent team's plan | 12 |
| Create Sandbox clones and try their network policy | 15 |
| Run the agents and review their results | 23 |
| Build and deploy the application | 6 |
| Compare a recorded example and discuss the results | 7 |
| **Total** | **75** |

Use the same steps in a guided session or at your own pace. The times are estimates; remote operations can take longer.

## 2.2 Your lab environment

Your Windows VM has the tools and code ready at:

```text
C:\Users\LabUser\code\ignite26-LAB722
```

Use the Azure account and subscription supplied with your lab. Infrastructure is already provisioned; you do not need to install tools or run an infrastructure deployment.

Keep one PowerShell 7 terminal open throughout the lab. Later steps use variables created in earlier steps. Each command block runs as one unit and pauses at its **Enter** checkpoints so you can inspect the output before continuing.

When asking for help, give the numbered heading (for example **8.1.3**), the command, and its error. You review and authorize your own lab actions; instructor sign-off is not required to continue when the checks pass.
